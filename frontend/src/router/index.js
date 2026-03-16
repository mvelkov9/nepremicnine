import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { guest: true, title: 'Prijava' },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true, title: 'Nadzorna plošča' },
  },
  {
    path: '/podatki',
    name: 'data',
    component: () => import('../views/DataView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Podatki' },
  },
  {
    path: '/model',
    name: 'model',
    component: () => import('../views/ModelView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Model' },
  },
  {
    path: '/napoved',
    name: 'prediction',
    component: () => import('../views/PredictionView.vue'),
    meta: { requiresAuth: true, title: 'Napoved' },
  },
  {
    path: '/zemljevid',
    name: 'map',
    component: () => import('../views/MapView.vue'),
    meta: { requiresAuth: true, title: 'Zemljevid' },
  },
  {
    path: '/diagnostika',
    name: 'diagnostics',
    component: () => import('../views/DiagnosticsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Diagnostika' },
  },
  {
    path: '/analiza',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Analiza' },
  },
  {
    path: '/priprava',
    name: 'prepare',
    component: () => import('../views/PrepareView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Priprava podatkov' },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: 'Administracija' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'dashboard' }
  }

  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

router.afterEach((to) => {
  const base = 'Nepremičnine'
  document.title = to.meta.title ? `${to.meta.title} | ${base}` : base
})

export default router
