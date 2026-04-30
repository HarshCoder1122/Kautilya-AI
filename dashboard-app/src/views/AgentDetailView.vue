<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Save, Loader2, PhoneOutgoing, BookOpen, Settings as SettingsIcon,
  History, Sparkles, Volume2, Globe, Bot, Trash2,
} from 'lucide-vue-next'
import { Agents } from '@/lib/api'
import { useAgents } from '@/stores/agents'
import { formatDuration, relativeTime, sentimentMeta, channelMeta } from '@/lib/format'

const route = useRoute()
const router = useRouter()
const agentsStore = useAgents()

const id = computed(() => route.params.id)
const tab = ref('config')   // config | knowledge | calls | settings
const agent = ref(null)
const loading = ref(true)
const saving = ref(false)
const err = ref('')

const logs = ref([])
const logsLoading = ref(false)

async function load() {
  loading.value = true
  err.value = ''
  try {
    if (!agentsStore.loaded) await agentsStore.fetch()
    const found = agentsStore.byId(id.value)
    agent.value = found ? { ...found } : null
    if (!agent.value) err.value = 'Agent not found.'
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const data = await Agents.logs(id.value)
    logs.value = data?.logs || []
  } catch { logs.value = [] }
  finally { logsLoading.value = false }
}

onMounted(load)
watch(() => id.value, load)
watch(tab, (t) => { if (t === 'calls' && !logs.value.length) loadLogs() })

async function save() {
  if (!agent.value) return
  saving.value = true; err.value = ''
  try {
    await agentsStore.update(id.value, agent.value)
    // Re-pull from store to refresh updated_at etc.
    const found = agentsStore.byId(id.value)
    if (found) agent.value = { ...found }
  } catch (e) { err.value = e.message }
  finally { saving.value = false }
}

async function remove() {
  if (!confirm(`Delete agent "${agent.value?.name}"? This cannot be undone.`)) return
  try {
    await agentsStore.remove(id.value)
    router.replace('/agents')
  } catch (e) { alert(e.message) }
}

const TABS = [
  { id: 'config', label: 'Configuration', icon: Bot },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen },
  { id: 'calls', label: 'Recent Calls', icon: History },
  { id: 'settings', label: 'Advanced', icon: SettingsIcon },
]
</script>

<template>
  <div class="space-y-5 animate-fadein">
    <header class="flex items-center gap-3">
      <button class="btn-icon" @click="router.push('/agents')"><ArrowLeft :size="16"/></button>
      <div class="flex-1 min-w-0">
        <p class="text-xs text-ink-muted">Agents / Studio</p>
        <h1 class="text-xl font-semibold truncate">{{ agent?.name || 'Loading…' }}</h1>
      </div>
      <button class="btn btn-ghost btn-sm" @click="remove" v-if="agent">
        <Trash2 :size="14"/> Delete
      </button>
      <button class="btn btn-primary" @click="save" :disabled="saving || !agent">
        <Loader2 v-if="saving" :size="14" class="animate-spin"/>
        <Save v-else :size="14"/>
        {{ saving ? 'Saving…' : 'Save changes' }}
      </button>
    </header>

    <div v-if="loading" class="space-y-3">
      <div class="skeleton h-10 w-72"></div>
      <div class="skeleton h-44 w-full"></div>
    </div>

    <div v-else-if="!agent" class="card empty">
      <p>{{ err || 'Agent not found.' }}</p>
      <button class="btn btn-ghost" @click="router.push('/agents')">Back to agents</button>
    </div>

    <template v-else>
      <!-- Tabs -->
      <nav class="tabs">
        <button v-for="t in TABS" :key="t.id"
          class="tab" :class="{ active: tab === t.id }" @click="tab = t.id">
          <component :is="t.icon" :size="14"/>
          {{ t.label }}
        </button>
      </nav>

      <!-- ===== Configuration tab ===== -->
      <section v-if="tab === 'config'" class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="card p-5 sm:p-6 lg:col-span-2 space-y-5">
          <div>
            <label class="label">Agent name</label>
            <input v-model="agent.name" class="input" />
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="label"><Globe :size="11" class="inline mr-1"/>Language</label>
              <select v-model="agent.language" class="select">
                <option value="hi-IN">Hindi (India)</option>
                <option value="en-IN">English (India)</option>
                <option value="en-US">English (US)</option>
                <option value="mr-IN">Marathi</option>
                <option value="ta-IN">Tamil</option>
                <option value="te-IN">Telugu</option>
                <option value="bn-IN">Bengali</option>
              </select>
            </div>
            <div>
              <label class="label"><Sparkles :size="11" class="inline mr-1"/>Model</label>
              <select v-model="agent.model" class="select">
                <option value="kautilya-daily">Kautilya Daily (Sarvam pipeline)</option>
                <option value="gemini-flash-live">Gemini Flash Live</option>
              </select>
            </div>
          </div>

          <div>
            <label class="label">Welcome message</label>
            <input v-model="agent.welcome_message" class="input" placeholder="What the agent says first" />
          </div>

          <div>
            <label class="label">System prompt</label>
            <textarea v-model="agent.system_prompt" class="textarea" rows="10" placeholder="Describe the agent's role, personality and tasks…"></textarea>
            <p class="help">Tip: be specific about the agent's persona, the goals of the call, and edge cases (e.g. "if the customer asks for refund, transfer to human").</p>
          </div>
        </div>

        <aside class="space-y-4">
          <div class="card p-5">
            <h3 class="text-sm font-semibold mb-3">Voice</h3>
            <div class="flex items-center gap-3">
              <div class="h-10 w-10 rounded-lg bg-accent-soft text-accent flex items-center justify-center"><Volume2 :size="16"/></div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium">{{ agent.voice || 'shubh' }}</p>
                <p class="text-xs text-ink-muted">{{ agent.tts_provider || 'cartesia' }}</p>
              </div>
              <button class="btn btn-subtle btn-sm">Preview</button>
            </div>
          </div>

          <div class="card p-5">
            <h3 class="text-sm font-semibold mb-3">Test the agent</h3>
            <p class="text-xs text-ink-muted mb-3">Quick checks without leaving the studio.</p>
            <div class="space-y-2">
              <button class="btn btn-ghost w-full"><PhoneOutgoing :size="14"/> Place test call</button>
              <button class="btn btn-ghost w-full"><Bot :size="14"/> Open chat playground</button>
            </div>
          </div>

          <div class="card p-5">
            <h3 class="text-sm font-semibold mb-2">Stats</h3>
            <dl class="space-y-2 text-sm">
              <div class="flex justify-between"><dt class="text-ink-muted">Total calls</dt><dd class="font-mono">{{ agent.call_count || 0 }}</dd></div>
              <div class="flex justify-between"><dt class="text-ink-muted">Updated</dt><dd>{{ relativeTime(agent.updated_at) || '—' }}</dd></div>
              <div class="flex justify-between"><dt class="text-ink-muted">Created</dt><dd>{{ relativeTime(agent.created_at) || '—' }}</dd></div>
            </dl>
          </div>
        </aside>
      </section>

      <!-- ===== Knowledge tab placeholder ===== -->
      <section v-else-if="tab === 'knowledge'" class="card empty">
        <div class="empty-icon"><BookOpen :size="22"/></div>
        <h3 class="text-base font-semibold text-ink">Knowledge Base — coming next</h3>
        <p class="text-sm">Upload PDFs/URLs and link a vector store. This panel will land in the next migration step.</p>
      </section>

      <!-- ===== Calls tab ===== -->
      <section v-else-if="tab === 'calls'" class="space-y-3">
        <div v-if="logsLoading" class="card p-6">
          <div class="skeleton h-4 w-1/3 mb-3"></div>
          <div class="skeleton h-12 w-full mb-2"></div>
          <div class="skeleton h-12 w-full mb-2"></div>
          <div class="skeleton h-12 w-full"></div>
        </div>
        <div v-else-if="!logs.length" class="card empty">
          <div class="empty-icon"><History :size="22"/></div>
          <p class="text-sm">No calls yet. Place a test call from the Configuration tab.</p>
        </div>
        <div v-else class="card divide-y divide-line">
          <div
            v-for="(l, i) in logs" :key="i"
            class="p-4 sm:p-5 flex items-center gap-3 hover:bg-white/[0.02] cursor-pointer"
          >
            <div class="h-10 w-10 rounded-lg flex items-center justify-center"
                 :class="channelMeta(l).tone.replace('pill-', 'bg-') + '/20'">
              <component :is="channelMeta(l).icon === 'phone-call' ? PhoneOutgoing : Bot" :size="16"/>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium truncate">{{ l.summary || l.analysis || 'Call completed.' }}</p>
              <div class="flex items-center gap-1.5 mt-1 flex-wrap">
                <span class="pill" :class="sentimentMeta(l.sentiment).cls">{{ sentimentMeta(l.sentiment).label }}</span>
                <span class="pill pill-mono">{{ l.model || '—' }}</span>
                <span class="text-[11px] text-ink-dim">#{{ String(l.call_id || '').slice(0,10) }}</span>
              </div>
            </div>
            <div class="text-right">
              <p class="font-mono text-sm">{{ formatDuration(l.duration) }}</p>
              <p class="text-[11px] text-ink-muted">{{ relativeTime(l.created_at || l.timestamp) }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- ===== Settings tab ===== -->
      <section v-else class="grid sm:grid-cols-2 gap-4">
        <div class="card p-5 space-y-4">
          <h3 class="text-sm font-semibold">Call behavior</h3>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="label">Silence timeout (s)</label>
              <input type="number" step="0.1" min="0.5" max="10" v-model.number="agent.silence_timeout" class="input"/>
            </div>
            <div>
              <label class="label">Max call (s)</label>
              <input type="number" min="30" max="3600" v-model.number="agent.max_call_duration" class="input"/>
            </div>
          </div>
          <label class="flex items-center gap-2 text-sm pt-2">
            <input type="checkbox" v-model="agent.end_on_silence" class="accent-accent"/>
            End call automatically on prolonged silence
          </label>
        </div>

        <div class="card p-5 space-y-4">
          <h3 class="text-sm font-semibold">Telephony</h3>
          <div>
            <label class="label">Provider</label>
            <select v-model="agent.telephony_provider" class="select">
              <option value="vobiz">Vobiz</option>
              <option value="exotel">Exotel</option>
            </select>
          </div>
          <div>
            <label class="label">Linked phone number</label>
            <input v-model="agent.vobiz_number" class="input" placeholder="+91…"/>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
