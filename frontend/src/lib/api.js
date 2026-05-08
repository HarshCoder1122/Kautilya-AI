import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add Firebase token to requests if available
api.interceptors.request.use(async (config) => {
  const token = localStorage.getItem('firebase_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Chat API
export const chatAPI = {
  // Stream chat message
  streamMessage: async (message, sessionId = null, model = 'daily') => {
    const response = await fetch(`${API_BASE_URL}/api/jarvis/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('firebase_token')}`,
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        model,
      }),
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
        'Authorization': `Bearer ${localStorage.getItem('firebase_token')}`,
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

// Artifacts API (if available)
export const artifactsAPI = {
  // List artifacts
  list: async () => {
    const response = await api.get('/api/artifacts');
    return response.data;
  },

  // Get artifact
  get: async (artifactId) => {
    const response = await api.get(`/api/artifacts/${artifactId}`);
    return response.data;
  },

  // Create artifact
  create: async (artifactData) => {
    const response = await api.post('/api/artifacts', artifactData);
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

    getVoices: (model) => {
      if (model === 'kokoro-en') {
        return ['af_heart', 'af_bella', 'af_nicole', 'af_sky', 'am_adam', 'am_michael'];
      } else if (model === 'kokoro-hi') {
        return ['hf_alpha', 'hf_beta'];
      }
      return [];
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

export default api;
