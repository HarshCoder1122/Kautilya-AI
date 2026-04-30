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
  const ctype = resp.headers.get('content-type') || ''
  let data = null
  if (ctype.includes('application/json')) data = await resp.json().catch(() => null)
  else data = await resp.text().catch(() => null)
  if (!resp.ok) {
    const msg = (data && (data.error || data.message)) || `${resp.status} ${resp.statusText}`
    throw new ApiError(msg, resp.status, data)
  }
  return data
}

// ----- Convenience endpoints -----
export const Agents = {
  list: () => api('/api/agents/list'),
  create: (payload) => api('/api/agents/create', { method: 'POST', body: payload }),
  update: (id, payload) => api(`/api/agents/${id}/update`, { method: 'POST', body: payload }),
  remove: (id) => api(`/api/agents/${id}/delete`, { method: 'POST' }),
  logs: (id) => api(`/api/agents/${id}/logs`),
  callOutbound: (id, payload) => api(`/api/agents/${id}/call-outbound`, { method: 'POST', body: payload }),
}

export const Telephony = {
  config: () => api('/api/telephony/config'),
  save: (payload) => api('/api/telephony/save', { method: 'POST', body: payload }),
}

export const Billing = {
  status: () => api('/api/billing/status'),
}
