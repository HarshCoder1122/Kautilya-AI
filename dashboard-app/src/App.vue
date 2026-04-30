<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '@/stores/auth'
import AppShell from '@/components/layout/AppShell.vue'

const route = useRoute()
const auth = useAuth()

const useShell = computed(() => route.meta.layout !== 'blank')

onMounted(() => {
  if (!auth.ready) auth.bootstrap()
})
</script>

<template>
  <template v-if="!auth.ready">
    <div class="h-screen w-screen flex items-center justify-center">
      <div class="flex items-center gap-3 text-ink-muted text-sm">
        <span class="inline-block w-4 h-4 rounded-full border-2 border-accent border-t-transparent animate-spin"></span>
        Loading workspace…
      </div>
    </div>
  </template>
  <template v-else>
    <AppShell v-if="useShell">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </AppShell>
    <router-view v-else />
  </template>
</template>

<style>
.fade-enter-active, .fade-leave-active { transition: opacity .15s ease, transform .15s ease; }
.fade-enter-from { opacity: 0; transform: translateY(4px); }
.fade-leave-to   { opacity: 0; transform: translateY(-2px); }
</style>
