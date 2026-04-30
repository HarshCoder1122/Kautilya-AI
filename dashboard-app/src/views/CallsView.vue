<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  Phone, MessageSquare, Globe, Filter, RefreshCw, Search, Eye, Download,
  PhoneCall, TrendingUp, History,
} from 'lucide-vue-next'
import { Agents } from '@/lib/api'
import { useAgents } from '@/stores/agents'
import { formatDuration, relativeTime, sentimentMeta, channelMeta } from '@/lib/format'

const agents = useAgents()
const selected = ref('all')
const filterCh = ref('all')      // all | sip | web | chat
const search = ref('')
const allLogs = ref([])
const loading = ref(false)
const detail = ref(null)

onMounted(async () => {
  if (!agents.loaded) await agents.fetch()
  await refresh()
})

watch(selected, refresh)

async function refresh() {
  loading.value = true
  try {
    const items = selected.value === 'all' ? agents.items : agents.items.filter((a) => a.id === selected.value)
    const calls = []
    await Promise.all(items.map(async (a) => {
      try {
        const data = await Agents.logs(a.id)
        ;(data?.logs || []).forEach((l) => calls.push({ ...l, _agent: a }))
      } catch {}
    }))
    calls.sort((a, b) => {
      const at = (a.timestamp || a.created_at?.seconds || 0)
      const bt = (b.timestamp || b.created_at?.seconds || 0)
      return bt - at
    })
    allLogs.value = calls
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return allLogs.value.filter((l) => {
    if (filterCh.value !== 'all') {
      const ch = String(l.channel || '').toLowerCase()
      if (filterCh.value === 'sip' && !(ch.includes('sip') || ch.includes('phone'))) return false
      if (filterCh.value === 'web' && !ch.includes('web')) return false
      if (filterCh.value === 'chat' && !ch.includes('chat')) return false
    }
    if (!q) return true
    return [l.summary, l.analysis, l.transcript, l._agent?.name, l.call_id].some((f) =>
      String(f || '').toLowerCase().includes(q)
    )
  })
})

const stats = computed(() => {
  const items = filtered.value
  const total = items.length
  const totalDur = items.reduce((s, l) => s + (Number(l.duration) || 0), 0)
  const avg = total ? Math.round(totalDur / total) : 0
  const success = total ? Math.round(items.filter((l) => l.outcome !== false).length / total * 100) : 0
  const positive = total ? Math.round(items.filter((l) => String(l.sentiment || '').toLowerCase().includes('pos')).length / total * 100) : 0
  return { total, avg, success, positive }
})

function exportCsv() {
  const rows = [['When', 'Agent', 'Channel', 'Duration', 'Sentiment', 'Summary']]
  filtered.value.forEach((l) => {
    rows.push([
      relativeTime(l.created_at || l.timestamp),
      l._agent?.name || '',
      l.channel || '',
      formatDuration(l.duration),
      l.sentiment || '',
      (l.summary || l.analysis || '').replace(/\n/g, ' '),
    ])
  })
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'kautilya-calls.csv'
  a.click()
}

function chTone(l) {
  const ch = String(l.channel || '').toLowerCase()
  if (ch.includes('sip') || ch.includes('phone')) return { bg: 'bg-accent/10 text-accent', icon: Phone }
  if (ch.includes('chat')) return { bg: 'bg-info/10 text-info', icon: MessageSquare }
  return { bg: 'bg-info/10 text-info', icon: Globe }
}
</script>

<template>
  <div class="space-y-5 animate-fadein">
    <header class="flex flex-wrap items-center gap-3">
      <div class="flex-1 min-w-[200px]">
        <h1 class="text-xl sm:text-2xl font-bold">Recent Calls</h1>
        <p class="text-sm text-ink-muted">Every conversation across voice, SIP and chat — filterable and exportable.</p>
      </div>
      <button class="btn btn-ghost btn-sm" @click="refresh"><RefreshCw :size="14" :class="loading && 'animate-spin'"/> Refresh</button>
      <button class="btn btn-ghost btn-sm" @click="exportCsv"><Download :size="14"/> Export CSV</button>
    </header>

    <!-- Stats -->
    <section class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      <div class="stat">
        <div class="flex justify-between items-start"><span class="stat-label">Total</span><PhoneCall :size="16" class="text-accent"/></div>
        <div class="stat-value">{{ stats.total }}</div>
      </div>
      <div class="stat">
        <div class="flex justify-between items-start"><span class="stat-label">Avg Duration</span><History :size="16" class="text-info"/></div>
        <div class="stat-value">{{ formatDuration(stats.avg) }}</div>
      </div>
      <div class="stat">
        <div class="flex justify-between items-start"><span class="stat-label">Success</span><TrendingUp :size="16" class="text-success"/></div>
        <div class="stat-value">{{ stats.success }}%</div>
      </div>
      <div class="stat">
        <div class="flex justify-between items-start"><span class="stat-label">Positive Sentiment</span><TrendingUp :size="16" class="text-success"/></div>
        <div class="stat-value">{{ stats.positive }}%</div>
      </div>
    </section>

    <!-- Filters -->
    <div class="card p-3 sm:p-4 flex flex-wrap items-center gap-2">
      <select v-model="selected" class="select max-w-[220px]">
        <option value="all">All agents</option>
        <option v-for="a in agents.items" :key="a.id" :value="a.id">{{ a.name }}</option>
      </select>

      <div class="flex items-center gap-1 p-0.5 bg-bg-subtle rounded-lg border border-line">
        <button v-for="c in [{k:'all',l:'All'},{k:'sip',l:'Phone'},{k:'web',l:'Web'},{k:'chat',l:'Chat'}]"
          :key="c.k" class="px-2.5 py-1 text-xs rounded-md transition-colors"
          :class="filterCh === c.k ? 'bg-bg-card text-ink' : 'text-ink-muted hover:text-ink'"
          @click="filterCh = c.k">
          {{ c.l }}
        </button>
      </div>

      <div class="relative flex-1 min-w-[200px]">
        <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-dim"/>
        <input v-model="search" placeholder="Search summary, agent, call id…" class="input pl-9 h-9"/>
      </div>
    </div>

    <!-- List -->
    <div v-if="loading && !filtered.length" class="card p-2">
      <div v-for="i in 5" :key="i" class="p-4 border-b border-line last:border-0">
        <div class="flex gap-3 items-center">
          <div class="skeleton h-10 w-10 rounded-lg"/>
          <div class="flex-1"><div class="skeleton h-3 w-2/5 mb-2"/><div class="skeleton h-3 w-1/5"/></div>
          <div class="skeleton h-3 w-12"/>
        </div>
      </div>
    </div>
    <div v-else-if="!filtered.length" class="card empty">
      <div class="empty-icon"><History :size="22"/></div>
      <h3 class="text-base font-semibold text-ink">No calls match these filters</h3>
      <p class="text-sm">Try a different agent, channel, or clear the search.</p>
    </div>
    <div v-else class="card divide-y divide-line">
      <article v-for="(l, i) in filtered" :key="i"
        class="p-4 sm:p-5 grid grid-cols-[40px,1fr,auto,auto] sm:grid-cols-[44px,1fr,auto,auto,auto] gap-3 items-center hover:bg-white/[0.02] cursor-pointer"
        @click="detail = l">
        <div class="h-10 w-10 sm:h-11 sm:w-11 rounded-lg flex items-center justify-center" :class="chTone(l).bg">
          <component :is="chTone(l).icon" :size="16"/>
        </div>
        <div class="min-w-0">
          <p class="text-sm font-medium truncate">{{ l.summary || l.analysis || 'Call completed.' }}</p>
          <div class="flex items-center gap-1.5 mt-1 flex-wrap">
            <span class="pill" :class="sentimentMeta(l.sentiment).cls">{{ sentimentMeta(l.sentiment).label }}</span>
            <span class="pill pill-mono">{{ l.model || 'kautilya-daily' }}</span>
            <span class="text-[11px] text-ink-dim font-mono hidden sm:inline">#{{ String(l.call_id || '').slice(0, 10) }}</span>
            <span class="text-[11px] text-ink-muted hidden sm:inline">· {{ l._agent?.name || 'Unknown' }}</span>
          </div>
        </div>
        <div class="text-right">
          <p class="font-mono text-sm">{{ formatDuration(l.duration) }}</p>
        </div>
        <div class="text-right hidden sm:block">
          <p class="text-[11px] text-ink-muted whitespace-nowrap">{{ relativeTime(l.created_at || l.timestamp) }}</p>
        </div>
        <button class="btn-icon hidden sm:inline-flex" @click.stop="detail = l"><Eye :size="14"/></button>
      </article>
    </div>

    <!-- Detail drawer -->
    <transition name="fade">
      <div v-if="detail">
        <div class="scrim" @click="detail = null"></div>
        <aside class="drawer">
          <div class="flex items-center justify-between px-5 py-4 border-b border-line">
            <div>
              <p class="text-xs text-ink-muted">Call detail</p>
              <h2 class="font-semibold">{{ detail._agent?.name || 'Unknown agent' }}</h2>
            </div>
            <button class="btn-icon" @click="detail = null">✕</button>
          </div>
          <div class="flex-1 overflow-y-auto px-5 py-5 space-y-5">
            <div class="grid grid-cols-3 gap-3">
              <div class="card p-3"><p class="text-[10px] text-ink-muted uppercase">Duration</p><p class="font-mono">{{ formatDuration(detail.duration) }}</p></div>
              <div class="card p-3"><p class="text-[10px] text-ink-muted uppercase">Sentiment</p><span class="pill" :class="sentimentMeta(detail.sentiment).cls">{{ sentimentMeta(detail.sentiment).label }}</span></div>
              <div class="card p-3"><p class="text-[10px] text-ink-muted uppercase">Channel</p><p class="text-sm">{{ detail.channel || 'web' }}</p></div>
            </div>

            <div>
              <h3 class="text-xs uppercase tracking-wider text-ink-muted mb-2">Summary</h3>
              <p class="text-sm leading-relaxed">{{ detail.summary || detail.analysis || 'No summary available.' }}</p>
            </div>

            <div v-if="detail.topics?.length">
              <h3 class="text-xs uppercase tracking-wider text-ink-muted mb-2">Topics</h3>
              <div class="flex gap-1.5 flex-wrap">
                <span v-for="t in detail.topics" :key="t" class="pill">{{ t }}</span>
              </div>
            </div>

            <div v-if="detail.turns?.length || detail.transcript">
              <h3 class="text-xs uppercase tracking-wider text-ink-muted mb-2">Transcript</h3>
              <div class="rounded-xl2 border border-line bg-bg-card p-3 max-h-[420px] overflow-y-auto flex flex-col gap-2">
                <template v-if="detail.turns?.length">
                  <div v-for="(t, i) in detail.turns" :key="i"
                    class="px-3 py-2 rounded-xl2 max-w-[88%] text-sm leading-relaxed"
                    :class="t.role === 'user' ? 'bg-info/10 border border-info/20 self-end' : 'bg-accent-soft border border-accent/20 self-start'">
                    <p class="text-[10px] uppercase tracking-wider opacity-60 mb-1">{{ t.role }}</p>
                    {{ t.content }}
                  </div>
                </template>
                <pre v-else class="whitespace-pre-wrap text-xs text-ink-muted font-mono">{{ detail.transcript }}</pre>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </transition>
  </div>
</template>
