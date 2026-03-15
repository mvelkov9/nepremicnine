import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/podatki',
    name: 'data',
    component: () => import('../views/DataView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/model',
    name: 'model',
    component: () => import('../views/ModelView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/napoved',
    name: 'prediction',
    component: () => import('../views/PredictionView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/zemljevid',
    name: 'map',
    component: () => import('../views/MapView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/diagnostika',
    name: 'diagnostics',
    component: () => import('../views/DiagnosticsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/analiza',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
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

export default router
