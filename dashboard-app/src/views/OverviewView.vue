<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  TrendingUp, TrendingDown, PhoneCall, Bot, Activity, Sparkles,
  ArrowUpRight, MessageSquare, Phone, Globe,
} from 'lucide-vue-next'
import { useAgents } from '@/stores/agents'
import { useAuth } from '@/stores/auth'
import { relativeTime } from '@/lib/format'
import { Analytics } from '@/lib/api'

const auth = useAuth()
const agents = useAgents()
const router = useRouter()

const timeRange = ref('12h')
const volData = ref(null)

onMounted(() => {
  if (!agents.loaded && !agents.loading) agents.fetch().catch(() => {})
  loadAnalytics()
})

watch(timeRange, loadAnalytics)

async function loadAnalytics() {
  try {
    volData.value = await Analytics.callVolume(timeRange.value)
  } catch (e) {
    console.error("Failed to load analytics:", e)
  }
}

const totalAgents = computed(() => agents.items.length)
const activeAgents = computed(() => agents.items.filter((a) => a.status !== 'inactive').length)

// Real sparkline based on analytics data
const sparkPoints = computed(() => {
  if (!volData.value || !volData.value.buckets) return '0,40 200,40'
  const buckets = volData.value.buckets
  const counts = buckets.map(b => b.count)
  const max = Math.max(...counts, 1) // prevent div by zero
  const w = 200, h = 40
  return counts.map((v, i) => `${(i / (counts.length - 1)) * w},${h - (v / max) * (h - 4) - 2}`).join(' ')
})

const chartLabels = computed(() => {
  if (!volData.value || !volData.value.buckets) return []
  const buckets = volData.value.buckets
  // Take 4 evenly spaced labels
  if (buckets.length <= 4) return buckets.map(b => b.label)
  const step = Math.floor(buckets.length / 4)
  return [
    buckets[0].label,
    buckets[step].label,
    buckets[step*2].label,
    buckets[buckets.length - 1].label
  ]
})

const firstName = computed(() => (auth.displayName || '').split(' ')[0] || 'there')

const stats = computed(() => ([
  { label: 'Active Agents', value: activeAgents.value, delta: '0', up: true, icon: Bot, accent: 'text-accent' },
  { label: 'Total Calls', value: volData.value?.total_calls || 0, delta: '0', up: true, icon: PhoneCall, accent: 'text-info' },
  { label: 'Avg. Sentiment', value: (volData.value?.avg_sentiment || 0) + '%', delta: '0', up: true, icon: Sparkles, accent: 'text-success' },
  { label: 'Failed Calls', value: volData.value?.failed_calls || 0, delta: '0', up: false, icon: Activity, accent: 'text-warning' },
]))
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <!-- Greeting -->
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Welcome back</p>
        <h1 class="text-2xl sm:text-3xl font-bold">Hello, {{ firstName }} 👋</h1>
        <p class="text-sm text-ink-muted mt-1">Here's what's happening across your agents today.</p>
      </div>
      <div class="flex items-center gap-2">
        <button class="btn btn-ghost btn-sm" @click="agents.fetch(true)">
          <Activity :size="14"/> Refresh
        </button>
        <button class="btn btn-primary btn-sm" @click="router.push('/agents?new=1')">
          <Bot :size="14"/> New Agent
        </button>
      </div>
    </header>

    <!-- Stat grid -->
    <section class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
      <div v-for="s in stats" :key="s.label" class="stat card-hover">
        <div class="flex items-start justify-between">
          <span class="stat-label">{{ s.label }}</span>
          <component :is="s.icon" :size="16" :class="s.accent"/>
        </div>
        <div class="stat-value">{{ s.value }}</div>
        <div class="stat-delta" :class="s.up ? 'up' : 'down'">
          <component :is="s.up ? TrendingUp : TrendingDown" :size="12" />
          <span>{{ s.delta }}</span>
          <span class="text-ink-dim font-normal ml-1">vs last 7d</span>
        </div>
      </div>
    </section>

    <!-- Big chart card + Recent activity -->
    <section class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div class="card lg:col-span-2 p-5 sm:p-6">
        <div class="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <h2 class="text-base font-semibold">Call Volume</h2>
            <p class="text-xs text-ink-muted mt-0.5">Last {{ timeRange }} · all channels</p>
          </div>
          <div class="flex items-center gap-1 p-0.5 bg-bg-subtle rounded-lg border border-line">
            <button @click="timeRange = '12h'" :class="timeRange === '12h' ? 'bg-bg-card text-ink shadow-sm' : 'text-ink-muted hover:text-ink'" class="px-2.5 py-1 text-xs rounded-md transition-colors">12h</button>
            <button @click="timeRange = '7d'" :class="timeRange === '7d' ? 'bg-bg-card text-ink shadow-sm' : 'text-ink-muted hover:text-ink'" class="px-2.5 py-1 text-xs rounded-md transition-colors">7d</button>
            <button @click="timeRange = '30d'" :class="timeRange === '30d' ? 'bg-bg-card text-ink shadow-sm' : 'text-ink-muted hover:text-ink'" class="px-2.5 py-1 text-xs rounded-md transition-colors">30d</button>
          </div>
        </div>

        <div class="relative h-44">
          <svg viewBox="0 0 200 40" preserveAspectRatio="none" class="w-full h-full">
            <defs>
              <linearGradient id="sparkFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="#00E6CC" stop-opacity="0.35"/>
                <stop offset="100%" stop-color="#00E6CC" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <polyline :points="sparkPoints" fill="none" stroke="#00E6CC" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
            <polygon :points="`0,40 ${sparkPoints} 200,40`" fill="url(#sparkFill)"/>
          </svg>
          <div class="absolute bottom-0 left-0 right-0 flex justify-between text-[10px] text-ink-dim font-mono">
            <span v-for="(lbl, idx) in chartLabels" :key="idx">{{ lbl }}</span>
          </div>
        </div>
      </div>

      <div class="card p-5 sm:p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold">Live Status</h2>
          <span class="pill pill-success"><span class="pulse-dot mr-1"></span>Online</span>
        </div>

        <ul class="space-y-3">
          <li class="flex items-center gap-3">
            <div class="h-9 w-9 rounded-lg bg-accent-soft text-accent flex items-center justify-center"><Phone :size="16"/></div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium">SIP Trunk</p>
              <p class="text-xs text-ink-muted">Vobiz · LiveKit ready</p>
            </div>
            <span class="pill pill-success">Healthy</span>
          </li>
          <li class="flex items-center gap-3">
            <div class="h-9 w-9 rounded-lg bg-info/10 text-info flex items-center justify-center"><Globe :size="16"/></div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium">Realtime LLM</p>
              <p class="text-xs text-ink-muted">Gemini Live · 3.1 flash</p>
            </div>
            <span class="pill pill-success">Healthy</span>
          </li>
          <li class="flex items-center gap-3">
            <div class="h-9 w-9 rounded-lg bg-info/10 text-info flex items-center justify-center"><MessageSquare :size="16"/></div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium">Post-call NIM</p>
              <p class="text-xs text-ink-muted">Nemotron 120B · summary</p>
            </div>
            <span class="pill pill-success">Healthy</span>
          </li>
        </ul>
      </div>
    </section>

    <!-- Agents preview -->
    <section class="card overflow-hidden">
      <div class="flex items-center justify-between px-5 sm:px-6 py-4 border-b border-line">
        <div>
          <h2 class="text-base font-semibold">Your Agents</h2>
          <p class="text-xs text-ink-muted mt-0.5">{{ totalAgents }} total · click to open studio</p>
        </div>
        <button class="btn btn-ghost btn-sm" @click="router.push('/agents')">
          View all <ArrowUpRight :size="14"/>
        </button>
      </div>

      <div v-if="agents.loading" class="p-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div v-for="i in 3" :key="i" class="skeleton h-24"></div>
      </div>
      <div v-else-if="!totalAgents" class="empty">
        <div class="empty-icon"><Bot :size="22"/></div>
        <h3 class="text-base font-semibold text-ink">No agents yet</h3>
        <p class="text-sm">Create your first AI agent to start handling calls and chats.</p>
        <button class="btn btn-primary mt-2" @click="router.push('/agents?new=1')">
          <Bot :size="14"/> Create your first agent
        </button>
      </div>
      <div v-else class="p-4 sm:p-5 grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <RouterLink
          v-for="a in agents.items.slice(0, 6)" :key="a.id"
          :to="`/agents/${a.id}`"
          class="card card-hover p-4 flex flex-col gap-2.5"
        >
          <div class="flex items-center gap-2.5">
            <div class="h-9 w-9 rounded-lg bg-gradient-to-br from-accent to-accent-strong text-[#00211D] font-bold flex items-center justify-center">
              {{ (a.name || '?')[0].toUpperCase() }}
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold truncate">{{ a.name || 'Unnamed Agent' }}</p>
              <p class="text-[11px] text-ink-muted truncate">{{ a.model || 'kautilya-daily' }} · {{ a.language || 'hi-IN' }}</p>
            </div>
          </div>
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="pill pill-accent">{{ a.call_count || 0 }} calls</span>
            <span class="pill pill-info">{{ a.agent_type || 'inbound' }}</span>
            <span class="pill" v-if="a.status === 'active'">{{ relativeTime(a.updated_at) || 'live' }}</span>
          </div>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
