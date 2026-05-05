<script setup>
import { ref, onMounted, computed } from 'vue'
import { Code2, Copy, CheckCircle2, Key, Loader2, RefreshCw } from 'lucide-vue-next'
import { User } from '@/lib/api'
import { useAgents } from '@/stores/agents'

const agents = useAgents()
const selected = ref(null)
const apiKey = ref('')
const loadingKey = ref(true)
const generating = ref(false)
const copied = ref(false)
const err = ref(null)
const tab = ref('react')

onMounted(async () => {
  if (!agents.loaded) await agents.fetch()
  if (agents.items.length) selected.value = agents.items[0]
  
  try {
    const act = await User.account()
    if (act.api_key) apiKey.value = act.api_key
  } catch (e) {
    console.error(e)
  } finally {
    loadingKey.value = false
  }
})

const snippetReact = computed(() => {
  const aid = selected.value?.id || 'YOUR_AGENT_ID'
  return `import { LiveKitRoom } from '@livekit/components-react';

// 1. Fetch token from RevealIQ using your API Key
const response = await fetch('https://revealiq.example.com/api/agents/${aid}/livekit-token', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ${apiKey.value || 'YOUR_API_KEY'}',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ participantName: "Web User" })
});
const { token, wsUrl } = await response.json();

// 2. Connect your UI
return (
  <LiveKitRoom
    video={false}
    audio={true}
    token={token}
    serverUrl={wsUrl}
    connect={true}
  >
    {/* Your custom UI here */}
  </LiveKitRoom>
);`
})

const snippetJS = computed(() => {
  const aid = selected.value?.id || 'YOUR_AGENT_ID'
  return `import { Room } from 'livekit-client';

// 1. Fetch token
const response = await fetch('https://revealiq.example.com/api/agents/${aid}/livekit-token', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ${apiKey.value || 'YOUR_API_KEY'}',
    'Content-Type': 'application/json'
  }
});
const { token, wsUrl } = await response.json();

// 2. Connect to Room
const room = new Room({ adaptiveStream: true, dynacast: true });
await room.connect(wsUrl, token);

// 3. Publish Microphone
await room.localParticipant.setMicrophoneEnabled(true);
console.log('Connected to agent!');`
})

async function generateKey() {
  if (!confirm(apiKey.value ? "Are you sure? This will invalidate your existing API key." : "Generate a new API key?")) return
  generating.value = true; err.value = null
  try {
    const res = await User.generateApiKey()
    apiKey.value = res.api_key
  } catch (e) { err.value = e.message }
  finally { generating.value = false }
}

async function copyCode(text) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => copied.value = false, 1500)
  } catch {}
}
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <header>
      <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Developer</p>
      <h1 class="text-2xl sm:text-3xl font-bold">API & Integrations</h1>
      <p class="text-sm text-ink-muted mt-1">
        Integrate RevealIQ agents directly into your own web or mobile applications using the LiveKit SDK.
      </p>
    </header>

    <section class="card p-5 sm:p-6 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold flex items-center gap-2"><Key :size="16"/> Your API Key</h2>
          <p class="text-xs text-ink-muted mt-0.5">Use this key to authenticate server-side API requests.</p>
        </div>
        <button class="btn btn-ghost text-xs" @click="generateKey" :disabled="generating">
          <Loader2 v-if="generating" :size="14" class="animate-spin"/>
          <RefreshCw v-else :size="14"/>
          {{ apiKey ? 'Regenerate' : 'Generate Key' }}
        </button>
      </div>
      
      <div v-if="loadingKey" class="skeleton h-10 w-full"></div>
      <div v-else-if="!apiKey" class="p-4 bg-bg-subtle border border-line rounded-lg text-center">
        <p class="text-sm text-ink-muted mb-3">You don't have an API key yet.</p>
        <button class="btn btn-primary" @click="generateKey">Generate API Key</button>
      </div>
      <div v-else class="flex gap-2">
        <input type="text" readonly :value="apiKey" class="input flex-1 font-mono text-sm" />
        <button class="btn btn-subtle" @click="copyCode(apiKey)">Copy</button>
      </div>
      <p v-if="err" class="text-red-400 text-xs">{{ err }}</p>
    </section>

    <section class="card p-5 sm:p-6 space-y-4">
      <div>
        <h2 class="text-base font-semibold">LiveKit Integration Guide</h2>
        <p class="text-xs text-ink-muted mt-0.5">Build a completely custom UI by connecting your app directly to the agent's WebRTC room.</p>
      </div>
      
      <div class="space-y-3 pt-2">
        <div>
          <label class="text-xs text-ink-muted font-medium mb-1 block">Select Agent to generate snippet for:</label>
          <select v-model="selected" class="select max-w-sm">
            <option v-for="a in agents.items" :key="a.id" :value="a">{{ a.name || a.id }}</option>
          </select>
        </div>

        <div class="border border-line rounded-lg overflow-hidden mt-4">
          <div class="flex items-center border-b border-line bg-bg-subtle">
            <button class="px-4 py-2 text-sm font-medium hover:bg-white/5 transition-colors" :class="tab==='react'?'text-accent border-b-2 border-accent':'text-ink-muted'" @click="tab='react'">React</button>
            <button class="px-4 py-2 text-sm font-medium hover:bg-white/5 transition-colors" :class="tab==='js'?'text-accent border-b-2 border-accent':'text-ink-muted'" @click="tab='js'">Vanilla JS</button>
            <div class="flex-1"></div>
            <button class="btn btn-ghost btn-sm mr-2" @click="copyCode(tab==='react'?snippetReact:snippetJS)">
              <CheckCircle2 v-if="copied" :size="14" class="text-emerald-400"/>
              <Copy v-else :size="14"/> Copy
            </button>
          </div>
          <pre class="p-4 text-xs overflow-x-auto font-mono bg-[#1e1e1e] text-[#d4d4d4]"><code>{{ tab === 'react' ? snippetReact : snippetJS }}</code></pre>
        </div>
      </div>
      
      <div class="mt-4 p-4 bg-accent/10 border border-accent/20 rounded-lg">
        <h3 class="text-sm font-semibold text-accent mb-1">Security Best Practice</h3>
        <p class="text-xs text-ink-muted">
          Never expose your API Key in your frontend code. You should proxy the token request through your own backend server to securely fetch the LiveKit token.
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.input {
  width: 100%; padding: 9px 12px; border-radius: 10px;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.09);
  color: inherit; font-size: 14px; outline: none;
}
</style>
