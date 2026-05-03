<script setup>
import { onMounted, ref, reactive, computed } from 'vue'
import { Phone, Save, CheckCircle2, XCircle, Loader2, Info } from 'lucide-vue-next'
import { Telephony } from '@/lib/api'

const loading = ref(true)
const saving = ref(false)
const lastSaved = ref(null)
const error = ref(null)

const providers = reactive({
  exotel: {
    enabled: false,
    account_sid: '',
    api_key: '',
    api_token: '',
    caller_id: '',
  },
  vobiz: {
    enabled: false,
    username: '',
    password: '',
    caller_id: '',
    sip_domain: '',
  },
})

const active = ref('exotel')

async function load() {
  loading.value = true
  error.value = null
  try {
    const cfg = await Telephony.config()
    if (cfg?.exotel) Object.assign(providers.exotel, cfg.exotel)
    if (cfg?.vobiz) Object.assign(providers.vobiz, cfg.vobiz)
  } catch (e) {
    error.value = e.message || 'Failed to load telephony config'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = null
  try {
    await Telephony.save({ exotel: providers.exotel, vobiz: providers.vobiz })
    lastSaved.value = new Date()
  } catch (e) {
    error.value = e.message || 'Save failed'
  } finally {
    saving.value = false
  }
}

const tabs = [
  { id: 'exotel', label: 'Exotel Cloud', hint: 'Indian PSTN, pay-as-you-go' },
  { id: 'vobiz', label: 'Vobiz AI', hint: 'SIP trunk for LiveKit' },
]

onMounted(load)
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <header class="flex items-end justify-between gap-3 flex-wrap">
      <div>
        <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Voice Infrastructure</p>
        <h1 class="text-2xl sm:text-3xl font-bold">Telephony</h1>
        <p class="text-sm text-ink-muted mt-1">Wire up your SIP / cloud-telephony provider. Agents dial through these credentials.</p>
      </div>
      <div class="flex items-center gap-2">
        <button class="btn btn-ghost btn-sm" @click="load" :disabled="loading">
          <Loader2 v-if="loading" :size="14" class="animate-spin"/>
          <Phone v-else :size="14"/>
          Refresh
        </button>
        <button class="btn btn-primary btn-sm" @click="save" :disabled="saving">
          <Save :size="14"/>
          {{ saving ? 'Saving…' : 'Save Changes' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="card p-4 border border-red-500/30 bg-red-500/5 text-red-400 text-sm flex items-center gap-2">
      <XCircle :size="16"/>{{ error }}
    </div>
    <div v-if="lastSaved" class="card p-3 border border-emerald-500/30 bg-emerald-500/5 text-emerald-400 text-sm flex items-center gap-2">
      <CheckCircle2 :size="16"/>Saved at {{ lastSaved.toLocaleTimeString() }}
    </div>

    <!-- Provider tabs -->
    <div class="card p-0 overflow-hidden">
      <div class="flex border-b border-border">
        <button v-for="t in tabs" :key="t.id"
                class="px-5 py-3 text-sm font-medium transition-colors"
                :class="active === t.id ? 'text-ink border-b-2 border-accent' : 'text-ink-muted hover:text-ink'"
                @click="active = t.id">
          {{ t.label }}
        </button>
      </div>

      <!-- Exotel -->
      <section v-if="active === 'exotel'" class="p-5 sm:p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="md:col-span-2 flex items-start gap-2 text-xs text-ink-muted bg-bg/50 border border-border rounded-lg p-3">
          <Info :size="14" class="mt-0.5 shrink-0"/>
          <span>Exotel credentials are stored encrypted on your Kautilya account and used only for outbound dials from your agents.</span>
        </div>
        <label class="field">
          <span class="field-label">Enable Exotel</span>
          <label class="toggle">
            <input type="checkbox" v-model="providers.exotel.enabled" />
            <span>Use Exotel as outbound provider</span>
          </label>
        </label>
        <label class="field">
          <span class="field-label">Account SID</span>
          <input class="field-input" v-model="providers.exotel.account_sid" placeholder="exotel_account_sid" />
        </label>
        <label class="field">
          <span class="field-label">API Key</span>
          <input class="field-input" v-model="providers.exotel.api_key" placeholder="Exotel API Key" />
        </label>
        <label class="field">
          <span class="field-label">API Token</span>
          <input type="password" class="field-input" v-model="providers.exotel.api_token" placeholder="••••••••" />
        </label>
        <label class="field">
          <span class="field-label">Caller ID</span>
          <input class="field-input" v-model="providers.exotel.caller_id" placeholder="+91XXXXXXXXXX" />
        </label>
      </section>

      <!-- Vobiz -->
      <section v-else class="p-5 sm:p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <label class="field">
          <span class="field-label">Enable Vobiz</span>
          <label class="toggle">
            <input type="checkbox" v-model="providers.vobiz.enabled" />
            <span>Use Vobiz SIP trunk</span>
          </label>
        </label>
        <label class="field">
          <span class="field-label">Username</span>
          <input class="field-input" v-model="providers.vobiz.username" placeholder="sip_user" />
        </label>
        <label class="field">
          <span class="field-label">Password</span>
          <input type="password" class="field-input" v-model="providers.vobiz.password" placeholder="••••••••" />
        </label>
        <label class="field">
          <span class="field-label">Caller ID</span>
          <input class="field-input" v-model="providers.vobiz.caller_id" placeholder="+91XXXXXXXXXX" />
        </label>
        <label class="field md:col-span-2">
          <span class="field-label">SIP Domain</span>
          <input class="field-input" v-model="providers.vobiz.sip_domain" placeholder="sip.vobiz.ai" />
        </label>
      </section>
    </div>
  </div>
</template>

<style scoped>
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 12px; color: var(--ink-muted, #9b9ba7); font-weight: 500; }
.field-input {
  padding: 9px 12px; border-radius: 8px;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.09);
  color: inherit; font-size: 14px; outline: none;
  transition: border-color 150ms;
}
.field-input:focus { border-color: var(--accent, #FF6D3F); }
.toggle { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; }
.toggle input { width: 16px; height: 16px; accent-color: var(--accent, #FF6D3F); }
</style>
