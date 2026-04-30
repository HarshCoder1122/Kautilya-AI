// Format helpers used across views.
export function formatDuration(seconds) {
  const t = Math.max(0, Math.round(Number(seconds) || 0))
  const m = Math.floor(t / 60)
  const s = t % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function relativeTime(input) {
  const d = toDate(input)
  if (!d) return ''
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`
  return d.toLocaleDateString()
}

export function toDate(raw) {
  if (!raw) return null
  if (raw instanceof Date) return raw
  if (typeof raw === 'object' && typeof raw.seconds === 'number') {
    return new Date(raw.seconds * 1000)
  }
  if (typeof raw === 'number') return new Date(raw > 1e12 ? raw : raw * 1000)
  if (typeof raw === 'string') {
    const n = Number(raw)
    if (!Number.isNaN(n)) return new Date(n > 1e12 ? n : n * 1000)
    const p = new Date(raw)
    if (!Number.isNaN(p.getTime())) return p
  }
  return null
}

export function sentimentMeta(raw) {
  const v = typeof raw === 'string' ? raw.toLowerCase() : ''
  if (v.includes('pos')) return { label: 'Positive', cls: 'pill-success', icon: 'smile' }
  if (v.includes('neg')) return { label: 'Negative', cls: 'pill-danger', icon: 'frown' }
  return { label: 'Neutral', cls: 'pill-info', icon: 'meh' }
}

export function channelMeta(log) {
  const ch = String(log?.channel || log?.type || '').toLowerCase()
  if (ch.includes('chat')) return { label: 'Chat', icon: 'message-square', tone: 'pill-info' }
  if (ch.includes('sip') || ch.includes('phone')) return { label: 'Phone', icon: 'phone-call', tone: 'pill-accent' }
  return { label: 'Web', icon: 'globe', tone: 'pill-info' }
}

export function initials(name = '') {
  const parts = String(name).trim().split(/\s+/).slice(0, 2)
  return parts.map((p) => p[0] || '').join('').toUpperCase() || 'U'
}
