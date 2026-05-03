<script setup>
import { ref, onMounted, computed } from 'vue'
import { Code2, Copy, CheckCircle2, RefreshCw, ExternalLink, Loader2 } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { useAgents } from '@/stores/agents'

const agents = useAgents()
const selected = ref(null)
const token = ref('')
const primary = ref('#FF6D3F')
const position = ref('bottom-right')
const allowed = ref('*')
const generating = ref(false)
const copied = ref(false)
const err = ref(null)

onMounted(async () => {
  if (!agents.loaded) await agents.fetch()
  if (agents.items.length) selected.value = agents.items[0]
  loadExisting()
})

function loadExisting() {
  if (selected.value?.embed_token) token.value = selected.value.embed_token
  else token.value = ''
}

const host = window.location.origin

const snippet = computed(() => {
  if (!selected.value?.id || !token.value) return '// Generate a token first'
  return `<script src="${host}/embed.js"
        data-agent="${selected.value.id}"
        data-token="${token.value}"
        data-primary="${primary.value}"
        data-position="${position.value}"><\/script>`
})

async function generate() {
  if (!selected.value) return
  generating.value = true; err.value = null
  try {
    const origins = allowed.value.split(',').map(s => s.trim()).filter(Boolean)
    const d = await api(`/api/agents/${selected.value.id}/embed-token`, {
      method: 'POST',
      body: { allowed_origins: origins.length ? origins : ['*'] },
    })
    token.value = d.token
    selected.value.embed_token = d.token
  } catch (e) { err.value = e.message }
  finally { generating.value = false }
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(snippet.value)
    copied.value = true
    setTimeout(() => copied.value = false, 1500)
  } catch {}
}

function openPreview() {
  const w = window.open('', '_blank')
  if (!w) return
  w.document.write(`
    <!doctype html><title>Kautilya embed preview</title>
    <body style="font-family:system-ui;padding:60px;background:#f7f7f5;">
      <h1>Sample page — your widget is in the corner ↘</h1>
      <p style="color:#555;">Blank demo page. Your agent's chat bubble should appear.</p>
      ${snippet.value}
    </body>`)
  w.document.close()
}
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <header>
      <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Distribution</p>
      <h1 class="text-2xl sm:text-3xl font-bold">Embed on your website</h1>
      <p class="text-sm text-ink-muted mt-1">
        Drop a single <code>&lt;script&gt;</code> tag on any site — your agent appears as a floating chat bubble.
        Captured conversations become <router-link to="/leads" class="text-accent hover:underline">leads</router-link> in your workspace.
      </p>
    </header>

    <section class="card p-5 sm:p-6 space-y-4">
      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <label class="text-xs text-ink-muted font-medium">Agent</label>
          <select v-model="selected" @change="loadExisting" class="input mt-1">
            <option v-for="a in agents.items" :key="a.id" :value="a">{{ a.name || a.id }}</option>
          </select>
          <p v-if="!agents.items.length" class="text-xs text-ink-muted mt-2">
            No agents yet. <router-link to="/agents" class="text-accent">Create one first</router-link>.
          </p>
        </div>
        <div>
          <label class="text-xs text-ink-muted font-medium">Allowed origins (comma-separated, * for any)</label>
          <input v-model="allowed" class="input mt-1" placeholder="https://mybrand.com, *.mybrand.com"/>
        </div>
        <div>
          <label class="text-xs text-ink-muted font-medium">Primary color</label>
          <div class="flex items-center gap-2 mt-1">
            <input type="color" v-model="primary" class="h-9 w-12 rounded cursor-pointer border border-line"/>
            <input v-model="primary" class="input flex-1"/>
          </div>
        </div>
        <div>
          <label class="text-xs text-ink-muted font-medium">Bubble position</label>
          <select v-model="position" class="input mt-1">
            <option value="bottom-right">Bottom-right</option>
            <option value="bottom-left">Bottom-left</option>
            <option value="top-right">Top-right</option>
            <option value="top-left">Top-left</option>
          </select>
        </div>
      </div>

      <div class="flex items-center gap-2 pt-2 border-t border-line">
        <button class="btn btn-primary" @click="generate" :disabled="!selected || generating">
          <Loader2 v-if="generating" :size="14" class="animate-spin"/>
          <RefreshCw v-else :size="14"/>
          {{ token ? 'Rotate token' : 'Generate embed token' }}
        </button>
        <span v-if="err" class="text-sm text-red-400">{{ err }}</span>
      </div>
    </section>

    <section v-if="token" class="card p-5 sm:p-6 space-y-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <Code2 :size="16" class="text-accent"/>
          <h3 class="font-semibold">Copy the snippet</h3>
        </div>
        <button class="btn btn-ghost btn-sm" @click="copyCode">
          <CheckCircle2 v-if="copied" :size="14" class="text-emerald-400"/>
          <Copy v-else :size="14"/>
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>
      <pre class="bg-bg/70 border border-line rounded-lg p-4 text-xs overflow-x-auto font-mono"><code>{{ snippet }}</code></pre>
      <p class="text-xs text-ink-muted">
        Paste this anywhere inside your website's HTML (e.g. just before <code>&lt;/body&gt;</code>).
        The widget loads async — it will not block your page.
      </p>
    </section>

    <section v-if="token" class="card p-5 sm:p-6 space-y-3">
      <h3 class="font-semibold">Try it live</h3>
      <p class="text-sm text-ink-muted">Preview the widget right now on this page:</p>
      <button class="btn btn-ghost" @click="openPreview">
        <ExternalLink :size="14"/>Open preview in new tab
      </button>
    </section>

    <section class="card p-5 sm:p-6 space-y-2 bg-bg/40">
      <h3 class="font-semibold">What the widget does</h3>
      <ul class="text-sm text-ink-muted space-y-1.5 list-disc pl-5">
        <li>Opens a chat bubble on the visitor's screen.</li>
        <li>Streams responses from your agent's configured model + system prompt.</li>
        <li>After 2 assistant turns, asks the visitor for name / email / phone.</li>
        <li>Posts captured leads to <code>/api/leads</code> — visible on your <router-link to="/leads" class="text-accent">Leads page</router-link>.</li>
        <li>If you set a <code>lead_webhook_url</code> on the agent, every lead is forked to that webhook (Zapier / Slack / your CRM).</li>
      </ul>
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
.input:focus { border-color: var(--accent, #FF6D3F); }
</style>
