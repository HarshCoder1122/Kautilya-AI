<script setup>
import { ref, onMounted, computed } from 'vue'
import { Plug, CheckCircle2, XCircle, Loader2, Save, Zap } from 'lucide-vue-next'
import { api } from '@/lib/api'

const loading = ref(true)
const items = ref([])
const editing = ref(null)       // provider id being edited
const form = ref({})
const savingForm = ref(false)
const err = ref(null)

const PROVIDER_META = {
  hubspot:         { emoji: '🟧', desc: 'Contacts + Deals sync, OAuth 2.0.' },
  salesforce:      { emoji: '☁️', desc: 'API scope: api + refresh_token.' },
  zoho:            { emoji: '🔷', desc: 'Indian SME favourite. ZohoCRM modules.' },
  google_calendar: { emoji: '📅', desc: 'Schedule follow-up meetings automatically.' },
  whatsapp:        { emoji: '🟢', desc: 'Meta WhatsApp Business — send templated follow-ups.' },
  slack:           { emoji: '💬', desc: 'Incoming webhook — team alerts.' },
  zapier:          { emoji: '⚡', desc: 'Generic webhook to 5000+ apps.' },
}

const CAT_LABELS = { crm: 'CRM', messaging: 'Messaging', calendar: 'Calendar', automation: 'Automation' }

async function load() {
  loading.value = true
  err.value = null
  try {
    const d = await api('/api/integrations')
    items.value = d.integrations || []
  } catch (e) { err.value = e.message } finally { loading.value = false }
}
onMounted(load)

const grouped = computed(() => {
  const g = {}
  for (const it of items.value) {
    ;(g[it.category] ||= []).push(it)
  }
  return g
})

function startEdit(it) {
  editing.value = it.id
  form.value = {}
}
function cancelEdit() { editing.value = null; form.value = {} }

const FIELDS = {
  hubspot:         [{ k: 'client_id', label: 'Client ID' }, { k: 'client_secret', label: 'Client Secret', type: 'password' }],
  salesforce:      [{ k: 'client_id', label: 'Consumer Key' }, { k: 'client_secret', label: 'Consumer Secret', type: 'password' }],
  zoho:            [{ k: 'client_id', label: 'Client ID' }, { k: 'client_secret', label: 'Client Secret', type: 'password' }],
  google_calendar: [{ k: 'client_id', label: 'Client ID' }, { k: 'client_secret', label: 'Client Secret', type: 'password' }],
  whatsapp: [
    { k: 'access_token', label: 'Access Token', type: 'password' },
    { k: 'phone_number_id', label: 'Phone Number ID' },
    { k: 'business_account_id', label: 'WABA ID' },
    { k: 'verify_token', label: 'Webhook Verify Token' },
  ],
  slack: [
    { k: 'webhook_url', label: 'Incoming Webhook URL', type: 'password' },
    { k: 'default_channel', label: 'Default channel (optional)' },
  ],
  zapier: [{ k: 'webhook_url', label: 'Zapier Hook URL', type: 'password' }],
}

async function saveCreds(provider) {
  savingForm.value = true
  try {
    await api(`/api/integrations/${provider}/save`, { method: 'POST', body: form.value })
    editing.value = null
    await load()
  } catch (e) { err.value = e.message } finally { savingForm.value = false }
}

async function connect(provider) {
  try {
    const d = await api(`/api/integrations/${provider}/connect`)
    if (d?.redirect_url) {
      window.open(d.redirect_url, 'kt_oauth', 'width=520,height=700')
    }
  } catch (e) { err.value = e.message }
}

async function disconnect(provider) {
  if (!confirm(`Disconnect ${provider}?`)) return
  await api(`/api/integrations/${provider}/disconnect`, { method: 'POST' })
  await load()
}

window.addEventListener('message', (e) => {
  if (e.data?.kt_integration_connected) load()
})
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <header>
      <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Connections</p>
      <h1 class="text-2xl sm:text-3xl font-bold">Integrations</h1>
      <p class="text-sm text-ink-muted mt-1">Connect Kautilya to your CRM, messaging, and calendar so agents can act — not just talk.</p>
    </header>

    <div v-if="err" class="card p-4 border border-red-500/30 bg-red-500/5 text-red-400 text-sm flex items-center gap-2">
      <XCircle :size="16"/>{{ err }}
    </div>

    <div v-if="loading" class="text-ink-muted"><Loader2 :size="14" class="animate-spin inline mr-1"/>Loading…</div>

    <section v-for="(group, cat) in grouped" :key="cat" class="space-y-3">
      <h2 class="text-sm font-semibold text-ink-muted uppercase tracking-wider">{{ CAT_LABELS[cat] || cat }}</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div v-for="it in group" :key="it.id" class="card p-4">
          <div class="flex items-start gap-3">
            <div class="text-2xl">{{ PROVIDER_META[it.id]?.emoji || '🔌' }}</div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <h3 class="font-semibold">{{ it.label }}</h3>
                <span v-if="it.connected" class="px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 :size="12"/>Connected
                </span>
                <span v-else class="px-2 py-0.5 rounded-full text-xs bg-ink-muted/10 text-ink-muted">Not connected</span>
              </div>
              <p class="text-xs text-ink-muted mt-1">{{ PROVIDER_META[it.id]?.desc || '' }}</p>
            </div>
          </div>

          <!-- Edit form -->
          <div v-if="editing === it.id" class="mt-4 space-y-2">
            <label v-for="f in FIELDS[it.id] || []" :key="f.k" class="block">
              <span class="text-xs text-ink-muted">{{ f.label }}</span>
              <input class="field-input" :type="f.type || 'text'" v-model="form[f.k]"/>
            </label>
            <div class="flex gap-2">
              <button class="btn btn-primary btn-sm" @click="saveCreds(it.id)" :disabled="savingForm">
                <Save :size="14"/>{{ savingForm ? 'Saving…' : 'Save' }}
              </button>
              <button class="btn btn-ghost btn-sm" @click="cancelEdit">Cancel</button>
              <button v-if="it.auth_type === 'oauth'" class="btn btn-ghost btn-sm ml-auto" @click="connect(it.id)">
                <Plug :size="14"/>Authorize
              </button>
            </div>
          </div>

          <div v-else class="flex gap-2 mt-4">
            <button class="btn btn-ghost btn-sm" @click="startEdit(it)">
              {{ it.connected ? 'Update credentials' : 'Set credentials' }}
            </button>
            <button v-if="it.auth_type === 'oauth' && !it.connected" class="btn btn-primary btn-sm" @click="connect(it.id)">
              <Plug :size="14"/>Connect
            </button>
            <button v-if="it.connected" class="btn btn-ghost btn-sm ml-auto text-red-400" @click="disconnect(it.id)">
              Disconnect
            </button>
          </div>
        </div>
      </div>
    </section>

    <section class="card p-5">
      <div class="flex items-center gap-2 mb-2">
        <Zap :size="16" class="text-accent"/>
        <h3 class="font-semibold">Follow-up automation</h3>
      </div>
      <p class="text-sm text-ink-muted">
        After any call or conversation, Kautilya can extract action items and dispatch them via your
        connected channels — WhatsApp follow-up, Slack ping, Calendar event, or Zapier workflow.
        Use the <code>/api/integrations/followup/extract</code> and <code>/dispatch</code> endpoints
        from your agents.
      </p>
    </section>
  </div>
</template>

<style scoped>
.field-input {
  padding: 8px 10px; border-radius: 8px; width: 100%;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.09);
  color: inherit; font-size: 13px; outline: none;
  transition: border-color 150ms; margin-top: 3px;
}
.field-input:focus { border-color: var(--accent, #FF6D3F); }
</style>
