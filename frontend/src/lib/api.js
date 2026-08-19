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

// ─── Lightweight client-side cache for dashboard reads ─────────────────────
// The dashboard tabs each refetch from Firestore on every mount/refresh, which
// hammers the DB when the user flips between Leads / Calls / Agents or reloads.
// cachedGet() serves a recent response straight from localStorage while it's
// still fresh (within `ttl`), so repeat loads read from cache instead of the
// DB. Mutations call bustCache(...) to drop the stale entry immediately so the
// next read reflects the write. Pass `force` from the caller to bypass cache
// (e.g. an explicit "Refresh" button).
const _cacheUid = () => {
  try { return JSON.parse(localStorage.getItem('user') || '{}').uid || 'anon'; }
  catch { return 'anon'; }
};
const _cacheKey = (key) => `kdash:${_cacheUid()}:${key}`;

// Drop cached dashboard entries. bustCache() with no args clears ALL of the
// current user's dashboard cache; bustCache('leads','agents') clears specific keys.
export const bustCache = (...keys) => {
  try {
    if (!keys.length) {
      const prefix = `kdash:${_cacheUid()}:`;
      Object.keys(localStorage).filter(k => k.startsWith(prefix)).forEach(k => localStorage.removeItem(k));
      return;
    }
    keys.forEach(k => localStorage.removeItem(_cacheKey(k)));
  } catch { /* ignore */ }
};

// Return cached data if younger than ttl; otherwise fetch, cache, and return.
// ttl=0 (or force) always hits the network.
export const cachedGet = async (key, fetchFn, { ttl = 60000, force = false } = {}) => {
  const ck = _cacheKey(key);
  if (!force) {
    try {
      const raw = localStorage.getItem(ck);
      if (raw) {
        const { ts, data } = JSON.parse(raw);
        if (ts && (Date.now() - ts) < ttl) return data;
      }
    } catch { /* corrupt entry — fall through to a fresh fetch */ }
  }
  const data = await fetchFn();
  try { localStorage.setItem(ck, JSON.stringify({ ts: Date.now(), data })); } catch { /* quota / private mode */ }
  return data;
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
  // Journey planner: geocode origin/destination + driving route.
  route: async ({ origin, destination, from } = {}) => {
    const params = { destination: destination || '' };
    if (origin) params.origin = origin;
    if (from && from.length === 2) { params.from_lat = from[0]; params.from_lng = from[1]; }
    return (await api.get('/api/maps/route', { params })).data;
  },
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
        if (options.skill) fd.append('skill', options.skill);
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
          skill: options.skill || '',
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
      body: JSON.stringify({
        question, session_id: sessionId,
        depth: options.depth || 'standard',
        mode: options.mode || 'research',
      }),
      contentType: 'application/json',
    });
    return _postStreamWithAuth(`${API_BASE_URL}/api/research/stream`, buildBody, options);
  },

  // Hard-stop the in-flight generation for a session so the backend LLM thread
  // halts and stops billing tokens. Best-effort, fire-and-forget.
  stopGeneration: async (sessionId) => {
    if (!sessionId) return;
    try {
      await fetch(`${API_BASE_URL}/api/jarvis/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ session_id: sessionId }),
        keepalive: true,
      });
    } catch (e) {
      /* best-effort — the fetch abort already cut the client side */
    }
  },

  // Get chat history (paginated). Pass { before } (ISO cursor from a previous
  // response's next_before) to fetch older chats. Returns { chats, next_before }.
  getHistory: async ({ before = null, limit = 100 } = {}) => {
    const params = { limit };
    if (before) params.before = before;
    const response = await api.get('/api/jarvis/history', { params });
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

  // Create (or refresh) a public share link for a conversation. Returns
  // { share_id, url }. The same session always maps to the same link.
  share: async (sessionId) => {
    const response = await api.post(`/api/jarvis/share/${sessionId}`);
    return response.data;
  },

  // Revoke a previously created share link (kills the public page).
  revokeShare: async (shareId) => {
    const response = await api.delete(`/api/jarvis/share/${shareId}`);
    return response.data;
  },

  // Fetch a publicly shared conversation — NO auth, works for logged-out
  // visitors opening a /share/<id> link. Uses plain fetch so the axios auth
  // interceptor never gets in the way.
  getShared: async (shareId) => {
    const resp = await fetch(`${API_BASE_URL}/api/shared/${encodeURIComponent(shareId)}`);
    if (!resp.ok) {
      const err = new Error('shared_fetch_failed');
      err.status = resp.status;
      throw err;
    }
    return resp.json();
  },

  // Get user status
  getStatus: async () => {
    const response = await api.get('/api/jarvis/status');
    return response.data;
  },
};

// Agents API
export const agentsAPI = {
  // List agents (cached — bust on create/update/delete)
  list: async ({ force = false } = {}) => {
    return cachedGet('agents', async () => (await api.get('/api/agents/list')).data, { ttl: 120000, force });
  },

  // Create agent
  create: async (agentData) => {
    const response = await api.post('/api/agents/create', agentData);
    bustCache('agents');
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
    bustCache('agents');
    return response.data;
  },

  // Delete agent
  delete: async (agentId) => {
    const response = await api.post(`/api/agents/${agentId}/delete`);
    bustCache('agents', `logs:${agentId}`);
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

  // Get agent logs (cached per agent)
  getLogs: async (agentId, { force = false } = {}) => {
    return cachedGet(`logs:${agentId}`, async () => (await api.get(`/api/agents/${agentId}/logs`)).data, { ttl: 60000, force });
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

  // Get KB file content (eye view)
  getKBContent: async (agentId, fileId) => {
    const response = await api.get(`/api/agents/${agentId}/kb/${fileId}/content`);
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
  // List campaigns (cached — bust on create/start/stop/delete)
  list: async ({ force = false } = {}) => {
    return cachedGet('campaigns', async () => (await api.get('/api/campaigns')).data, { ttl: 45000, force });
  },

  // Create campaign
  create: async (campaignData) => {
    const response = await api.post('/api/campaigns/create', campaignData);
    bustCache('campaigns');
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
    bustCache('campaigns');
    return response.data;
  },

  // Stop/Pause campaign
  stop: async (campaignId) => {
    const response = await api.post(`/api/campaigns/${campaignId}/stop`);
    bustCache('campaigns');
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
    bustCache('campaigns');
    return response.data;
  },
};

// User API
export const userAPI = {
  // Get user profile (cached — bust on update)
  getProfile: async ({ force = false } = {}) => {
    return cachedGet('user:profile', async () => (await api.get('/api/user/profile')).data, { ttl: 300000, force });
  },

  // Update user profile
  updateProfile: async (profileData) => {
    const response = await api.put('/api/user/profile', profileData);
    bustCache('user:profile');
    return response.data;
  },

  // Get full settings doc (cached — bust on save)
  getSettings: async ({ force = false } = {}) => {
    return cachedGet('user:settings', async () => (await api.get('/api/user/settings')).data, { ttl: 300000, force });
  },

  // Save full settings doc
  saveSettings: async (settingsData) => {
    const response = await api.post('/api/user/settings', settingsData);
    bustCache('user:settings');
    return response.data;
  },

  // Built-in personas for the picker (static server-side list — cache hard)
  getPersonalities: async ({ force = false } = {}) => {
    return cachedGet('user:personalities', async () => (await api.get('/api/user/personalities')).data, { ttl: 3600000, force });
  },

  // Turn a plain-language description into a persona overlay (preview only —
  // the caller still saves it through saveSettings).
  generatePersonality: async ({ description, name }) => {
    const response = await api.post('/api/user/personality/generate', { description, name });
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

// Deck (Presentation skill) exports — the canvas sends the live deck JSON and
// gets back a PowerPoint (.pptx) or PDF blob rendered with the same theme.
export const deckAPI = {
  export: async ({ deck, format = 'pptx', title }) => {
    const response = await api.post('/api/export/deck', { deck, format, title }, {
      responseType: 'blob',
    });
    return response.data;
  },
};

// Activatable Skills catalog (composer → Tools & Capabilities → Skills).
export const skillsAPI = {
  list: async ({ force = false } = {}) => {
    return cachedGet('skills', async () => (await api.get('/api/skills')).data, { ttl: 300000, force });
  },
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

// Kautilya Computer — persistent per-session sandbox file browser
export const computerAPI = {
  listFiles: async (sessionId) => {
    const response = await api.get('/api/computer/files', { params: { session_id: sessionId } });
    return response.data;
  },
  readFile: async (sessionId, name) => {
    const response = await api.get('/api/computer/file', { params: { session_id: sessionId, name } });
    return response.data;
  },
  // The browser is per-USER (one persistent "computer"), not per-chat — no
  // session_id here on purpose, see backend routes/computer_routes.py.
  getBrowserState: async () => {
    const response = await api.get('/api/computer/browser');
    return response.data;
  },
};

// API Keys
export const keysAPI = {
  list: async ({ force = false } = {}) => {
    return cachedGet('keys', async () => (await api.get('/api/keys/list')).data, { ttl: 120000, force });
  },

  create: async (keyData) => {
    const response = await api.post('/api/keys/create', keyData);
    bustCache('keys');
    return response.data;
  },

  revoke: async (keyHash) => {
    const response = await api.post('/api/keys/revoke', { key_hash: keyHash });
    bustCache('keys');
    return response.data;
  },
};

// Telephony
export const telephonyAPI = {
  getConfig: async ({ force = false } = {}) => {
    return cachedGet('telephony:config', async () => (await api.get('/api/telephony/config')).data, { ttl: 300000, force });
  },

  saveConfig: async (config) => {
    const response = await api.post('/api/telephony/save', config);
    bustCache('telephony:config');
    return response.data;
  },

  // Ready-to-paste Vobiz Answer/Events URLs for INBOUND calls on an agent
  inboundUrl: async (agentId) => {
    const response = await api.get(`/api/telephony/inbound-url/${agentId}`);
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
  // Get billing config and user tier (cached — bust after a successful payment)
  getConfig: async ({ force = false } = {}) => {
    return cachedGet('billing:config', async () => (await api.get('/api/billing/config')).data, { ttl: 120000, force });
  },

  // Create payment order
  createOrder: async (amount, planType) => {
    const response = await api.post('/api/billing/create-order', { amount, plan_type: planType });
    return response.data;
  },

  // Verify payment
  verifyPayment: async (paymentData) => {
    const response = await api.post('/api/billing/verify-payment', paymentData);
    bustCache('billing:config', 'analytics:usage'); // tier changed → drop stale tier/usage
    return response.data;
  },

  // Recover a payment that Razorpay captured but our system missed
  reconcilePayment: async (razorpayPaymentId) => {
    const response = await api.post('/api/billing/reconcile-payment', { razorpay_payment_id: razorpayPaymentId });
    bustCache('billing:config', 'analytics:usage');
    return response.data;
  },
};

// Leads API
export const leadsAPI = {
  // List leads (cached — bust on update/delete)
  list: async ({ force = false } = {}) => {
    return cachedGet('leads', async () => (await api.get('/api/leads')).data, { ttl: 60000, force });
  },

  // Update lead
  update: async (leadId, data) => {
    const response = await api.patch(`/api/leads/${leadId}`, data);
    bustCache('leads');
    return response.data;
  },

  // Delete lead
  delete: async (leadId) => {
    const response = await api.delete(`/api/leads/${leadId}`);
    bustCache('leads');
    return response.data;
  },
};

// Analytics API (all cached — read-only dashboards)
export const analyticsAPI = {
  // Get usage analytics
  getUsage: async ({ force = false } = {}) => {
    return cachedGet('analytics:usage', async () => (await api.get('/api/analytics/usage')).data, { ttl: 120000, force });
  },

  // Get call volume
  getCallVolume: async ({ force = false } = {}) => {
    return cachedGet('analytics:call-volume', async () => (await api.get('/api/analytics/call-volume')).data, { ttl: 60000, force });
  },

  // Get trends
  getTrends: async ({ force = false } = {}) => {
    return cachedGet('analytics:trends', async () => (await api.get('/api/analytics/trends')).data, { ttl: 120000, force });
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
      // The TTS Space is single-GPU and HF throttles it (429) under concurrent
      // bursts; the backend already does a short retry, but the throttle window
      // can outlast it. A 429 response carries no audio body, so retry the whole
      // request a few times with backoff before surfacing the error.
      const BACKOFFS = [1000, 2500, 5000]; // ms
      let response;
      for (let attempt = 0; ; attempt++) {
        response = await fetch(`${baseUrl}/api/tts/revealiq/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders(),
          },
          body: JSON.stringify({ text, model, voice, speed }),
        });
        if (response.status !== 429 || attempt >= BACKOFFS.length) break;
        await new Promise((r) => setTimeout(r, BACKOFFS[attempt]));
      }
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

// STT API — RevealIQ STT Studio (Nemotron 3.5 streaming ASR on HF CPU Space).
// Always goes through the backend proxy so HF auth / rate-limit / billing apply.
export const sttAPI = {
  revealIQ: {
    // Transcribe one audio blob (a full file upload, or one live segment).
    // `blob` is a Blob/File; `language` empty = auto-detect.
    transcribe: async (blob, language = '', filename = 'audio.webm') => {
      const baseUrl = API_BASE_URL.replace(/\/+$/, '');
      const form = new FormData();
      form.append('file', blob, filename);
      if (language) form.append('language', language);
      // IMPORTANT: do NOT set Content-Type — the browser must set the
      // multipart boundary itself. getAuthHeaders() only adds auth headers.
      const res = await fetch(`${baseUrl}/api/stt/revealiq/transcribe`, {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        body: form,
      });
      if (!res.ok) {
        let msg = `Transcription error (${res.status})`;
        try { const j = await res.json(); msg = j.error || msg; } catch {}
        const err = new Error(msg);
        err.status = res.status;
        throw err;
      }
      return res.json(); // { text, duration, latency_ms }
    },

    // Space/model readiness so the UI can show a "warming up" state.
    status: async () => {
      const baseUrl = API_BASE_URL.replace(/\/+$/, '');
      try {
        const res = await fetch(`${baseUrl}/api/stt/revealiq/status`, {
          headers: { ...getAuthHeaders() },
        });
        return res.json();
      } catch {
        return { status: 'unreachable', ready: false };
      }
    },
  },
};

// Integrations API
export const integrationsAPI = {
  // Cached — bust on connect/save/disconnect so the grid reflects changes.
  list: async ({ force = false } = {}) => {
    return cachedGet('integrations', async () => (await api.get('/api/integrations')).data, { ttl: 120000, force });
  },
  save: async (provider, data) => {
    const res = await api.post(`/api/integrations/${provider}/save`, data);
    bustCache('integrations');
    return res.data;
  },
  disconnect: async (provider) => {
    const res = await api.post(`/api/integrations/${provider}/disconnect`);
    bustCache('integrations');
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
