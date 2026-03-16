<script setup>
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { setLocale } from '../i18n'
  import { adminNavigation, viewerNavigation } from '../constants/navigation'
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
  const sidebarCollapsed = ref(localStorage.getItem('sidebar_collapsed') === '1')
  const profileForm = ref({
    full_name: '',
    avatar_url: '',
  })

  const isAdminArea = computed(() => route.path.startsWith('/admin'))
  const currentNavItems = computed(() => (isAdminArea.value ? adminNavigation : viewerNavigation))
  const shellStyle = computed(() => ({
    '--sidebar-width': sidebarCollapsed.value ? '5.75rem' : '17.5rem',
  }))

  const currentItem = computed(
    () =>
      currentNavItems.value.find((item) => isActiveRoute(item)) ||
      currentNavItems.value[0] ||
      viewerNavigation[0],
  )

  const currentTitle = computed(() =>
    route.meta.titleKey
      ? t(route.meta.titleKey)
      : currentItem.value
        ? t(currentItem.value.label)
        : t('app.title'),
  )

  const currentDescription = computed(() =>
    route.meta.descriptionKey ? t(route.meta.descriptionKey) : t('layout.page.default'),
  )

  const workspaceLabel = computed(() =>
    isAdminArea.value ? t('layout.adminWorkbench') : t('layout.marketWorkspace'),
  )

  const workspaceTag = computed(() =>
    isAdminArea.value ? t('layout.adminWorkbenchShort') : t('layout.marketWorkspaceShort'),
  )

  const switchLink = computed(() => {
    if (!auth.isAdmin) return null

    return isAdminArea.value
      ? {
          to: '/',
          icon: 'dashboard',
          label: t('layout.backToMarket'),
        }
      : {
          to: '/admin',
          icon: 'admin',
          label: t('layout.openAdminWorkbench'),
        }
  })

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

  watch(sidebarCollapsed, (collapsed) => {
    localStorage.setItem('sidebar_collapsed', collapsed ? '1' : '0')
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

  watch(
    () => route.fullPath,
    () => {
      mobileMenuOpen.value = false
    },
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

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
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

  function isActiveRoute(item) {
    if (item.to === '/' || item.to === '/admin') return route.path === item.to
    return route.path === item.to || route.path.startsWith(`${item.to}/`)
  }
</script>

<template>
  <div class="app-shell" :style="shellStyle" :class="{ collapsed: sidebarCollapsed }">
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
        <span class="brand-mark">NN</span>
        <div>
          <strong>{{ t('app.title') }}</strong>
          <small>{{ workspaceTag }}</small>
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

    <aside class="sidebar" :class="{ 'mobile-open': mobileMenuOpen, collapsed: sidebarCollapsed }">
      <div class="sidebar-top">
        <div class="sidebar-brand">
          <div class="brand-mark">NN</div>
          <div class="brand-copy">
            <strong>{{ t('app.title') }}</strong>
            <small>{{ workspaceTag }}</small>
          </div>
        </div>

        <button class="icon-btn subtle desktop-only" @click="toggleSidebar">
          {{ sidebarCollapsed ? '→' : '←' }}
        </button>
      </div>

      <div class="sidebar-rail-label">
        <span class="sidebar-label">{{ workspaceTag }}</span>
      </div>

      <nav class="sidebar-nav" :aria-label="t('layout.navigation')">
        <RouterLink
          v-for="item in currentNavItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: isActiveRoute(item) }"
        >
          <span class="nav-icon"><AppIcon :name="item.icon" :size="18" /></span>
          <span class="nav-copy">
            <strong>{{ t(item.label) }}</strong>
          </span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <RouterLink v-if="switchLink" :to="switchLink.to" class="switch-link">
          <AppIcon :name="switchLink.icon" :size="16" />
          <span>{{ switchLink.label }}</span>
        </RouterLink>

        <div class="status-stack">
          <span class="status-pill muted">{{ userRoleLabel }}</span>
          <span v-if="versionBadge" class="status-pill">{{ versionBadge }}</span>
        </div>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="page-meta">
          <span class="page-kicker">{{ workspaceLabel }}</span>
          <h1 class="page-heading">{{ currentTitle }}</h1>
          <p class="page-description">{{ currentDescription }}</p>
        </div>

        <div class="topbar-actions">
          <RouterLink v-if="switchLink" :to="switchLink.to" class="switch-link mobile-switch">
            <AppIcon :name="switchLink.icon" :size="16" />
            <span>{{ switchLink.label }}</span>
          </RouterLink>

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

<style scoped>
  .sidebar {
    overflow-y: auto;
    transition:
      width 160ms ease,
      transform 180ms ease;
  }

  .sidebar-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .sidebar-brand {
    min-width: 0;
  }

  .brand-copy {
    display: grid;
    gap: 0.15rem;
  }

  .sidebar-rail-label {
    min-height: 1rem;
  }

  .sidebar-label {
    color: rgb(255 255 255 / 44%);
  }

  .nav-link.active {
    background: linear-gradient(135deg, rgb(16 185 129 / 22%), rgb(255 255 255 / 8%));
    border-color: rgb(16 185 129 / 24%);
    color: #f8fbff;
  }

  .sidebar-footer {
    display: grid;
    gap: 0.6rem;
    padding-top: 0.15rem;
  }

  .switch-link {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.82rem 0.9rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    text-decoration: none;
    font-weight: 700;
  }

  .switch-link:hover {
    border-color: rgb(16 185 129 / 32%);
  }

  .sidebar-meta {
    display: grid;
    gap: 0.18rem;
    padding: 0 0.15rem;
    color: rgb(255 255 255 / 60%);
  }

  .sidebar-meta small {
    font-size: 0.8rem;
  }

  .sidebar-version {
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .mobile-switch {
    display: none;
  }

  .workspace {
    position: relative;
    min-height: 100vh;
  }

  .workspace::before {
    content: '';
    position: fixed;
    inset: 0 0 auto var(--sidebar-width);
    height: 220px;
    background:
      radial-gradient(circle at top left, rgb(16 185 129 / 10%), transparent 32%),
      radial-gradient(circle at top right, rgb(245 158 11 / 8%), transparent 24%);
    pointer-events: none;
    z-index: 0;
  }

  .topbar {
    position: sticky;
    top: 0;
    z-index: 12;
    margin: 0 1.35rem;
    padding: 1rem 0 0.95rem;
    backdrop-filter: blur(18px);
  }

  .page-meta,
  .profile-copy {
    display: grid;
    gap: 0.2rem;
  }

  .page-kicker {
    color: var(--text-soft);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }

  .page-description {
    max-width: 56ch;
    margin: 0;
    color: var(--text-muted);
    font-size: 0.92rem;
  }

  .main {
    position: relative;
    z-index: 1;
    padding-top: 0.4rem;
  }

  .desktop-only {
    display: inline-flex;
  }

  .collapsed .brand-copy,
  .collapsed .nav-copy,
  .collapsed .switch-link span,
  .collapsed .sidebar-rail-label,
  .collapsed .sidebar-meta {
    display: none;
  }

  .collapsed .sidebar-top {
    justify-content: center;
  }

  .collapsed .switch-link {
    justify-content: center;
    padding-inline: 0.6rem;
  }

  @media (max-width: 960px) {
    .workspace::before {
      inset: 0;
    }

    .topbar {
      margin: 0 1rem;
    }

    .page-description {
      max-width: none;
    }

    .mobile-switch {
      display: inline-flex;
    }

    .desktop-only {
      display: none;
    }

    .sidebar.collapsed .brand-copy,
    .sidebar.collapsed .nav-copy,
    .sidebar.collapsed .switch-link span,
    .sidebar.collapsed .sidebar-rail-label,
    .sidebar.collapsed .sidebar-meta {
      display: initial;
    }
  }
</style>
