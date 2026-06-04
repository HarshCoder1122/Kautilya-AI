import axios from 'axios';

// When the app is served from our own domain (revealiq.in or any subdomain),
// ALWAYS route through the same origin so the ai.revealiq.in → HF Space proxy
// handles auth headers, CORS, and rate-limiting. Hitting the raw HF Space URL
// bypasses the proxy and breaks signed cookies / custom auth headers.
const _hn = (typeof window !== 'undefined' ? window.location.hostname : '') || '';
const _onOwnDomain = /(^|\.)revealiq\.in$/i.test(_hn);
const API_BASE_URL = _onOwnDomain
  ? window.location.origin
  : (process.env.REACT_APP_API_URL
      || (_hn === 'localhost' ? 'http://localhost:5000' : window.location.origin));

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper to get consistent headers for both axios and fetch
export const getAuthHeaders = () => {
  const fbToken = localStorage.getItem('firebase_token');
  const hfToken = process.env.REACT_APP_HF_API_TOKEN;
  const headers = {};

  if (hfToken) {
    // 1. Private HF Space: Authorization must be HF Token
    headers['Authorization'] = `Bearer ${hfToken}`;
    if (fbToken) {
      headers['X-Firebase-Token'] = fbToken;
    }
  } else if (fbToken) {
    // 2. Public Space/Local: Authorization is Firebase Token
    headers['Authorization'] = `Bearer ${fbToken}`;
  }

  return headers;
};

// Maps (in-chat map card). Uses the shared `api` instance so the base URL +
// auth interceptors apply. Endpoints degrade to OpenStreetMap if Mappls keys
// aren't set, so these always return usable data.
export const mapsAPI = {
  getConfig: async () => (await api.get('/api/maps/config')).data,
  nearby: async ({ keyword, radius, lat, lng } = {}) => {
    const params = { keyword: keyword || 'restaurant', radius: radius || 3000 };
    if (lat != null && lng != null) { params.lat = lat; params.lng = lng; }
    return (await api.get('/api/maps/nearby', { params })).data;
  },
  directions: async ({ from, to } = {}) => {
    const params = { from_lat: from[0], from_lng: from[1], to_lat: to[0], to_lng: to[1] };
    return (await api.get('/api/maps/directions', { params })).data;
  },
  // Persist / restore a map card's resolved results (so reopening a chat shows
  // the same map without re-asking for location).
  getResult: async (mapId) => (await api.get(`/api/maps/result/${encodeURIComponent(mapId)}`)).data,
  saveResult: async (payload) => (await api.post('/api/maps/save', payload)).data,
};

// Proactive Firebase token refresh — used before streaming calls because
// raw fetch() bypasses the axios 401-retry interceptor. Refreshes if the
// cached token was issued > 50min ago, or always when `force` is true.
// Safe to call concurrently: in-flight refresh is shared via the promise
// cache so we never burn multiple Firebase round-trips for the same tab.
const TOKEN_STALE_MS = 50 * 60 * 1000;
let _tokenRefreshInFlight = null;
export const ensureFreshFirebaseToken = async ({ force = false } = {}) => {
  try {
    const issuedAt = parseInt(localStorage.getItem('firebase_token_issued_at') || '0', 10);
    const age = Date.now() - issuedAt;
    if (!force && issuedAt && age < TOKEN_STALE_MS) {
      return localStorage.getItem('firebase_token');
    }
    if (_tokenRefreshInFlight) return _tokenRefreshInFlight;
    _tokenRefreshInFlight = (async () => {
      try {
        const { getAuthInstance } = await import('./firebase.js');
        // Firebase Auth may not be initialized yet on cold page load.
        // Retry up to 5 times (1 second total) before giving up.
        let auth = getAuthInstance();
        for (let i = 0; !auth && i < 5; i++) {
          await new Promise(r => setTimeout(r, 200));
          auth = getAuthInstance();
        }
        const u = auth && auth.currentUser;
        if (!u) return localStorage.getItem('firebase_token');
        const token = await u.getIdToken(true);
        localStorage.setItem('firebase_token', token);
        localStorage.setItem('firebase_token_issued_at', String(Date.now()));
        return token;
      } catch (e) {
        console.warn('[Auth] ensureFreshFirebaseToken failed:', e);
        return localStorage.getItem('firebase_token');
      } finally {
        _tokenRefreshInFlight = null;
      }
    })();
    return _tokenRefreshInFlight;
  } catch {
    return localStorage.getItem('firebase_token');
  }
};

// Add Firebase token to requests if available. Also refresh the token
// proactively when it's > 50min old (axios path) — this prevents the very
// first request after a long tab-background period from 401-ing.
api.interceptors.request.use(async (config) => {
  await ensureFreshFirebaseToken({ force: false });
  const authHeaders = getAuthHeaders();
  Object.assign(config.headers, authHeaders);
  return config;
}, (error) => Promise.reject(error));

// On 401, force-refresh the Firebase token and retry once. Reapply the
// FULL header set so X-Firebase-Token (private HF Spaces) gets refreshed
// alongside Authorization.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      try {
        await ensureFreshFirebaseToken({ force: true });
        Object.assign(original.headers, getAuthHeaders());
        return api(original);
      } catch (e) {
        console.warn('[Auth] Token refresh on 401 failed:', e);
      }
    }
    return Promise.reject(error);
  }
);

// Build a streaming POST that proactively refreshes the Firebase token
// when stale, and retries once on a 401. FormData can't be safely re-sent
// after refresh without rebuilding it, so the body is constructed via a
// factory (`buildBody`) that we can call again.
const _postStreamWithAuth = async (url, buildBody, options = {}) => {
  await ensureFreshFirebaseToken({ force: false });

  const doFetch = async () => {
    const { body, contentType } = buildBody();
    const headers = { ...getAuthHeaders() };
    if (contentType) headers['Content-Type'] = contentType;
    return fetch(url, { method: 'POST', headers, body, signal: options.signal });
  };

  let response = await doFetch();
  if (response.status === 401) {
    await ensureFreshFirebaseToken({ force: true });
    response = await doFetch();
  }
  return response;
};

// Chat API
export const chatAPI = {
  // Stream chat message
  streamMessage: async (message, sessionId = null, model = 'auto', files = [], options = {}) => {
    const buildBody = () => {
      if (files && files.length > 0) {
        const fd = new FormData();
        fd.append('message', message);
        if (sessionId) fd.append('session_id', sessionId);
        fd.append('model', model);
        if (options.maxThinking) fd.append('max_thinking', 'true');
        files.forEach(file => fd.append('files', file));
        // Browser sets multipart boundary automatically; don't set Content-Type.
        return { body: fd, contentType: undefined };
      }
      return {
        body: JSON.stringify({
          message,
          session_id: sessionId,
          model,
          max_thinking: !!options.maxThinking,
        }),
        contentType: 'application/json',
      };
    };
    return _postStreamWithAuth(`${API_BASE_URL}/api/jarvis/stream`, buildBody, options);
  },

  // Stream deep research; this hits the backend research pipeline
  // so SerpAPI/source gathering is actually used.
  streamResearch: async (question, sessionId, options = {}) => {
    const buildBody = () => ({
      body: JSON.stringify({ question, session_id: sessionId, depth: options.depth || 'standard' }),
      contentType: 'application/json',
    });
    return _postStreamWithAuth(`${API_BASE_URL}/api/research/stream`, buildBody, options);
  },

  // Get chat history
  getHistory: async () => {
    const response = await api.get('/api/jarvis/history');
    return response.data;
  },

  // Get specific conversation
  getConversation: async (sessionId) => {
    const response = await api.get(`/api/jarvis/history/${sessionId}`);
    return response.data;
  },

  // Delete conversation
  deleteConversation: async (sessionId) => {
    const response = await api.delete(`/api/jarvis/history/${sessionId}`);
    return response.data;
  },

  // Get user status
  getStatus: async () => {
    const response = await api.get('/api/jarvis/status');
    return response.data;
  },
};

// Agents API
export const agentsAPI = {
  // List agents
  list: async () => {
    const response = await api.get('/api/agents/list');
    return response.data;
  },

  // Create agent
  create: async (agentData) => {
    const response = await api.post('/api/agents/create', agentData);
    return response.data;
  },

  // Get agent details
  get: async (agentId) => {
    const response = await api.get(`/api/agents/${agentId}`);
    return response.data;
  },

  // Update agent
  update: async (agentId, agentData) => {
    const response = await api.post(`/api/agents/${agentId}/update`, agentData);
    return response.data;
  },

  // Delete agent
  delete: async (agentId) => {
    const response = await api.post(`/api/agents/${agentId}/delete`);
    return response.data;
  },

  // Chat with agent
  chat: async (agentId, messages) => {
    const response = await fetch(`${API_BASE_URL}/api/agents/${agentId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ messages }),
    });
    return response;
  },

  // Get agent logs
  getLogs: async (agentId) => {
    const response = await api.get(`/api/agents/${agentId}/logs`);
    return response.data;
  },

  // Upload knowledge base file
  uploadKB: async (agentId, files) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    const response = await api.post(`/api/agents/${agentId}/kb`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // Add URL to knowledge base
  addKBUrl: async (agentId, url) => {
    const response = await api.post(`/api/agents/${agentId}/kb-url`, { url });
    return response.data;
  },

  // Crawl up to N pages from a start URL (same-origin BFS, cap 50)
  crawlKBSite: async (agentId, url, maxPages = 50) => {
    const response = await api.post(`/api/agents/${agentId}/kb-crawl`, { url, max_pages: maxPages }, {
      timeout: 300000, // 5 min — crawl can take a while
    });
    return response.data;
  },

  // Get knowledge base
  getKB: async (agentId) => {
    const response = await api.get(`/api/agents/${agentId}/kb`);
    return response.data;
  },

  // Delete KB file
  deleteKBFile: async (agentId, fileId) => {
    const response = await api.delete(`/api/agents/${agentId}/kb/${fileId}`);
    return response.data;
  },

  // Preview voice for an agent
  previewVoice: async ({ voice = 'shubh', provider = 'sarvam', text }) => {
    const response = await api.post('/api/voice/preview', {
      voice,
      provider,
      text,
    }, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Generate/Rotate public embed token
  rotateEmbedToken: async (agentId, allowedOrigins = ['*']) => {
    const response = await api.post(`/api/agents/${agentId}/embed-token`, { allowed_origins: allowedOrigins });
    return response.data;
  },
};

// Campaigns API
export const campaignsAPI = {
  // List campaigns
  list: async () => {
    const response = await api.get('/api/campaigns');
    return response.data;
  },

  // Create campaign
  create: async (campaignData) => {
    const response = await api.post('/api/campaigns/create', campaignData);
    return response.data;
  },

  // Upload CSV for campaign
  upload: async (agentId, name, file) => {
    const formData = new FormData();
    formData.append('agent_id', agentId);
    formData.append('name', name);
    formData.append('file', file);
    const response = await api.post('/api/campaigns/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // Start campaign
  start: async (campaignId) => {
    const response = await api.post(`/api/campaigns/${campaignId}/start`);
    return response.data;
  },

  // Stop/Pause campaign
  stop: async (campaignId) => {
    const response = await api.post(`/api/campaigns/${campaignId}/stop`);
    return response.data;
  },

  // Get campaign status
  getStatus: async (campaignId) => {
    const response = await api.get(`/api/campaigns/${campaignId}/status`);
    return response.data;
  },

  // Delete campaign
  delete: async (campaignId) => {
    const response = await api.delete(`/api/campaigns/${campaignId}`);
    return response.data;
  },
};

// User API
export const userAPI = {
  // Get user profile
  getProfile: async () => {
    const response = await api.get('/api/user/profile');
    return response.data;
  },

  // Update user profile
  updateProfile: async (profileData) => {
    const response = await api.put('/api/user/profile', profileData);
    return response.data;
  },

  // Get full settings doc
  getSettings: async () => {
    const response = await api.get('/api/user/settings');
    return response.data;
  },

  // Save full settings doc
  saveSettings: async (settingsData) => {
    const response = await api.post('/api/user/settings', settingsData);
    return response.data;
  },

  // Idempotent first-login welcome trigger. Safe to call after every login.
  welcomeCheck: async () => {
    const response = await api.post('/api/user/welcome-check');
    return response.data;
  },
};

// Artifacts API
export const artifactsAPI = {
  // Create artifact (excel, pdf, etc.)
  create: async (artifactData) => {
    const response = await api.post('/api/artifact/create', artifactData, {
      responseType: 'blob'
    });
    return response.data;
  },

  // List supported artifact types
  getTypes: async () => {
    const response = await api.get('/api/artifact/types');
    return response.data;
  }
};

// Coder Projects — multi-file workspaces persisted to Firestore so coder
// projects survive across reloads / message edits.
export const coderProjectsAPI = {
  save: async ({ uid, message_id, title, files }) => {
    const response = await api.post('/api/coder/project/save', { uid, message_id, title, files });
    return response.data;
  },
  load: async (message_id, uid) => {
    const response = await api.get(`/api/coder/project/${encodeURIComponent(message_id)}`, {
      params: { uid }
    });
    return response.data;
  },
};

// API Keys
export const keysAPI = {
  list: async () => {
    const response = await api.get('/api/keys/list');
    return response.data;
  },

  create: async (keyData) => {
    const response = await api.post('/api/keys/create', keyData);
    return response.data;
  },

  revoke: async (keyHash) => {
    const response = await api.post('/api/keys/revoke', { key_hash: keyHash });
    return response.data;
  },
};

// Telephony
export const telephonyAPI = {
  getConfig: async () => {
    const response = await api.get('/api/telephony/config');
    return response.data;
  },

  saveConfig: async (config) => {
    const response = await api.post('/api/telephony/save', config);
    return response.data;
  },

  outbound: async ({ agent_id, agentId, to, to_number }) => {
    const resolvedAgentId = agent_id || agentId;
    const response = await api.post(`/api/telephony/outbound-call`, {
      agent_id: resolvedAgentId,
      to_number: to_number || to,
    });
    return response.data;
  },
};

// Billing API
export const billingAPI = {
  // Get billing config and user tier
  getConfig: async () => {
    const response = await api.get('/api/billing/config');
    return response.data;
  },

  // Create payment order
  createOrder: async (amount, planType) => {
    const response = await api.post('/api/billing/create-order', { amount, plan_type: planType });
    return response.data;
  },

  // Verify payment
  verifyPayment: async (paymentData) => {
    const response = await api.post('/api/billing/verify-payment', paymentData);
    return response.data;
  },

  // Recover a payment that Razorpay captured but our system missed
  reconcilePayment: async (razorpayPaymentId) => {
    const response = await api.post('/api/billing/reconcile-payment', { razorpay_payment_id: razorpayPaymentId });
    return response.data;
  },
};

// Leads API
export const leadsAPI = {
  // List leads
  list: async () => {
    const response = await api.get('/api/leads');
    return response.data;
  },

  // Update lead
  update: async (leadId, data) => {
    const response = await api.patch(`/api/leads/${leadId}`, data);
    return response.data;
  },

  // Delete lead
  delete: async (leadId) => {
    const response = await api.delete(`/api/leads/${leadId}`);
    return response.data;
  },
};

// Analytics API
export const analyticsAPI = {
  // Get usage analytics
  getUsage: async () => {
    const response = await api.get('/api/analytics/usage');
    return response.data;
  },

  // Get call volume
  getCallVolume: async () => {
    const response = await api.get('/api/analytics/call-volume');
    return response.data;
  },

  // Get trends
  getTrends: async () => {
    const response = await api.get('/api/analytics/trends');
    return response.data;
  },
};

// TTS API
export const ttsAPI = {
  // RevealIQ TTS - calls backend endpoint (backend uses ENV keys)
  revealIQ: {
    synthesize: async (text, model = 'kokoro-en', voice = 'af_bella', speed = 1.0) => {
      const response = await api.post('/api/tts/revealiq/synthesize', {
        text,
        model,
        voice,
        speed,
      }, {
        responseType: 'blob',
      });
      return response.data;
    },

    stream: async (text, model = 'kokoro-en', voice = 'af_bella', speed = 1.0) => {
      const baseUrl = API_BASE_URL.replace(/\/+$/, '');
      const response = await fetch(`${baseUrl}/api/tts/revealiq/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ text, model, voice, speed }),
      });
      return response;
    },

    getVoices: (model) => {
      if (model && model.includes('hi')) {
        return ['hf_alpha', 'hf_beta'];
      }
      return ['af_heart', 'af_bella', 'af_nicole', 'af_sky', 'am_adam', 'am_michael'];
    },
  },

  // Cartesia TTS - calls backend endpoint
  cartesia: {
    synthesize: async (text, voice) => {
      const response = await api.post('/api/tts/cartesia/synthesize', { text, voice }, { responseType: 'blob' });
      return response.data;
    },
    getVoices: () => [
      { id: '79a125e8-cd45-4c05-8747-8f8c6989182a', name: 'British Male (Baritone)' },
      { id: '694f9389-aac1-45b6-b726-9d9369182a5a', name: 'Soft Female (US)' },
      { id: 'a0e99861-dfaf-42ad-86c7-fb0ac95fc403', name: 'Professional Male' },
      { id: '50fb60ef-c195-4674-8b6f-11758c0c4558', name: 'Sweet Female' },
    ]
  },

  // ElevenLabs TTS - calls backend endpoint
  elevenLabs: {
    synthesize: async (text, voiceId) => {
      const response = await api.post('/api/tts/elevenlabs/synthesize', { text, voice_id: voiceId }, { responseType: 'blob' });
      return response.data;
    },
    getVoices: () => [
      { id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel (Female, Soft)' },
      { id: 'AZnzlk1XhkUvS5ch7s7i', name: 'Nicole (Female, Whisper)' },
      { id: 'EXAVITQu4vr4xnSDxMaL', name: 'Bella (Female, Professional)' },
      { id: 'ErXw9S1aaH7HBy8S4H2u', name: 'Antoni (Male, Deep)' },
      { id: 'Lcf7m3M63S7G38m7V8p7', name: 'Domi (Female, News)' },
      { id: 'MF3m7V8p7m7V8p7m7V8p', name: 'Josh (Male, Generic)' },
    ]
  },

  // Sarvam TTS - calls backend endpoint
  sarvam: {
    synthesize: async (text, language = 'hi-IN') => {
      const response = await api.post('/api/tts/sarvam/synthesize', { text, language }, { responseType: 'blob' });
      return response.data;
    },
    getLanguages: () => [
      { id: 'hi-IN', name: 'Hindi' },
      { id: 'en-IN', name: 'English (India)' },
      { id: 'bn-IN', name: 'Bengali' },
      { id: 'kn-IN', name: 'Kannada' },
      { id: 'ml-IN', name: 'Malayalam' },
      { id: 'mr-IN', name: 'Marathi' },
      { id: 'ta-IN', name: 'Tamil' },
      { id: 'te-IN', name: 'Telugu' },
      { id: 'gu-IN', name: 'Gujarati' },
    ]
  },
};

// Integrations API
export const integrationsAPI = {
  list: async () => {
    const res = await api.get('/api/integrations');
    return res.data;
  },
  save: async (provider, data) => {
    const res = await api.post(`/api/integrations/${provider}/save`, data);
    return res.data;
  },
  disconnect: async (provider) => {
    const res = await api.post(`/api/integrations/${provider}/disconnect`);
    return res.data;
  },
  connectOAuth: async (provider, redirectUri) => {
    const res = await api.get(`/api/integrations/${provider}/connect`, {
      params: redirectUri ? { redirect_uri: redirectUri } : undefined,
    });
    return res.data;
  },
  getMcpStatus: async () => {
    const res = await api.get('/api/mcp/status');
    return res.data;
  },
};

export default api;
