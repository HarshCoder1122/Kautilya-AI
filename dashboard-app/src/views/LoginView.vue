<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Sparkles, Bot, BarChart3, ShieldCheck } from 'lucide-vue-next'
import { useAuth } from '@/stores/auth'

const auth = useAuth()
const router = useRouter()
const route = useRoute()
const loading = ref(false)
const err = ref('')

async function go() {
  err.value = ''
  loading.value = true
  try {
    await auth.signIn()
    router.replace(route.query.next || '/overview')
  } catch (e) {
    err.value = e?.message || 'Sign-in failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen grid lg:grid-cols-2">
    <!-- Left: marketing panel -->
    <div class="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden">
      <div class="absolute inset-0 -z-10">
        <div class="absolute inset-0 bg-gradient-to-br from-bg via-bg-elev to-bg"></div>
        <div class="absolute -top-32 -left-32 w-[480px] h-[480px] rounded-full bg-accent/20 blur-3xl"></div>
        <div class="absolute -bottom-40 -right-32 w-[520px] h-[520px] rounded-full bg-info/10 blur-3xl"></div>
      </div>

      <div class="flex items-center gap-3">
        <div class="h-10 w-10 rounded-xl bg-gradient-to-br from-accent to-accent-strong flex items-center justify-center text-[#00211D] font-extrabold shadow-glow">K</div>
        <div>
          <div class="text-base font-semibold text-ink">Kautilya AI</div>
          <div class="text-[11px] uppercase tracking-widest text-ink-muted">RevealIQ Studio</div>
        </div>
      </div>

      <div class="space-y-6 max-w-md">
        <h1 class="text-4xl font-bold leading-tight grad-text">
          Voice agents that <br/>convert calls into customers.
        </h1>
        <p class="text-ink-muted text-[15px] leading-relaxed">
          Build, deploy and analyze AI voice & chat agents end-to-end. Sub-second latency,
          Indian-language native, full call intelligence — all in one studio.
        </p>
        <ul class="space-y-3 text-sm">
          <li class="flex items-start gap-3"><Sparkles :size="18" class="text-accent mt-0.5"/><span>Realtime voice with Gemini Live & Sarvam STT/TTS</span></li>
          <li class="flex items-start gap-3"><Bot :size="18" class="text-accent mt-0.5"/><span>Multi-agent workspace with knowledge bases</span></li>
          <li class="flex items-start gap-3"><BarChart3 :size="18" class="text-accent mt-0.5"/><span>NIM-powered post-call analytics & lead scoring</span></li>
          <li class="flex items-start gap-3"><ShieldCheck :size="18" class="text-accent mt-0.5"/><span>SIP-ready: Vobiz, Exotel, Twilio compatible</span></li>
        </ul>
      </div>

      <div class="text-xs text-ink-dim">© 2026 Kautilya AI · ai.revealiq.in</div>
    </div>

    <!-- Right: sign-in -->
    <div class="flex items-center justify-center p-6 sm:p-12">
      <div class="w-full max-w-md">
        <div class="lg:hidden flex items-center gap-3 mb-10">
          <div class="h-10 w-10 rounded-xl bg-gradient-to-br from-accent to-accent-strong flex items-center justify-center text-[#00211D] font-extrabold">K</div>
          <div>
            <div class="text-base font-semibold">Kautilya AI</div>
            <div class="text-[11px] uppercase tracking-widest text-ink-muted">RevealIQ Studio</div>
          </div>
        </div>

        <div class="card p-7 sm:p-9 shadow-2xl">
          <h2 class="text-xl font-semibold mb-1">Sign in to your studio</h2>
          <p class="text-sm text-ink-muted mb-7">Access your agents, calls and analytics in one place.</p>

          <button class="btn btn-lg w-full bg-white text-black hover:brightness-95 flex items-center justify-center gap-3" :disabled="loading" @click="go">
            <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.4 29.3 35.5 24 35.5c-6.4 0-11.5-5.1-11.5-11.5S17.6 12.5 24 12.5c2.9 0 5.6 1.1 7.6 2.9l5.7-5.7C33.6 6.3 29 4.5 24 4.5 13.2 4.5 4.5 13.2 4.5 24S13.2 43.5 24 43.5c10.8 0 19.5-8.7 19.5-19.5 0-1.3-.1-2.3-.4-3.5z"/>
              <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.5 16 18.9 12.5 24 12.5c2.9 0 5.6 1.1 7.6 2.9l5.7-5.7C33.6 6.3 29 4.5 24 4.5 16.3 4.5 9.6 8.7 6.3 14.7z"/>
              <path fill="#4CAF50" d="M24 43.5c5 0 9.5-1.7 13-4.6l-6-5.1c-1.9 1.4-4.3 2.2-7 2.2-5.3 0-9.7-3.1-11.3-7.5l-6.5 5C9.4 39.4 16.1 43.5 24 43.5z"/>
              <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.7 2.2-2.1 4.1-3.9 5.4l6 5.1c-.4.4 6.6-4.8 6.6-14 0-1.3-.1-2.3-.4-4z"/>
            </svg>
            <span class="font-semibold">{{ loading ? 'Signing in…' : 'Continue with Google' }}</span>
          </button>

          <p v-if="err" class="mt-4 text-sm text-danger text-center">{{ err }}</p>

          <div class="divider my-8"></div>
          
          <div class="text-center space-y-4">
            <p class="text-sm text-ink-muted">
              Don't have an account? 
              <button @click="go" class="text-accent hover:underline font-medium">Sign up for free</button>
            </p>
            
            <p class="text-xs text-ink-dim">
              By continuing you agree to our <a href="#" class="underline hover:text-ink">Terms</a> &
              <a href="#" class="underline hover:text-ink">Privacy Policy</a>.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
