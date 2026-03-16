<script setup>
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { setLocale } from '../i18n'
  import AppIcon from './AppIcon.vue'
  import { useDarkMode } from '../composables/useDarkMode'
  import { useAuthStore } from '../stores/auth'
  import { useToast } from '../composables/useToast'
  import { getApiErrorMessage } from '../utils/apiError'

  const { t, locale } = useI18n()
  const auth = useAuthStore()
  const route = useRoute()
  const router = useRouter()
  const { showToast } = useToast()
  const { isDark, toggleDark } = useDarkMode()

  const mobileMenuOpen = ref(false)
  const profileOpen = ref(false)
  const profileSaving = ref(false)
  const appVersion = ref('')
  const profileForm = ref({
    full_name: '',
    avatar_url: '',
  })

  const navItems = [
    { to: '/', icon: 'dashboard', label: 'nav.dashboard', shortKey: 'dashboard', admin: false },
    { to: '/podatki', icon: 'data', label: 'nav.data', shortKey: 'data', admin: true },
    { to: '/priprava', icon: 'prepare', label: 'nav.prepare', shortKey: 'prepare', admin: true },
    { to: '/model', icon: 'model', label: 'nav.model', shortKey: 'model', admin: true },
    {
      to: '/napoved',
      icon: 'prediction',
      label: 'nav.prediction',
      shortKey: 'prediction',
      admin: false,
    },
    { to: '/zemljevid', icon: 'map', label: 'nav.map', shortKey: 'map', admin: false },
    {
      to: '/diagnostika',
      icon: 'diagnostics',
      label: 'nav.diagnostics',
      shortKey: 'diagnostics',
      admin: true,
    },
    { to: '/analiza', icon: 'analysis', label: 'nav.analysis', shortKey: 'analysis', admin: true },
    { to: '/admin', icon: 'admin', label: 'nav.admin', shortKey: 'admin', admin: true },
  ]

  const currentItem = computed(
    () =>
      navItems.find((item) => item.to === route.path) || navItems.find((item) => item.to === '/'),
  )

  const currentTitle = computed(() =>
    route.meta.titleKey
      ? t(route.meta.titleKey)
      : currentItem.value
        ? t(currentItem.value.label)
        : t('app.title'),
  )

  const visibleNavItems = computed(() => navItems.filter((item) => !item.admin || auth.isAdmin))

  const avatarUrl = computed(() => auth.user?.avatar_url || '')
  const profileAvatarUrl = computed(() => profileForm.value.avatar_url.trim() || avatarUrl.value)

  const userRoleLabel = computed(() =>
    auth.isAdmin ? t('layout.roleAdmin') : t('layout.roleViewer'),
  )

  const versionBadge = computed(() =>
    appVersion.value ? t('layout.versionBadge', { version: appVersion.value }) : '',
  )

  const profileInitials = computed(() => {
    const source = profileForm.value.full_name || auth.user?.full_name || ''
    if (!source.trim()) return '?'
    return source
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  })

  watch(
    () => auth.user,
    (user) => {
      profileForm.value = {
        full_name: user?.full_name || '',
        avatar_url: user?.avatar_url || '',
      }
    },
    { immediate: true },
  )

  onMounted(async () => {
    try {
      const res = await fetch('/api/health')
      if (res.ok) {
        const data = await res.json()
        appVersion.value = data.version || ''
      }
    } catch {
      /* no-op */
    }
  })

  function changeLocale(nextLocale) {
    locale.value = nextLocale
    setLocale(nextLocale)
  }

  function openProfile() {
    profileForm.value = {
      full_name: auth.user?.full_name || '',
      avatar_url: auth.user?.avatar_url || '',
    }
    profileOpen.value = true
  }

  function closeProfile() {
    profileOpen.value = false
  }

  async function saveProfile() {
    profileSaving.value = true
    try {
      await auth.updateProfile({
        full_name: profileForm.value.full_name,
        avatar_url: profileForm.value.avatar_url || null,
      })
      showToast(t('layout.profileSaved'), 'success')
      profileOpen.value = false
    } catch (error) {
      showToast(getApiErrorMessage(error, t), 'error')
    } finally {
      profileSaving.value = false
    }
  }

  async function handleLogout() {
    await auth.logout()
    router.push('/login')
  }
</script>

<template>
  <div class="app-shell">
    <div class="mobile-topbar">
      <button
        class="icon-btn"
        @click="mobileMenuOpen = !mobileMenuOpen"
        :aria-label="mobileMenuOpen ? t('ui.closeMenu') : t('ui.openMenu')"
        :aria-expanded="mobileMenuOpen"
      >
        {{ mobileMenuOpen ? '×' : '☰' }}
      </button>
      <div class="mobile-brand">
        <span class="brand-mark">N</span>
        <div>
          <strong>{{ t('app.title') }}</strong>
          <small>{{ t('app.subtitle') }}</small>
        </div>
      </div>
      <button class="profile-pill compact" @click="openProfile">
        <span class="avatar-frame">
          <img
            v-if="avatarUrl"
            :src="avatarUrl"
            :alt="auth.user?.full_name || t('layout.profile')"
          />
          <span v-else>{{ profileInitials }}</span>
        </span>
      </button>
    </div>

    <div v-if="mobileMenuOpen" class="mobile-backdrop" @click="mobileMenuOpen = false"></div>

    <aside class="sidebar" :class="{ 'mobile-open': mobileMenuOpen }">
      <div class="sidebar-brand">
        <div class="brand-mark">N</div>
        <div>
          <strong>{{ t('app.title') }}</strong>
          <small>{{ t('app.subtitle') }}</small>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="Main navigation">
        <RouterLink
          v-for="item in visibleNavItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          @click="mobileMenuOpen = false"
        >
          <span class="nav-icon"><AppIcon :name="item.icon" :size="18" /></span>
          <span class="nav-copy">
            <strong>{{ t(item.label) }}</strong>
          </span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="status-stack">
          <span v-if="versionBadge" class="status-pill">{{ versionBadge }}</span>
          <span class="status-pill muted">{{ userRoleLabel }}</span>
        </div>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="page-meta">
          <h1 class="page-heading">{{ currentTitle }}</h1>
        </div>

        <div class="topbar-actions">
          <div class="segmented-control" role="group" :aria-label="t('layout.language')">
            <button
              class="segmented-btn"
              :class="{ active: locale === 'sl' }"
              @click="changeLocale('sl')"
            >
              SI
            </button>
            <button
              class="segmented-btn"
              :class="{ active: locale === 'en' }"
              @click="changeLocale('en')"
            >
              EN
            </button>
          </div>

          <button class="ghost-btn icon-label-btn" @click="toggleDark">
            <AppIcon :name="isDark ? 'sun' : 'moon'" :size="16" />
            <span>{{ isDark ? t('ui.lightMode') : t('ui.darkMode') }}</span>
          </button>

          <button class="profile-pill" @click="openProfile">
            <span class="avatar-frame">
              <img
                v-if="avatarUrl"
                :src="avatarUrl"
                :alt="auth.user?.full_name || t('layout.profile')"
              />
              <span v-else>{{ profileInitials }}</span>
            </span>
            <span class="profile-copy">
              <strong>{{ auth.user?.full_name || t('layout.profile') }}</strong>
              <small>{{ userRoleLabel }}</small>
            </span>
          </button>

          <button class="danger-soft icon-label-btn" @click="handleLogout">
            <AppIcon name="logout" :size="16" />
            <span>{{ t('nav.logout') }}</span>
          </button>
        </div>
      </header>

      <main class="main">
        <slot />
      </main>
    </div>
  </div>

  <div v-if="profileOpen" class="modal-overlay" @click.self="closeProfile">
    <div class="modal-content profile-modal">
      <div class="profile-header">
        <div>
          <p class="eyebrow">{{ t('layout.profile') }}</p>
          <h2>{{ t('layout.profileTitle') }}</h2>
          <p class="muted">{{ t('layout.profileDescription') }}</p>
        </div>
        <button class="icon-btn subtle" :aria-label="t('common.close')" @click="closeProfile">
          ×
        </button>
      </div>

      <div class="profile-preview">
        <span class="avatar-frame large">
          <img
            v-if="profileAvatarUrl"
            :src="profileAvatarUrl"
            :alt="profileForm.full_name || t('layout.profile')"
          />
          <span v-else>{{ profileInitials }}</span>
        </span>
        <div>
          <strong>{{ profileForm.full_name || t('layout.profilePlaceholder') }}</strong>
          <p class="muted">{{ auth.user?.email }}</p>
        </div>
      </div>

      <div class="form-grid profile-form">
        <div>
          <label class="form-label">{{ t('auth.fullName') }}</label>
          <input v-model="profileForm.full_name" class="form-input" type="text" />
        </div>
        <div>
          <label class="form-label">{{ t('layout.avatarUrl') }}</label>
          <input
            v-model="profileForm.avatar_url"
            class="form-input"
            type="url"
            :placeholder="t('layout.avatarPlaceholder')"
          />
        </div>
      </div>

      <p class="muted">{{ t('layout.avatarHint') }}</p>

      <div class="modal-actions">
        <button class="ghost-btn" @click="closeProfile">{{ t('common.cancel') }}</button>
        <button class="btn btn-primary" :disabled="profileSaving" @click="saveProfile">
          {{ profileSaving ? t('layout.savingProfile') : t('common.save') }}
        </button>
      </div>
    </div>
  </div>
</template>
