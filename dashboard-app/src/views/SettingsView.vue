<script setup>
import { ref, onMounted, computed } from 'vue'
import { Key, User, Palette, Trash2, Copy, Plus, Loader2, ShieldCheck } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const tab = ref('profile')
const location = window.location

// ---------- Profile ----------
const profile = ref({ displayName: '', preferences: '' })
const savingProfile = ref(false)

async function loadProfile() {
  try {
    const p = await api('/api/user/profile').catch(() => ({}))
    profile.value.displayName = p?.displayName || auth.displayName || ''
    profile.value.preferences = p?.preferences || ''
  } catch {}
}
async function saveProfile() {
  savingProfile.value = true
  try {
    await api('/api/user/profile', { method: 'POST', body: profile.value })
  } finally { savingProfile.value = false }
}

// ---------- API Keys ----------
const keys = ref([])
const loadingKeys = ref(false)
const newKey = ref(null)
const newKeyName = ref('')

async function loadKeys() {
  loadingKeys.value = true
  try {
    const d = await api('/api/keys/list')
    keys.value = d.keys || []
  } catch { keys.value = [] }
  finally { loadingKeys.value = false }
}
async function createKey() {
  if (!newKeyName.value.trim()) return
  const d = await api('/api/keys/create', { method: 'POST', body: { name: newKeyName.value.trim() } })
  if (d.key) {
    newKey.value = d.key
    newKeyName.value = ''
    await loadKeys()
  }
}
async function revokeKey(h) {
  if (!confirm('Revoke this API key?')) return
  await api('/api/keys/revoke', { method: 'POST', body: { key_hash: h } })
  await loadKeys()
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text) } catch {}
}

// ---------- Theme ----------
const theme = ref(localStorage.getItem('kt_theme') || 'dark')
function applyTheme(v) {
  theme.value = v
  localStorage.setItem('kt_theme', v)
  document.documentElement.setAttribute('data-theme', v === 'system'
    ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
    : v)
}

onMounted(() => {
  loadProfile()
  loadKeys()
})

const tabs = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'keys', label: 'API Keys', icon: Key },
  { id: 'appearance', label: 'Appearance', icon: Palette },
]
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <header>
      <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Account</p>
      <h1 class="text-2xl sm:text-3xl font-bold">Settings</h1>
      <p class="text-sm text-ink-muted mt-1">Profile, API keys, and appearance preferences.</p>
    </header>

    <div class="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4">
      <!-- Tabs -->
      <nav class="card p-2 flex md:flex-col gap-1 overflow-x-auto">
        <button v-for="t in tabs" :key="t.id"
                class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors whitespace-nowrap"
                :class="tab === t.id ? 'bg-white/5 text-ink font-medium' : 'text-ink-muted hover:text-ink hover:bg-white/[.03]'"
                @click="tab = t.id">
          <component :is="t.icon" :size="15"/>{{ t.label }}
        </button>
      </nav>

      <!-- Content -->
      <section class="card p-5 sm:p-6 space-y-5">
        <!-- PROFILE -->
        <div v-if="tab === 'profile'" class="space-y-4">
          <h2 class="text-lg font-semibold">Your profile</h2>
          <label class="field">
            <span class="field-label">Display name</span>
            <input class="field-input" v-model="profile.displayName" placeholder="How Kautilya should address you"/>
          </label>
          <label class="field">
            <span class="field-label">Personal preferences</span>
            <textarea class="field-input" rows="5" v-model="profile.preferences"
                      placeholder="e.g. I prefer concise answers. I'm a Python developer at an Indian SaaS startup."></textarea>
            <span class="text-xs text-ink-dim">Kautilya uses this to personalize every response.</span>
          </label>
          <button class="btn btn-primary" @click="saveProfile" :disabled="savingProfile">
            <Loader2 v-if="savingProfile" :size="14" class="animate-spin"/>
            <ShieldCheck v-else :size="14"/>
            {{ savingProfile ? 'Saving…' : 'Save Profile' }}
          </button>
        </div>

        <!-- KEYS -->
        <div v-else-if="tab === 'keys'" class="space-y-4">
          <div>
            <h2 class="text-lg font-semibold">API Keys</h2>
            <p class="text-sm text-ink-muted">
              Use Kautilya in <strong>Cline</strong>, <strong>Continue</strong>, <strong>Cursor</strong>, or any OpenAI-compatible tool.
            </p>
          </div>

          <div class="rounded-lg border border-border bg-bg/40 p-4 text-sm space-y-1">
            <div><span class="text-ink-muted">Base URL:</span> <code class="text-accent">{{ location.origin }}/v1</code></div>
            <div><span class="text-ink-muted">Models:</span> <code>kautilya-coder</code>, <code>kautilya-pro</code>, <code>kautilya-daily</code></div>
            <div class="text-xs text-ink-dim">Supports streaming, tool calling, and the <code>max_thinking</code> toggle via <code>extra_body</code>.</div>
          </div>

          <div v-if="newKey" class="card p-4 border border-amber-500/40 bg-amber-500/5">
            <div class="text-sm font-semibold text-amber-400 mb-1">Copy this key now — it will not be shown again</div>
            <div class="flex items-center gap-2">
              <code class="flex-1 overflow-x-auto text-xs bg-black/30 px-3 py-2 rounded">{{ newKey }}</code>
              <button class="btn btn-ghost btn-sm" @click="copy(newKey)"><Copy :size="14"/>Copy</button>
            </div>
            <button class="text-xs text-ink-muted hover:text-ink mt-2" @click="newKey = null">Dismiss</button>
          </div>

          <div class="flex items-end gap-2">
            <label class="field flex-1">
              <span class="field-label">Key name</span>
              <input class="field-input" v-model="newKeyName" placeholder='e.g. "Laptop Cline"' @keydown.enter="createKey"/>
            </label>
            <button class="btn btn-primary" @click="createKey" :disabled="!newKeyName.trim()">
              <Plus :size="14"/>Generate
            </button>
          </div>

          <div v-if="loadingKeys" class="text-sm text-ink-muted"><Loader2 :size="14" class="animate-spin inline mr-1"/>Loading…</div>
          <div v-else-if="!keys.length" class="text-sm text-ink-muted italic">No API keys yet. Generate one above.</div>
          <ul v-else class="space-y-2">
            <li v-for="k in keys" :key="k.key_hash" class="flex items-center gap-3 p-3 rounded-lg border border-border bg-white/[.02]">
              <Key :size="16" class="text-accent shrink-0"/>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate">{{ k.name }}</div>
                <div class="text-xs text-ink-dim font-mono truncate">{{ k.preview }}</div>
              </div>
              <button class="btn btn-ghost btn-sm" @click="revokeKey(k.key_hash)">
                <Trash2 :size="14"/>Revoke
              </button>
            </li>
          </ul>
        </div>

        <!-- APPEARANCE -->
        <div v-else-if="tab === 'appearance'" class="space-y-4">
          <h2 class="text-lg font-semibold">Appearance</h2>
          <div class="grid grid-cols-3 gap-3 max-w-md">
            <button v-for="t in ['dark','light','system']" :key="t"
                    class="card p-4 border-2 transition-colors text-sm capitalize"
                    :class="theme === t ? 'border-accent' : 'border-border hover:border-white/20'"
                    @click="applyTheme(t)">
              {{ t }}
            </button>
          </div>
          <p class="text-xs text-ink-muted">Theme applies to the dashboard only; chat has its own theme setting.</p>
        </div>
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
  transition: border-color 150ms; width: 100%;
}
.field-input:focus { border-color: var(--accent, #FF6D3F); }
</style>
