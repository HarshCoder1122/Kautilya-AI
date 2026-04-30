<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import {
  LayoutDashboard, Bot, Phone, Radio, Wallet, Settings,
  Menu, X, Search, LogOut, ChevronsLeft, ChevronsRight, Plus,
} from 'lucide-vue-next'
import { useAuth } from '@/stores/auth'
import { initials } from '@/lib/format'

const auth = useAuth()
const route = useRoute()
const router = useRouter()

const drawerOpen = ref(false)
const collapsed = ref(false)

const NAV = [
  { to: '/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/calls', label: 'Calls', icon: Phone },
  { to: '/telephony', label: 'Telephony', icon: Radio },
  { to: '/billing', label: 'Billing', icon: Wallet },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const MOBILE_NAV = [
  { to: '/overview', label: 'Home', icon: LayoutDashboard },
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/calls', label: 'Calls', icon: Phone },
  { to: '/telephony', label: 'Phone', icon: Radio },
  { to: '/settings', label: 'More', icon: Settings },
]

const title = computed(() => route.meta.title || '')

function isActive(path) {
  return route.path === path || route.path.startsWith(path + '/')
}

async function doSignOut() {
  await auth.signOut()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="min-h-screen flex w-full">
    <!-- ===== Desktop sidebar ===== -->
    <aside
      class="hidden md:flex flex-col border-r border-line bg-bg-elev/60 backdrop-blur-md sticky top-0 h-screen transition-[width] duration-200 z-20"
      :style="{ width: collapsed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)' }"
    >
      <div class="h-14 flex items-center gap-2 px-4 border-b border-line">
        <div class="h-8 w-8 rounded-lg bg-gradient-to-br from-accent to-accent-strong flex items-center justify-center text-[#00211D] font-extrabold text-sm shadow-glow">
          K
        </div>
        <div v-if="!collapsed" class="flex flex-col leading-tight">
          <span class="text-sm font-semibold text-ink">Kautilya</span>
          <span class="text-[10px] text-ink-muted uppercase tracking-wider">RevealIQ Studio</span>
        </div>
      </div>

      <nav class="flex-1 px-3 py-4 flex flex-col gap-1">
        <RouterLink
          v-for="item in NAV" :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to) }"
          :title="collapsed ? item.label : ''"
        >
          <component :is="item.icon" :size="18" />
          <span v-if="!collapsed">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="p-3 border-t border-line">
        <div class="flex items-center gap-2.5" :class="{ 'justify-center': collapsed }">
          <div class="avatar">
            <img v-if="auth.photo" :src="auth.photo" referrerpolicy="no-referrer" />
            <span v-else>{{ initials(auth.displayName) }}</span>
          </div>
          <div v-if="!collapsed" class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate">{{ auth.displayName }}</div>
            <div class="text-[11px] text-ink-muted truncate">{{ auth.email }}</div>
          </div>
          <button v-if="!collapsed" @click="doSignOut" class="btn-icon" title="Sign out">
            <LogOut :size="14" />
          </button>
        </div>

        <button
          @click="collapsed = !collapsed"
          class="mt-3 w-full btn-icon !justify-center"
          :title="collapsed ? 'Expand' : 'Collapse'"
        >
          <component :is="collapsed ? ChevronsRight : ChevronsLeft" :size="14" />
        </button>
      </div>
    </aside>

    <!-- ===== Mobile drawer ===== -->
    <transition name="drawer">
      <div v-if="drawerOpen" class="md:hidden fixed inset-0 z-40">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="drawerOpen = false"></div>
        <aside class="absolute inset-y-0 left-0 w-[78%] max-w-[300px] bg-bg-elev border-r border-line flex flex-col">
          <div class="h-14 flex items-center justify-between px-4 border-b border-line">
            <div class="flex items-center gap-2">
              <div class="h-8 w-8 rounded-lg bg-gradient-to-br from-accent to-accent-strong flex items-center justify-center text-[#00211D] font-extrabold text-sm">K</div>
              <span class="text-sm font-semibold">Kautilya</span>
            </div>
            <button class="btn-icon" @click="drawerOpen = false"><X :size="16" /></button>
          </div>
          <nav class="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
            <RouterLink
              v-for="item in NAV" :key="item.to"
              :to="item.to"
              class="nav-item"
              :class="{ active: isActive(item.to) }"
              @click="drawerOpen = false"
            >
              <component :is="item.icon" :size="18" />
              <span>{{ item.label }}</span>
            </RouterLink>
          </nav>
          <div class="p-3 border-t border-line">
            <div class="flex items-center gap-2.5">
              <div class="avatar">
                <img v-if="auth.photo" :src="auth.photo" referrerpolicy="no-referrer" />
                <span v-else>{{ initials(auth.displayName) }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate">{{ auth.displayName }}</div>
                <div class="text-[11px] text-ink-muted truncate">{{ auth.email }}</div>
              </div>
              <button @click="doSignOut" class="btn-icon" title="Sign out"><LogOut :size="14" /></button>
            </div>
          </div>
        </aside>
      </div>
    </transition>

    <!-- ===== Main column ===== -->
    <div class="flex-1 min-w-0 flex flex-col">
      <header class="topbar sticky top-0 z-10">
        <button class="btn-icon md:hidden" @click="drawerOpen = true"><Menu :size="18" /></button>
        <div class="flex flex-col flex-1 min-w-0">
          <h1 class="text-base sm:text-lg font-semibold truncate">{{ title }}</h1>
        </div>
        <div class="hidden md:flex items-center gap-2 max-w-[320px] flex-1 min-w-0">
          <div class="relative w-full">
            <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-dim" />
            <input class="input pl-8 h-9 text-sm" placeholder="Search agents, calls…" />
            <span class="kbd absolute right-2 top-1/2 -translate-y-1/2 hidden lg:inline">⌘K</span>
          </div>
        </div>
        <button class="btn btn-primary btn-sm hidden sm:inline-flex" @click="router.push('/agents?new=1')">
          <Plus :size="14" /> New Agent
        </button>
        <div class="avatar md:hidden">
          <img v-if="auth.photo" :src="auth.photo" referrerpolicy="no-referrer" />
          <span v-else>{{ initials(auth.displayName) }}</span>
        </div>
      </header>

      <main class="flex-1 px-4 sm:px-6 lg:px-8 py-6 pb-24 md:pb-10 max-w-[1400px] w-full mx-auto">
        <slot />
      </main>
    </div>

    <!-- ===== Mobile bottom nav ===== -->
    <nav class="bottom-nav">
      <RouterLink
        v-for="item in MOBILE_NAV" :key="item.to" :to="item.to"
        class="bottom-nav-item"
        :class="{ active: isActive(item.to) }"
      >
        <component :is="item.icon" :size="20" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.drawer-enter-active, .drawer-leave-active { transition: opacity .2s ease; }
.drawer-enter-active aside, .drawer-leave-active aside { transition: transform .25s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from aside, .drawer-leave-to aside { transform: translateX(-100%); }
</style>
