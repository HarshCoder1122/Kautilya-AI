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
    path: '/leads',
    name: 'leads',
    component: () => import('@/views/LeadsView.vue'),
    meta: { auth: true, title: 'Leads' },
  },
  {
    path: '/embed',
    name: 'embed',
    component: () => import('@/views/EmbedView.vue'),
    meta: { auth: true, title: 'Embed' },
  },
  {
    path: '/telephony',
    name: 'telephony',
    component: () => import('@/views/TelephonyView.vue'),
    meta: { auth: true, title: 'Telephony' },
  },
  {
    path: '/billing',
    name: 'billing',
    component: () => import('@/views/BillingView.vue'),
    meta: { auth: true, title: 'Billing' },
  },
  {
    path: '/integrations',
    name: 'integrations',
    component: () => import('@/views/IntegrationsView.vue'),
    meta: { auth: true, title: 'Integrations' },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { auth: true, title: 'Settings' },
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
