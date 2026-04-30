<script setup>
import { ref } from 'vue'
import { X, Bot, Loader2 } from 'lucide-vue-next'
import { useAgents } from '@/stores/agents'
import { useRouter } from 'vue-router'

const emit = defineEmits(['close'])
const router = useRouter()
const agents = useAgents()

const form = ref({
  name: '',
  system_prompt: 'You are a helpful AI assistant. Speak warmly and politely in the user\'s language.',
  welcome_message: 'Hello! How can I help you today?',
  language: 'hi-IN',
  model: 'kautilya-daily',
  agent_type: 'inbound',
})
const saving = ref(false)
const err = ref('')

async function submit() {
  err.value = ''
  if (!form.value.name.trim()) { err.value = 'Please enter a name.'; return }
  saving.value = true
  try {
    const res = await agents.create(form.value)
    emit('close')
    if (res?.agent_id) router.push(`/agents/${res.agent_id}`)
  } catch (e) {
    err.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <div class="scrim" @click="emit('close')"></div>
    <div class="modal p-6 sm:p-7">
      <div class="flex items-start justify-between mb-5">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-xl bg-accent-soft text-accent flex items-center justify-center">
            <Bot :size="18"/>
          </div>
          <div>
            <h2 class="text-lg font-semibold">New AI Agent</h2>
            <p class="text-xs text-ink-muted">You can fine-tune everything later in the studio.</p>
          </div>
        </div>
        <button class="btn-icon" @click="emit('close')"><X :size="16"/></button>
      </div>

      <form @submit.prevent="submit" class="space-y-4">
        <div>
          <label class="label">Agent Name</label>
          <input v-model="form.name" class="input" placeholder="e.g. Sales SDR · Mumbai" autofocus />
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="label">Language</label>
            <select v-model="form.language" class="select">
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
            <label class="label">Model</label>
            <select v-model="form.model" class="select">
              <option value="kautilya-daily">Kautilya Daily (Sarvam pipeline)</option>
              <option value="gemini-flash-live">Gemini Flash Live</option>
            </select>
          </div>
        </div>

        <div>
          <label class="label">Welcome Message</label>
          <input v-model="form.welcome_message" class="input" />
        </div>

        <div>
          <label class="label">System Prompt</label>
          <textarea v-model="form.system_prompt" class="textarea" rows="4"></textarea>
        </div>

        <div>
          <label class="label">Type</label>
          <div class="grid grid-cols-2 gap-2">
            <label
              v-for="t in ['inbound', 'outbound']" :key="t"
              class="flex items-center gap-2 p-3 border border-line rounded-lg cursor-pointer transition-colors"
              :class="form.agent_type === t ? 'bg-accent-soft border-accent/50 text-ink' : 'hover:bg-white/5'"
            >
              <input type="radio" :value="t" v-model="form.agent_type" class="accent-accent" />
              <span class="text-sm capitalize">{{ t }}</span>
            </label>
          </div>
        </div>

        <p v-if="err" class="text-sm text-danger">{{ err }}</p>

        <div class="flex justify-end gap-2 pt-2 border-t border-line">
          <button type="button" class="btn btn-ghost" @click="emit('close')">Cancel</button>
          <button class="btn btn-primary" :disabled="saving">
            <Loader2 v-if="saving" :size="14" class="animate-spin"/>
            <Bot v-else :size="14"/>
            {{ saving ? 'Creating…' : 'Create Agent' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>
