import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL 
  || (window.location.hostname === 'localhost' ? 'http://localhost:5000' : window.location.origin);

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

// Add Firebase token to requests if available
api.interceptors.request.use(async (config) => {
  const authHeaders = getAuthHeaders();
  Object.assign(config.headers, authHeaders);
  return config;
}, (error) => {
  return Promise.reject(error);
});

// On 401, force-refresh the Firebase token and retry once
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retried) {
      original._retried = true;
      try {
        const { getAuthInstance } = await import('./firebase.js');
        const auth = getAuthInstance();
        const user = auth.currentUser;
        if (user) {
          const token = await user.getIdToken(true);
          localStorage.setItem('firebase_token', token);
          original.headers['Authorization'] = `Bearer ${token}`;
          return api(original);
        }
      } catch (e) {
        console.warn('[Auth] Token refresh on 401 failed:', e);
      }
    }
    return Promise.reject(error);
  }
);

// Chat API
export const chatAPI = {
  // Stream chat message
  streamMessage: async (message, sessionId = null, model = 'auto', files = [], options = {}) => {
    let body;
    let headers = {
      ...getAuthHeaders(),
    };

    if (files && files.length > 0) {
      // Use FormData if files are present
      body = new FormData();
      body.append('message', message);
      if (sessionId) body.append('session_id', sessionId);
      body.append('model', model);
      if (options.maxThinking) body.append('max_thinking', 'true');
      files.forEach(file => body.append('files', file));
      // Fetch will automatically set the correct boundary for FormData
    } else {
      // Use JSON if no files
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify({
        message,
        session_id: sessionId,
        model,
        max_thinking: !!options.maxThinking,
      });
    }

    const response = await fetch(`${API_BASE_URL}/api/jarvis/stream`, {
      method: 'POST',
      headers,
      body,
    });
    return response;
  },

  // Stream deep research; this hits the backend research pipeline
  // so SerpAPI/source gathering is actually used.
  streamResearch: async (question) => {
    const response = await fetch(`${API_BASE_URL}/api/research/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ question }),
    });
    return response;
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
    const response = await api.post(`/api/agents/${resolvedAgentId}/call-outbound`, {
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
  }
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
    synthesize: async (text, model = 'kokoro-en', voice = 'af_heart', speed = 1.0) => {
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

    stream: async (text, model = 'kokoro-en', voice = 'af_heart', speed = 1.0) => {
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
  connectOAuth: async (provider) => {
    const res = await api.get(`/api/integrations/${provider}/connect`);
    return res.data;
  },
};

export default api;
