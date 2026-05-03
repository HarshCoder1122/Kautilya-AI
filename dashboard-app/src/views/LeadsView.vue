<script setup>
import { ref, computed, onMounted } from 'vue'
import { Users, RefreshCw, Search, Filter, Trash2, Mail, Phone, Loader2 } from 'lucide-vue-next'
import { api } from '@/lib/api'

const leads = ref([])
const loading = ref(false)
const search = ref('')
const filter = ref('all')   // all | new | contacted | qualified | lost
const err = ref(null)

async function load() {
  loading.value = true; err.value = null
  try {
    const d = await api('/api/leads')
    leads.value = d.leads || []
  } catch (e) { err.value = e.message }
  finally { loading.value = false }
}
onMounted(load)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return leads.value.filter(l => {
    if (filter.value !== 'all' && (l.status || 'new') !== filter.value) return false
    if (!q) return true
    return ['name','email','phone','message','source','agent_id']
      .some(k => (l[k] || '').toLowerCase().includes(q))
  })
})

const stats = computed(() => ({
  total: leads.value.length,
  new: leads.value.filter(l => (l.status||'new') === 'new').length,
  contacted: leads.value.filter(l => l.status === 'contacted').length,
  qualified: leads.value.filter(l => l.status === 'qualified').length,
  lost: leads.value.filter(l => l.status === 'lost').length,
}))

async function setStatus(lead, status) {
  try {
    await api(`/api/leads/${lead.id}`, { method: 'PATCH', body: { status } })
    lead.status = status
  } catch (e) { alert(e.message) }
}

async function remove(lead) {
  if (!confirm('Delete this lead?')) return
  try {
    await api(`/api/leads/${lead.id}`, { method: 'DELETE' })
    leads.value = leads.value.filter(l => l.id !== lead.id)
  } catch (e) { alert(e.message) }
}

function fmtDate(d) {
  if (!d) return '—'
  try { return new Date(d).toLocaleString() } catch { return String(d) }
}

const STATUS_STYLES = {
  new:       'bg-amber-500/10 text-amber-400 border-amber-500/30',
  contacted: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  qualified: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  lost:      'bg-rose-500/10 text-rose-400 border-rose-500/30',
}
</script>

<template>
  <div class="space-y-5 animate-fadein">
    <header class="flex items-end justify-between gap-3 flex-wrap">
      <div>
        <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Pipeline</p>
        <h1 class="text-2xl sm:text-3xl font-bold">Leads</h1>
        <p class="text-sm text-ink-muted mt-1">Contacts captured by your agents — web widget, voice calls, and chat.</p>
      </div>
      <button class="btn btn-ghost btn-sm" @click="load" :disabled="loading">
        <Loader2 v-if="loading" :size="14" class="animate-spin"/>
        <RefreshCw v-else :size="14"/>
        Refresh
      </button>
    </header>

    <section class="grid grid-cols-2 md:grid-cols-5 gap-3">
      <button v-for="(v,k) in stats" :key="k"
              class="card p-3 text-left transition-colors"
              :class="filter === k || (k === 'total' && filter === 'all') ? 'ring-1 ring-accent/40' : ''"
              @click="filter = k === 'total' ? 'all' : k">
        <div class="text-xs text-ink-muted uppercase tracking-wider">{{ k }}</div>
        <div class="text-xl font-bold mt-0.5">{{ v }}</div>
      </button>
    </section>

    <div class="flex items-center gap-2">
      <div class="relative flex-1 max-w-md">
        <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-dim"/>
        <input v-model="search" class="input pl-9 w-full" placeholder="Search name / email / message…"/>
      </div>
    </div>

    <div v-if="err" class="card p-3 border border-red-500/30 bg-red-500/5 text-red-400 text-sm">{{ err }}</div>

    <div v-if="!loading && !filtered.length" class="card empty">
      <div class="empty-icon"><Users :size="22"/></div>
      <h3 class="text-base font-semibold text-ink">No leads yet</h3>
      <p class="text-sm">Leads captured by your web-embed agents or live conversations will appear here.</p>
    </div>

    <div v-else class="card overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-xs uppercase tracking-wider text-ink-dim border-b border-line">
            <th class="py-3 px-4">Contact</th>
            <th class="py-3 px-4 hidden md:table-cell">Message</th>
            <th class="py-3 px-4 hidden sm:table-cell">Source</th>
            <th class="py-3 px-4">Status</th>
            <th class="py-3 px-4 hidden lg:table-cell">Captured</th>
            <th class="py-3 px-4"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in filtered" :key="l.id" class="border-b border-line/70 hover:bg-white/[.02]">
            <td class="py-3 px-4">
              <div class="font-medium">{{ l.name || '(no name)' }}</div>
              <div class="flex items-center gap-2 text-xs text-ink-muted mt-0.5">
                <a v-if="l.email" :href="`mailto:${l.email}`" class="inline-flex items-center gap-1 hover:text-accent">
                  <Mail :size="11"/>{{ l.email }}
                </a>
                <a v-if="l.phone" :href="`tel:${l.phone}`" class="inline-flex items-center gap-1 hover:text-accent">
                  <Phone :size="11"/>{{ l.phone }}
                </a>
              </div>
            </td>
            <td class="py-3 px-4 hidden md:table-cell max-w-xs">
              <div class="text-xs text-ink-muted truncate">{{ l.message || '—' }}</div>
            </td>
            <td class="py-3 px-4 hidden sm:table-cell">
              <span class="text-xs text-ink-muted truncate block max-w-[140px]">{{ l.source || 'embed' }}</span>
            </td>
            <td class="py-3 px-4">
              <select :value="l.status || 'new'" @change="setStatus(l, $event.target.value)"
                      class="px-2 py-1 rounded-full text-xs border"
                      :class="STATUS_STYLES[l.status || 'new']">
                <option value="new">New</option>
                <option value="contacted">Contacted</option>
                <option value="qualified">Qualified</option>
                <option value="lost">Lost</option>
              </select>
            </td>
            <td class="py-3 px-4 hidden lg:table-cell text-xs text-ink-muted">{{ fmtDate(l.created_at) }}</td>
            <td class="py-3 px-4 text-right">
              <button class="btn-icon text-ink-muted hover:text-red-400" @click="remove(l)" title="Delete">
                <Trash2 :size="14"/>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.input {
  padding: 9px 12px 9px 32px; border-radius: 10px;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.09);
  color: inherit; font-size: 14px; outline: none;
}
.input:focus { border-color: var(--accent, #FF6D3F); }
</style>
