import { createRouter, createWebHistory } from 'vue-router'
import { i18n } from '../i18n'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { guest: true, titleKey: 'auth.login', descriptionKey: 'layout.page.login' },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: {
      requiresAuth: true,
      titleKey: 'nav.dashboard',
      descriptionKey: 'layout.page.dashboard',
    },
  },
  {
    path: '/podatki',
    name: 'data',
    component: () => import('../views/DataView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      titleKey: 'nav.data',
      descriptionKey: 'layout.page.data',
    },
  },
  {
    path: '/model',
    name: 'model',
    component: () => import('../views/ModelView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      titleKey: 'nav.model',
      descriptionKey: 'layout.page.model',
    },
  },
  {
    path: '/napoved',
    name: 'prediction',
    component: () => import('../views/PredictionView.vue'),
    meta: {
      requiresAuth: true,
      titleKey: 'nav.prediction',
      descriptionKey: 'layout.page.prediction',
    },
  },
  {
    path: '/zemljevid',
    name: 'map',
    component: () => import('../views/MapView.vue'),
    meta: { requiresAuth: true, titleKey: 'nav.map', descriptionKey: 'layout.page.map' },
  },
  {
    path: '/diagnostika',
    name: 'diagnostics',
    component: () => import('../views/DiagnosticsView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      titleKey: 'nav.diagnostics',
      descriptionKey: 'layout.page.diagnostics',
    },
  },
  {
    path: '/analiza',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      titleKey: 'nav.analysis',
      descriptionKey: 'layout.page.analysis',
    },
  },
  {
    path: '/priprava',
    name: 'prepare',
    component: () => import('../views/PrepareView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      titleKey: 'nav.prepare',
      descriptionKey: 'layout.page.prepare',
    },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      titleKey: 'nav.admin',
      descriptionKey: 'layout.page.admin',
    },
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
  document.title = to.meta.titleKey ? `${i18n.global.t(to.meta.titleKey)} | ${base}` : base
})

export default router
