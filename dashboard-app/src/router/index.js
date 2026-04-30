import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'

const routes = [
  { path: '/', redirect: '/overview' },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { layout: 'blank' },
  },
  {
    path: '/overview',
    name: 'overview',
    component: () => import('@/views/OverviewView.vue'),
    meta: { auth: true, title: 'Overview' },
  },
  {
    path: '/agents',
    name: 'agents',
    component: () => import('@/views/AgentsView.vue'),
    meta: { auth: true, title: 'Agents' },
  },
  {
    path: '/agents/:id',
    name: 'agent-detail',
    component: () => import('@/views/AgentDetailView.vue'),
    meta: { auth: true, title: 'Agent Studio' },
  },
  {
    path: '/calls',
    name: 'calls',
    component: () => import('@/views/CallsView.vue'),
    meta: { auth: true, title: 'Recent Calls' },
  },
  {
    path: '/telephony',
    name: 'telephony',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { auth: true, title: 'Telephony', placeholder: 'Telephony providers (Vobiz / Exotel) — coming in next migration step.' },
  },
  {
    path: '/billing',
    name: 'billing',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { auth: true, title: 'Billing', placeholder: 'Billing & usage — coming in next migration step.' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: { auth: true, title: 'Settings', placeholder: 'API keys, profile, preferences — coming in next migration step.' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/overview' },
]

export const router = createRouter({
  history: createWebHistory('/dashboard/'),
  routes,
  scrollBehavior() { return { top: 0 } },
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.ready) await auth.bootstrap()
  if (to.meta.auth && !auth.isAuthed) return { name: 'login', query: { next: to.fullPath } }
  if (to.name === 'login' && auth.isAuthed) return { path: '/overview' }
  return true
})
