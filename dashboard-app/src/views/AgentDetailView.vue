<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Save, Loader2, PhoneOutgoing, BookOpen, Settings as SettingsIcon,
  History, Sparkles, Volume2, Globe, Bot, Trash2, Play, Pause, Upload, FileText, Link, X
} from 'lucide-vue-next'
import { Agents, Voice } from '@/lib/api'
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

const sarvamVoices = ['shubh', 'meera', 'amartya', 'aatreyi']
const geminiVoices = ['Puck', 'Charon', 'Kore', 'Fenrir', 'Aoede']

const availableVoices = computed(() => {
  return (agent.value?.model || '').includes('gemini') ? geminiVoices : sarvamVoices
})

watch(() => agent.value?.model, (newModel, oldModel) => {
  if (oldModel && newModel !== oldModel) {
    // If we switched from Gemini to Sarvam or vice versa, reset the voice to default
    const isNowGemini = newModel.includes('gemini')
    const wasGemini = oldModel.includes('gemini')
    if (isNowGemini !== wasGemini) {
      agent.value.voice = isNowGemini ? 'Puck' : 'shubh'
    }
  }
})

// Preview state
const previewing = ref(false)
const previewAudio = ref(null)

// KB state
const kbFiles = ref([])
const kbLoading = ref(false)
const kbUploadErr = ref('')
const kbUrlInput = ref('')
const kbIndexingUrl = ref(false)

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
watch(tab, (t) => { 
  if (t === 'calls' && !logs.value.length) loadLogs() 
  if (t === 'knowledge') fetchKB()
})

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

async function fetchKB() {
  kbLoading.value = true
  try {
    const res = await Agents.kb.list(id.value)
    kbFiles.value = res.knowledge_base || []
  } catch (e) { console.error(e) }
  finally { kbLoading.value = false }
}

async function uploadKB(e) {
  const files = e.target.files
  if (!files.length) return
  kbLoading.value = true
  kbUploadErr.value = ''
  const fd = new FormData()
  for (let f of files) fd.append('files', f)
  try {
    await Agents.kb.upload(id.value, fd)
    await fetchKB()
  } catch (err) { kbUploadErr.value = err.message }
  finally { kbLoading.value = false }
}

async function addKBUrl() {
  if (!kbUrlInput.value) return
  kbIndexingUrl.value = true
  try {
    await Agents.kb.addUrl(id.value, kbUrlInput.value)
    kbUrlInput.value = ''
    await fetchKB()
  } catch (err) { alert(err.message) }
  finally { kbIndexingUrl.value = false }
}

async function removeKBFile(fileId) {
  if (!confirm('Delete this file?')) return
  try {
    await Agents.kb.remove(id.value, fileId)
    kbFiles.value = kbFiles.value.filter(f => f.id !== fileId)
  } catch (err) { alert(err.message) }
}

const TABS = [
  { id: 'config', label: 'Configuration', icon: Bot },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen },
  { id: 'calls', label: 'Recent Calls', icon: History },
  { id: 'settings', label: 'Advanced', icon: SettingsIcon },
]

async function playPreview() {
  if (!agent.value || previewing.value) return
  if (previewAudio.value) {
    previewAudio.value.pause()
    previewAudio.value = null
    return
  }
  
  // Gemini real-time voices can't be easily previewed via TTS REST API currently
  if ((agent.value.model || '').includes('gemini')) {
    alert("Gemini voices can only be previewed during a live call.")
    return
  }

  previewing.value = true
  try {
    const audioData = await Voice.preview({
      voice: agent.value.voice || 'shubh',
      provider: 'sarvam',
      text: agent.value.welcome_message || "Namaste! This is a preview of my voice."
    })
    
    // Create a blob URL from the binary response
    const blob = audioData
    const url = URL.createObjectURL(blob)
    previewAudio.value = new Audio(url)
    previewAudio.value.onended = () => { previewAudio.value = null }
    previewAudio.value.play()
  } catch (e) {
    alert(`Preview failed: ${e.message}`)
  } finally {
    previewing.value = false
  }
}
const showTestCallModal = ref(false)
const testPhoneNumber = ref('')
const testDialing = ref(false)
const testDialError = ref('')
const testDialSuccess = ref(false)

function openWebRTCChat() {
  // Opens the embedded livekit viewer in a new window/tab
  window.open(`/embed.html?agent_id=${id.value}`, '_blank', 'width=400,height=600')
}

function startWebCall() {
  showTestCallModal.value = false
  openWebRTCChat()
}

async function startPhoneCall() {
  if (!testPhoneNumber.value) return
  testDialing.value = true
  testDialError.value = ''
  testDialSuccess.value = false
  try {
    const res = await Agents.callOutbound(id.value, { to_number: testPhoneNumber.value })
    if (res?.status === 'ok') {
      testDialSuccess.value = true
      setTimeout(() => {
        showTestCallModal.value = false
        testDialSuccess.value = false
        testPhoneNumber.value = ''
      }, 3000)
    } else {
      testDialError.value = res?.error || 'Dial failed'
    }
  } catch (e) {
    testDialError.value = e.message
  } finally {
    testDialing.value = false
  }
}
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
      <!-- Test Call Modal -->
      <div v-if="showTestCallModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-fadein">
        <div class="bg-surface border border-line rounded-xl w-full max-w-md shadow-2xl overflow-hidden">
          <div class="p-5 border-b border-line flex items-center justify-between">
            <h2 class="text-lg font-semibold">Test Agent</h2>
            <button class="btn btn-ghost p-1" @click="showTestCallModal = false">✕</button>
          </div>
          <div class="p-5 space-y-4">
            <p class="text-sm text-ink-muted">Choose how you want to test the agent:</p>
            
            <div class="space-y-3">
              <button class="btn btn-subtle w-full flex flex-col items-center py-4" @click="startWebCall">
                <Globe class="mb-2" :size="20"/>
                <span class="font-medium">Web Call (Browser)</span>
                <span class="text-xs text-ink-muted mt-1">Talk via your computer microphone</span>
              </button>
              
              <div class="relative py-2">
                <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-line"></div></div>
                <div class="relative flex justify-center"><span class="bg-surface px-2 text-xs text-ink-muted">OR</span></div>
              </div>
              
              <div class="space-y-2">
                <label class="label text-xs">Enter your phone number</label>
                <div class="flex gap-2">
                  <input v-model="testPhoneNumber" type="tel" class="input flex-1" placeholder="+91..." @keyup.enter="startPhoneCall">
                  <button class="btn btn-primary" @click="startPhoneCall" :disabled="testDialing || !testPhoneNumber">
                    <Loader2 v-if="testDialing" class="animate-spin" :size="14"/>
                    <PhoneOutgoing v-else :size="14"/>
                    Dial
                  </button>
                </div>
                <p v-if="testDialError" class="text-red-400 text-xs">{{ testDialError }}</p>
                <p v-if="testDialSuccess" class="text-green-400 text-xs">Ringing! Check your phone.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

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
            <div class="space-y-4">
              <select v-model="agent.voice" class="select w-full">
                <option v-for="v in availableVoices" :key="v" :value="v">{{ v }}</option>
              </select>
              
              <div class="flex items-center gap-3">
                <div class="h-10 w-10 rounded-lg bg-accent-soft text-accent flex items-center justify-center">
                  <Volume2 :size="16"/>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium">{{ agent.voice || 'shubh' }}</p>
                  <p class="text-xs text-ink-muted">{{ (agent.model || '').includes('gemini') ? 'Gemini Realtime' : 'Sarvam TTS' }}</p>
                </div>
                <button class="btn btn-subtle btn-sm" @click="playPreview" :disabled="previewing">
                  <Loader2 v-if="previewing" :size="14" class="animate-spin" />
                  <Pause v-else-if="previewAudio" :size="14" />
                  <Play v-else :size="14" />
                </button>
              </div>
            </div>
          </div>

          <div class="card p-5">
            <h3 class="text-sm font-semibold mb-3">Test the agent</h3>
            <p class="text-xs text-ink-muted mb-3">Quick checks without leaving the studio.</p>
            <div class="space-y-2">
              <button class="btn btn-ghost w-full" @click="showTestCallModal = true"><PhoneOutgoing :size="14"/> Place test call</button>
              <button class="btn btn-ghost w-full" @click="openWebRTCChat"><Bot :size="14"/> Open WebRTC chat</button>
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

      <!-- ===== Knowledge tab ===== -->
      <section v-else-if="tab === 'knowledge'" class="space-y-6">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Upload Box -->
          <div class="card p-6 border-2 border-dashed border-line hover:border-accent/40 transition-colors relative group">
            <input type="file" multiple accept=".pdf,.txt,.docx" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer" @change="uploadKB" :disabled="kbLoading">
            <div class="text-center">
              <div class="h-12 w-12 bg-accent-soft text-accent rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform">
                <Upload :size="24"/>
              </div>
              <h3 class="font-semibold">Upload Documents</h3>
              <p class="text-sm text-ink-muted mt-1">Drop PDFs or Text files here to train your agent.</p>
              <div v-if="kbLoading" class="mt-4 flex items-center justify-center gap-2 text-accent text-sm">
                <Loader2 class="animate-spin" :size="14"/> Processing...
              </div>
            </div>
          </div>

          <!-- URL Box -->
          <div class="card p-6 flex flex-col justify-between">
            <div>
              <div class="h-10 w-10 bg-blue-500/10 text-blue-400 rounded-lg flex items-center justify-center mb-3">
                <Link :size="20"/>
              </div>
              <h3 class="font-semibold">Index Website</h3>
              <p class="text-sm text-ink-muted mt-1">Crawl a URL to add its content to the knowledge base.</p>
            </div>
            <div class="mt-4 flex gap-2">
              <input v-model="kbUrlInput" class="input flex-1" placeholder="https://example.com/docs" @keyup.enter="addKBUrl">
              <button class="btn btn-primary" @click="addKBUrl" :disabled="kbIndexingUrl || !kbUrlInput">
                <Loader2 v-if="kbIndexingUrl" class="animate-spin" :size="14"/>
                <span v-else>Add</span>
              </button>
            </div>
          </div>
        </div>

        <div v-if="kbUploadErr" class="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-xs flex items-center justify-between">
          <span>{{ kbUploadErr }}</span>
          <button @click="kbUploadErr = ''"><X :size="14"/></button>
        </div>

        <!-- Files List -->
        <div class="space-y-3">
          <h4 class="text-xs uppercase tracking-widest text-ink-muted font-bold">Current Knowledge</h4>
          
          <div v-if="kbFiles.length === 0 && !kbLoading" class="card empty py-12">
            <div class="empty-icon"><FileText :size="22"/></div>
            <p class="text-sm">No documents added yet.</p>
          </div>

          <div v-else class="grid grid-cols-1 gap-2">
            <div v-for="f in kbFiles" :key="f.id" class="card p-3 flex items-center gap-3 group">
              <div class="h-8 w-8 rounded bg-white/5 flex items-center justify-center text-ink-dim">
                <FileText v-if="f.type.includes('text') || f.type.includes('pdf')" :size="16"/>
                <Globe v-else :size="16"/>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate">{{ f.name }}</p>
                <p class="text-[10px] text-ink-muted uppercase">{{ Math.round(f.size/1024) }} KB • {{ f.type }}</p>
              </div>
              <button class="btn btn-ghost btn-sm text-red-400 opacity-0 group-hover:opacity-100 transition-opacity" @click="removeKBFile(f.id)">
                <Trash2 :size="14"/>
              </button>
            </div>
          </div>
        </div>
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

        <div class="card p-5 space-y-4 sm:col-span-2">
          <h3 class="text-sm font-semibold">Advanced Human Handoff</h3>
          <p class="text-xs text-ink-muted -mt-2">Configure behavior when a caller asks to speak to support.</p>
          <label class="flex items-center gap-2 text-sm pt-2">
            <input type="checkbox" v-model="agent.handoff_enabled" class="accent-accent"/>
            Enable human handoff fallback
          </label>
          <div v-if="agent.handoff_enabled" class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3 p-4 bg-surface-raised rounded-lg border border-line">
            <div>
              <label class="label">Support Phone Number</label>
              <input v-model="agent.handoff_number" class="input" placeholder="+91..." />
              <p class="text-[11px] text-ink-muted mt-1">For internal context. Live transfer isn't active yet.</p>
            </div>
            <div>
              <label class="label">Callback Message</label>
              <textarea v-model="agent.handoff_callback_message" class="textarea" rows="3" placeholder="All our support team members are busy right now..."></textarea>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
