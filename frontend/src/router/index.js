import { createRouter, createWebHistory } from 'vue-router'
import { i18n } from '../i18n'
import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'
import { useUiStore } from '../stores/ui'

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
      appArea: 'viewer',
      titleKey: 'nav.dashboard',
      descriptionKey: 'layout.page.dashboard',
    },
  },
  {
    path: '/napoved',
    name: 'prediction',
    alias: '/prediction',
    component: () => import('../views/PredictionView.vue'),
    meta: {
      requiresAuth: true,
      appArea: 'viewer',
      titleKey: 'nav.prediction',
      descriptionKey: 'layout.page.prediction',
    },
  },
  {
    path: '/zemljevid',
    name: 'map',
    component: () => import('../views/MapView.vue'),
    meta: {
      requiresAuth: true,
      appArea: 'viewer',
      titleKey: 'nav.map',
      descriptionKey: 'layout.page.map',
    },
  },
  {
    path: '/analiza',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
    meta: {
      requiresAuth: true,
      appArea: 'viewer',
      titleKey: 'nav.analysis',
      descriptionKey: 'layout.page.analysis',
    },
  },
  {
    path: '/obcine/:slug',
    name: 'municipality',
    component: () => import('../views/MunicipalityView.vue'),
    meta: {
      requiresAuth: true,
      appArea: 'viewer',
      titleKey: 'municipality.pageTitle',
      descriptionKey: 'municipality.pageDescription',
    },
  },
  {
    path: '/admin',
    name: 'admin-home',
    component: () => import('../views/AdminHomeView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      appArea: 'admin',
      titleKey: 'nav.admin',
      descriptionKey: 'layout.page.adminHome',
    },
  },
  {
    path: '/admin/podatki',
    name: 'admin-data',
    component: () => import('../views/DataView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      appArea: 'admin',
      titleKey: 'nav.data',
      descriptionKey: 'layout.page.data',
    },
  },
  {
    path: '/admin/priprava',
    name: 'admin-prepare',
    component: () => import('../views/PrepareView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      appArea: 'admin',
      titleKey: 'nav.prepare',
      descriptionKey: 'layout.page.prepare',
    },
  },
  {
    path: '/admin/model',
    name: 'admin-model',
    component: () => import('../views/ModelView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      appArea: 'admin',
      titleKey: 'nav.model',
      descriptionKey: 'layout.page.model',
    },
  },
  {
    path: '/admin/diagnostika',
    name: 'admin-diagnostics',
    component: () => import('../views/DiagnosticsView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      appArea: 'admin',
      titleKey: 'nav.diagnostics',
      descriptionKey: 'layout.page.diagnostics',
    },
  },
  {
    path: '/admin/uporabniki',
    name: 'admin-users',
    component: () => import('../views/AdminView.vue'),
    meta: {
      requiresAuth: true,
      requiresAdmin: true,
      appArea: 'admin',
      titleKey: 'admin.userManagement',
      descriptionKey: 'layout.page.adminUsers',
    },
  },
  {
    path: '/podatki',
    redirect: { name: 'admin-data' },
  },
  {
    path: '/priprava',
    redirect: { name: 'admin-prepare' },
  },
  {
    path: '/model',
    redirect: { name: 'admin-model' },
  },
  {
    path: '/diagnostika',
    redirect: { name: 'admin-diagnostics' },
  },
  {
    path: '/admin/users',
    redirect: { name: 'admin-users' },
  },
  {
    path: '/admin/data',
    redirect: { name: 'admin-data' },
  },
  {
    path: '/admin/prepare',
    redirect: { name: 'admin-prepare' },
  },
  {
    path: '/admin/diagnostics',
    redirect: { name: 'admin-diagnostics' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore(pinia)
  const ui = useUiStore(pinia)

  ui.beginNavigation()

  return auth.init().then(() => {
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
})

router.afterEach((to) => {
  const ui = useUiStore(pinia)
  ui.endNavigation()

  const base = 'Nepremičnine'
  document.title = to.meta.titleKey ? `${i18n.global.t(to.meta.titleKey)} | ${base}` : base
})

router.onError(() => {
  const ui = useUiStore(pinia)
  ui.endNavigation()
})

export default router
