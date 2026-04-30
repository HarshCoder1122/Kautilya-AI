<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bot, Plus, Search, MoreHorizontal, PhoneOutgoing, MessageSquare, Trash2 } from 'lucide-vue-next'
import { useAgents } from '@/stores/agents'
import { relativeTime } from '@/lib/format'
import AgentCreateModal from '@/components/agents/AgentCreateModal.vue'

const agents = useAgents()
const router = useRouter()
const route = useRoute()
const search = ref('')
const showCreate = ref(false)

onMounted(() => {
  if (!agents.loaded) agents.fetch().catch(() => {})
  if (route.query.new) showCreate.value = true
})

watch(() => route.query.new, (v) => { if (v) showCreate.value = true })

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return agents.items
  return agents.items.filter((a) =>
    [a.name, a.model, a.language, a.agent_type].some((f) => String(f || '').toLowerCase().includes(q))
  )
})

async function remove(a) {
  if (!confirm(`Delete agent "${a.name}"? This cannot be undone.`)) return
  try { await agents.remove(a.id) } catch (e) { alert(e.message) }
}

function open(a) { router.push(`/agents/${a.id}`) }
</script>

<template>
  <div class="space-y-5 animate-fadein">
    <header class="flex flex-wrap items-center gap-3">
      <div class="flex-1 min-w-[200px]">
        <h1 class="text-xl sm:text-2xl font-bold">Agents</h1>
        <p class="text-sm text-ink-muted">Build and manage your AI voice & chat agents.</p>
      </div>
      <div class="relative flex-1 min-w-[200px] max-w-sm">
        <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-dim" />
        <input v-model="search" placeholder="Search agents…" class="input pl-9" />
      </div>
      <button class="btn btn-primary" @click="showCreate = true">
        <Plus :size="14"/> New Agent
      </button>
    </header>

    <!-- Loading skeleton -->
    <div v-if="agents.loading && !agents.loaded" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div v-for="i in 6" :key="i" class="card p-5">
        <div class="skeleton h-10 w-10 rounded-lg mb-3"></div>
        <div class="skeleton h-4 w-3/5 mb-2"></div>
        <div class="skeleton h-3 w-2/5 mb-4"></div>
        <div class="flex gap-2"><div class="skeleton h-5 w-16 rounded-full"></div><div class="skeleton h-5 w-12 rounded-full"></div></div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="!agents.items.length" class="card empty">
      <div class="empty-icon"><Bot :size="22"/></div>
      <h3 class="text-base font-semibold text-ink">Create your first agent</h3>
      <p class="text-sm max-w-sm">Define a system prompt, pick a voice and model, link a phone number — your AI is ready to take calls.</p>
      <button class="btn btn-primary mt-3" @click="showCreate = true"><Plus :size="14"/> New Agent</button>
    </div>

    <!-- Grid -->
    <div v-else-if="filtered.length" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
      <article
        v-for="a in filtered" :key="a.id"
        class="card card-hover p-5 cursor-pointer flex flex-col gap-3 group"
        @click="open(a)"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-3 min-w-0">
            <div class="h-10 w-10 rounded-xl bg-gradient-to-br from-accent to-accent-strong text-[#00211D] font-bold flex items-center justify-center shadow-glow">
              {{ (a.name || '?')[0].toUpperCase() }}
            </div>
            <div class="min-w-0">
              <h3 class="text-sm font-semibold truncate">{{ a.name || 'Unnamed Agent' }}</h3>
              <p class="text-[11px] text-ink-muted font-mono">#{{ String(a.id || '').slice(0, 10) }}</p>
            </div>
          </div>
          <button
            class="btn-icon opacity-0 group-hover:opacity-100 transition-opacity"
            @click.stop="remove(a)"
            title="Delete"
          >
            <Trash2 :size="14"/>
          </button>
        </div>

        <p class="text-xs text-ink-muted line-clamp-2 min-h-[32px]">
          {{ a.welcome_message || a.system_prompt || 'No description.' }}
        </p>

        <div class="flex items-center flex-wrap gap-1.5 mt-auto">
          <span class="pill pill-accent">{{ a.model || 'kautilya-daily' }}</span>
          <span class="pill pill-info">{{ a.language || 'hi-IN' }}</span>
          <span class="pill">{{ a.agent_type || 'inbound' }}</span>
          <span v-if="a.call_count" class="pill"><PhoneOutgoing :size="10" class="inline mr-0.5"/>{{ a.call_count }}</span>
        </div>

        <div class="flex items-center justify-between text-[11px] text-ink-dim pt-1 border-t border-line/60 -mx-1 px-1">
          <span>Updated {{ relativeTime(a.updated_at) || '—' }}</span>
          <span class="text-accent opacity-0 group-hover:opacity-100 transition-opacity">Open studio →</span>
        </div>
      </article>
    </div>

    <!-- Filtered empty -->
    <div v-else class="card empty">
      <div class="empty-icon"><Search :size="22"/></div>
      <p class="text-sm">No agents match "{{ search }}"</p>
    </div>

    <AgentCreateModal v-if="showCreate" @close="showCreate = false; router.replace({ query: {} })" />
  </div>
</template>

<style scoped>
.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>
