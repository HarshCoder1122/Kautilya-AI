<script setup>
import { useRoute } from 'vue-router'
import { Construction } from 'lucide-vue-next'
const route = useRoute()
</script>

<template>
  <div class="card empty animate-fadein">
    <div class="empty-icon"><Construction :size="22"/></div>
    <h3 class="text-base font-semibold text-ink">{{ route.meta.title }} — coming next</h3>
    <p class="text-sm max-w-md">{{ route.meta.placeholder }}</p>
    <p class="text-xs text-ink-dim">In the meantime, the legacy view stays available at <a href="/dashboard-legacy" class="underline hover:text-ink">/dashboard-legacy</a>.</p>
  </div>
</template>
