// Thin API wrapper. All Flask endpoints are prefixed with /api and require
// a Firebase ID token in `Authorization: Bearer <token>`. Same contract as
// the legacy dashboard — we just centralise it here.
import { auth } from './firebase'

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.status = status
    this.payload = payload
  }
}

async function getToken() {
  const u = auth.currentUser
  if (!u) return null
  try { return await u.getIdToken() } catch { return null }
}

export async function api(path, opts = {}) {
  const token = await getToken()
  const headers = {
    'Accept': 'application/json',
    ...(opts.body && !(opts.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(opts.headers || {}),
  }
  let body = opts.body
  if (body && typeof body === 'object' && !(body instanceof FormData)) {
    body = JSON.stringify(body)
  }
  const resp = await fetch(path, { ...opts, headers, body })
  
  if (!resp.ok) {
    const data = await resp.json().catch(() => null)
    const msg = (data && (data.error || data.message)) || `${resp.status} ${resp.statusText}`
    throw new ApiError(msg, resp.status, data)
  }

  // Handle blob response if requested
  if (opts.responseType === 'blob') {
    return await resp.blob()
  }

  const ctype = resp.headers.get('content-type') || ''
  if (ctype.includes('application/json')) return await resp.json().catch(() => null)
  return await resp.text().catch(() => null)
}

// ----- Convenience endpoints -----
export const Agents = {
  list: () => api('/api/agents/list'),
  create: (payload) => api('/api/agents/create', { method: 'POST', body: payload }),
  update: (id, payload) => api(`/api/agents/${id}/update`, { method: 'POST', body: payload }),
  remove: (id) => api(`/api/agents/${id}/delete`, { method: 'POST' }),
  logs: (id) => api(`/api/agents/${id}/logs`),
  callOutbound: (id, payload) => api(`/api/agents/${id}/call-outbound`, { method: 'POST', body: payload }),
  chat: (id, payload, opts = {}) => api(`/api/agents/${id}/chat`, { method: 'POST', body: payload, ...opts }),
  kb: {
    list: (agentId) => api(`/api/agents/${agentId}/kb`),
    upload: (agentId, formData) => api(`/api/agents/${agentId}/kb`, { method: 'POST', body: formData }),
    addUrl: (agentId, url) => api(`/api/agents/${agentId}/kb-url`, { method: 'POST', body: { url } }),
    remove: (agentId, fileId) => api(`/api/agents/${agentId}/kb/${fileId}`, { method: 'DELETE' }),
  }
}

export const Telephony = {
  config: () => api('/api/telephony/config'),
  save: (payload) => api('/api/telephony/save', { method: 'POST', body: payload }),
}

export const Billing = {
  status: () => api('/api/billing/config'),
}

export const Analytics = {
  callVolume: (range = '12h') => api(`/api/analytics/call-volume?range=${range}`),
}

export const Campaigns = {
  list: () => api('/api/campaigns'),
  upload: (formData) => api('/api/campaigns/upload', { method: 'POST', body: formData }),
  status: (id) => api(`/api/campaigns/${id}/status`),
  start: (id) => api(`/api/campaigns/${id}/start`, { method: 'POST' }),
  pause: (id) => api(`/api/campaigns/${id}/pause`, { method: 'POST' }),
  remove: (id) => api(`/api/campaigns/${id}`, { method: 'DELETE' }),
}

export const User = {
  account: () => api('/api/user/account'),
  generateApiKey: () => api('/api/user/api-key', { method: 'POST' }),
}

export const Voice = {
  preview: (payload) => api('/api/voice/preview', { method: 'POST', body: payload, responseType: 'blob' }),
}
