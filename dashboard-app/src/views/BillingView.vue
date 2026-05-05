<script setup>
import { ref, onMounted, computed } from 'vue'
import { Crown, Zap, Sparkles, CreditCard, Download, Loader2, ArrowUpRight } from 'lucide-vue-next'
import { Billing } from '@/lib/api'

const loading = ref(true)
const config = ref(null)
const txns = ref([])

async function load() {
  loading.value = true
  try {
    const [cfg, tx] = await Promise.all([
      Billing.status().catch(() => ({})),
      api('/api/billing/transactions').catch(() => ({ transactions: [] })),
    ])
    config.value = cfg || {}
    txns.value = tx.transactions || tx.items || []
  } finally {
    loading.value = false
  }
}
onMounted(load)

const isPro = computed(() => !!config.value?.is_pro)
const credits = computed(() => config.value?.credits ?? 0)
const tokens = computed(() => config.value?.usage?.llm_tokens ?? 0)
const ttsChars = computed(() => config.value?.usage?.tts_chars ?? 0)

const plans = [
  {
    id: 'free', name: 'Free', price: '₹0', tagline: 'Get started',
    features: ['30 messages/day', 'Daily model', '10k tokens/day', 'Community support'],
    accent: 'border-border',
  },
  {
    id: 'pro', name: 'Pro', price: '₹599', period: '/mo', tagline: 'Most popular',
    features: ['Unlimited messages', 'All models (Pro + Coder)', 'Max Thinking mode', 'Background tasks', 'API access for Cline/Continue', 'Priority support'],
    accent: 'border-accent',
    highlight: true,
  },
]

async function upgrade() {
  try {
    const order = await api('/api/billing/create-order', {
      method: 'POST',
      body: { plan: 'pro' },
    })
    if (!order?.order_id) { alert('Failed to create order'); return }
    const rzp = new window.Razorpay({
      key: order.key_id,
      order_id: order.order_id,
      amount: order.amount,
      currency: order.currency || 'INR',
      name: 'Kautilya AI Pro',
      description: 'Monthly subscription',
      theme: { color: '#FF6D3F' },
      handler: async (resp) => {
        await api('/api/billing/verify-payment', {
          method: 'POST',
          body: {
            razorpay_order_id: resp.razorpay_order_id,
            razorpay_payment_id: resp.razorpay_payment_id,
            razorpay_signature: resp.razorpay_signature,
          },
        })
        await load()
      },
    })
    rzp.open()
  } catch (e) {
    alert(e.message || 'Upgrade failed')
  }
}

function fmtDate(ts) {
  if (!ts) return '—'
  try { return new Date(ts * 1000 || ts).toLocaleString() } catch { return String(ts) }
}
</script>

<template>
  <div class="space-y-6 animate-fadein">
    <header class="flex items-end justify-between gap-3 flex-wrap">
      <div>
        <p class="text-xs uppercase tracking-widest text-ink-muted mb-1">Plan & Usage</p>
        <h1 class="text-2xl sm:text-3xl font-bold">Billing</h1>
        <p class="text-sm text-ink-muted mt-1">Manage your subscription, credits, and payment history.</p>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="loading" class="text-xs text-ink-dim flex items-center gap-1"><Loader2 :size="12" class="animate-spin"/> Loading…</span>
        <div class="px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5"
             :class="isPro ? 'bg-accent/10 text-accent border border-accent/30' : 'bg-bg/60 text-ink-muted border border-border'">
          <Crown :size="12"/>{{ isPro ? 'Pro Plan' : 'Free Plan' }}
        </div>
      </div>
    </header>

    <!-- Usage overview -->
    <section class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="stat card-hover">
        <div class="flex items-start justify-between">
          <span class="stat-label">Credits balance</span>
          <Sparkles :size="16" class="text-accent"/>
        </div>
        <div class="stat-value">{{ credits }}</div>
        <div class="text-xs text-ink-dim">Used for premium features</div>
      </div>
      <div class="stat card-hover">
        <div class="flex items-start justify-between">
          <span class="stat-label">LLM tokens today</span>
          <Zap :size="16" class="text-info"/>
        </div>
        <div class="stat-value">{{ tokens.toLocaleString() }}</div>
        <div class="text-xs text-ink-dim">{{ isPro ? 'Unlimited' : 'Free limit: 10k' }}</div>
      </div>
      <div class="stat card-hover">
        <div class="flex items-start justify-between">
          <span class="stat-label">TTS characters today</span>
          <CreditCard :size="16" class="text-success"/>
        </div>
        <div class="stat-value">{{ ttsChars.toLocaleString() }}</div>
        <div class="text-xs text-ink-dim">{{ isPro ? 'Unlimited' : 'Free limit: 5k' }}</div>
      </div>
    </section>

    <!-- Plans -->
    <section class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div v-for="p in plans" :key="p.id" class="card p-5 sm:p-6 border-2 relative"
           :class="[p.accent, p.highlight && 'ring-1 ring-accent/30']">
        <div v-if="p.highlight" class="absolute -top-3 left-6 bg-accent text-white text-xs px-2 py-0.5 rounded-full font-semibold">
          {{ p.tagline }}
        </div>
        <div class="flex items-baseline gap-2 mb-1">
          <h2 class="text-xl font-bold">{{ p.name }}</h2>
          <span class="text-2xl font-bold">{{ p.price }}</span>
          <span class="text-sm text-ink-muted">{{ p.period || '' }}</span>
        </div>
        <p class="text-sm text-ink-muted mb-4">{{ p.tagline }}</p>
        <ul class="space-y-2 text-sm mb-5">
          <li v-for="f in p.features" :key="f" class="flex items-start gap-2">
            <span class="text-accent mt-1">✓</span><span>{{ f }}</span>
          </li>
        </ul>
        <button v-if="p.id === 'pro' && !isPro" class="btn btn-primary w-full" @click="upgrade">
          Upgrade to Pro <ArrowUpRight :size="14"/>
        </button>
        <button v-else-if="p.id === 'pro' && isPro" class="btn btn-ghost w-full" disabled>
          <Crown :size="14"/> Current plan
        </button>
        <button v-else class="btn btn-ghost w-full" disabled>
          {{ isPro ? 'Downgrade via support' : 'Current plan' }}
        </button>
      </div>
    </section>

    <!-- Transactions -->
    <section class="card p-5 sm:p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-base font-semibold">Payment history</h3>
        <button class="btn btn-ghost btn-sm" @click="load"><Download :size="14"/>Refresh</button>
      </div>
      <div v-if="!txns.length" class="text-sm text-ink-muted italic py-6 text-center">
        No transactions yet.
      </div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left text-xs uppercase tracking-wider text-ink-dim border-b border-border">
            <th class="py-2">Date</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(t, i) in txns" :key="i" class="border-b border-border/50">
            <td class="py-3">{{ fmtDate(t.timestamp || t.created_at) }}</td>
            <td>{{ t.description || t.plan || 'Payment' }}</td>
            <td>₹{{ ((t.amount || 0) / 100).toFixed(2) }}</td>
            <td>
              <span class="px-2 py-0.5 rounded-full text-xs"
                    :class="t.status === 'captured' || t.status === 'paid'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-amber-500/10 text-amber-400'">
                {{ t.status || 'pending' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
