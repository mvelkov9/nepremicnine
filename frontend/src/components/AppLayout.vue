<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const { t, locale } = useI18n()
const auth = useAuthStore()
const router = useRouter()

const appVersion = ref('')

onMounted(async () => {
  try {
    const res = await fetch('/api/health')
    if (res.ok) {
      const data = await res.json()
      appVersion.value = data.version || ''
    }
  } catch {
    /* health endpoint unavailable */
  }
})

const navItems = [
  { to: '/', icon: '📊', label: 'nav.dashboard' },
  { to: '/podatki', icon: '📁', label: 'nav.data' },
  { to: '/model', icon: '🧠', label: 'nav.model' },
  { to: '/napoved', icon: '🔮', label: 'nav.prediction' },
  { to: '/zemljevid', icon: '🗺️', label: 'nav.map' },
  { to: '/diagnostika', icon: '📈', label: 'nav.diagnostics' },
  { to: '/analiza', icon: '🔍', label: 'nav.analysis' },
]

function userInitials() {
  if (!auth.user?.full_name) return '?'
  return auth.user.full_name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-brand">
        {{ t('app.title') }}
        <small>{{ t('app.subtitle') }}</small>
      </div>

      <nav class="sidebar-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-btn"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          {{ t(item.label) }}
        </RouterLink>

        <RouterLink
          v-if="auth.isAdmin"
          to="/admin"
          class="nav-btn"
        >
          <span class="nav-icon">⚙️</span>
          {{ t('nav.admin') }}
        </RouterLink>
      </nav>

      <div class="side-meta">
        <div class="locale-toggle">
          <button
            class="locale-btn"
            :class="{ active: locale === 'sl' }"
            @click="locale = 'sl'"
          >
            SI
          </button>
          <button
            class="locale-btn"
            :class="{ active: locale === 'en' }"
            @click="locale = 'en'"
          >
            EN
          </button>
        </div>

        <div class="user-info">
          <div class="user-avatar">{{ userInitials() }}</div>
          <div>
            <div style="color: #e2e8f0; font-weight: 600">
              {{ auth.user?.full_name || '—' }}
            </div>
            <div style="font-size: 11px">
              {{ auth.user?.role || '' }}
            </div>
          </div>
        </div>

        <button class="nav-btn" @click="handleLogout">
          <span class="nav-icon">🚪</span>
          {{ t('nav.logout') }}
        </button>

        <div v-if="appVersion" class="app-version">v{{ appVersion }}</div>
      </div>
    </aside>

    <main class="main">
      <slot />
    </main>
  </div>
</template>
