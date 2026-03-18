<script setup lang="ts">
  import { useWindowSize, useLocalStorage } from '@vueuse/core'

  // ─── Stores & composables ────────────────────────────────────────────────────
  const auth = useAuthStore()
  const route = useRoute()
  const { t, locale, setLocale } = useI18n()
  const colorMode = useColorMode()
  const runtimeConfig = useRuntimeConfig()

  // ─── Sidebar collapse: persistent via localStorage, auto-collapse on mobile ──
  const sidebarCollapsed = useLocalStorage<boolean>('sidebar-collapsed', false)
  const mobileNavOpen = ref(false)

  const { width } = useWindowSize()

  watch(
    width,
    (w) => {
      if (w < 1024) {
        sidebarCollapsed.value = true
        mobileNavOpen.value = false
      }
    },
    { immediate: false },
  )

  // ─── Navigation definitions ──────────────────────────────────────────────────
  const viewerNav = computed(() => [
    {
      to: '/',
      icon: 'i-lucide-layout-dashboard',
      label: t('nav.dashboard'),
      short: t('layout.short.dashboard'),
    },
    {
      to: '/napoved',
      icon: 'i-lucide-zap',
      label: t('nav.prediction'),
      short: t('layout.short.prediction'),
    },
    { to: '/zemljevid', icon: 'i-lucide-map', label: t('nav.map'), short: t('layout.short.map') },
    {
      to: '/analiza',
      icon: 'i-lucide-bar-chart-2',
      label: t('nav.analysis'),
      short: t('layout.short.analysis'),
    },
  ])

  const adminNav = computed(() =>
    auth.isAdmin
      ? [
          {
            to: '/admin',
            icon: 'i-lucide-home',
            label: t('nav.admin'),
            short: t('layout.short.admin'),
          },
          {
            to: '/admin/podatki',
            icon: 'i-lucide-database',
            label: t('nav.data'),
            short: t('layout.short.data'),
          },
          {
            to: '/admin/priprava',
            icon: 'i-lucide-file-cog',
            label: t('nav.prepare'),
            short: t('layout.short.prepare'),
          },
          {
            to: '/admin/model',
            icon: 'i-lucide-brain',
            label: t('nav.model'),
            short: t('layout.short.model'),
          },
          {
            to: '/admin/diagnostika',
            icon: 'i-lucide-activity',
            label: t('nav.diagnostics'),
            short: t('layout.short.diagnostics'),
          },
          {
            to: '/admin/uporabniki',
            icon: 'i-lucide-users',
            label: t('admin.userManagement', 'Users'),
            short: t('admin.userManagement', 'Users'),
          },
        ]
      : [],
  )

  // ─── Active route detection ──────────────────────────────────────────────────
  function isActive(to: string): boolean {
    if (to === '/' || to === '/admin') return route.path === to
    return route.path === to || route.path.startsWith(`${to}/`)
  }

  // ─── Page title mapping ───────────────────────────────────────────────────────
  const routeTitle = computed<string>(() => {
    const path = route.path
    const map: Array<{ match: (p: string) => boolean; key: string }> = [
      { match: (p) => p === '/', key: 'nav.dashboard' },
      { match: (p) => p === '/napoved', key: 'nav.prediction' },
      { match: (p) => p === '/zemljevid', key: 'nav.map' },
      { match: (p) => p === '/analiza', key: 'nav.analysis' },
      { match: (p) => p.startsWith('/obcine/'), key: 'municipality.pageTitle' },
      { match: (p) => p === '/admin', key: 'nav.admin' },
      { match: (p) => p === '/admin/podatki', key: 'nav.data' },
      { match: (p) => p === '/admin/priprava', key: 'nav.prepare' },
      { match: (p) => p === '/admin/model', key: 'nav.model' },
      { match: (p) => p === '/admin/diagnostika', key: 'nav.diagnostics' },
      { match: (p) => p === '/admin/uporabniki', key: 'admin.userManagement' },
    ]
    return t(map.find((m) => m.match(path))?.key ?? 'app.title')
  })

  // ─── User info ───────────────────────────────────────────────────────────────
  const userDisplayName = computed<string>(
    () => auth.user?.full_name || auth.user?.email || t('layout.profile'),
  )

  const userInitials = computed<string>(() => {
    const name = auth.user?.full_name || auth.user?.email || '?'
    return name
      .split(/[\s@._-]+/)
      .map((n: string) => n[0] ?? '')
      .join('')
      .toUpperCase()
      .slice(0, 2)
  })

  const roleLabel = computed<string>(() =>
    auth.isAdmin ? t('layout.roleAdmin') : t('layout.roleViewer'),
  )

  const versionLabel = computed<string>(() => `v${runtimeConfig.public.appVersion}`)

  // ─── Theme & locale ──────────────────────────────────────────────────────────
  const isDark = computed(() => colorMode.value === 'dark')

  function toggleTheme(): void {
    colorMode.preference = isDark.value ? 'light' : 'dark'
  }

  // ─── Profile dialog state ─────────────────────────────────────────────────────
  const toast = useToast()
  const profileOpen = ref(false)
  const profileName = ref(auth.user?.full_name ?? '')
  const profileSaving = ref(false)

  async function saveProfile(): Promise<void> {
    profileSaving.value = true
    try {
      await auth.updateProfile({ full_name: profileName.value })
      profileOpen.value = false
      toast.add({
        title: t('layout.profileSaved'),
        color: 'success',
        icon: 'i-lucide-check-circle',
      })
    } finally {
      profileSaving.value = false
    }
  }

  // ─── Dropdown menu items ──────────────────────────────────────────────────────
  const userMenuItems = computed(() => [
    [
      {
        label: t('layout.profile'),
        icon: 'i-lucide-user',
        onSelect() {
          profileName.value = auth.user?.full_name ?? ''
          setTimeout(() => {
            profileOpen.value = true
          }, 150)
        },
      },
    ],
    [
      {
        label: locale.value === 'sl' ? 'English' : 'Slovenščina',
        icon: 'i-lucide-languages',
        onSelect() {
          const next = locale.value === 'sl' ? 'en' : 'sl'
          setLocale(next)
        },
      },
      {
        label: isDark.value ? t('ui.lightMode', 'Light mode') : t('ui.darkMode', 'Dark mode'),
        icon: isDark.value ? 'i-lucide-sun' : 'i-lucide-moon',
        onSelect: toggleTheme,
      },
    ],
    [
      {
        label: t('nav.logout'),
        icon: 'i-lucide-log-out',
        color: 'error' as const,
        async onSelect() {
          await auth.logout()
          await navigateTo('/login')
        },
      },
    ],
  ])

  // ─── Mobile nav close on route change ────────────────────────────────────────
  watch(
    () => route.path,
    () => {
      mobileNavOpen.value = false
    },
  )
</script>

<template>
  <div class="shell-surface app-shell" :class="{ 'sidebar-is-collapsed': sidebarCollapsed }">
    <!-- Mobile backdrop -->
    <Transition name="backdrop-fade">
      <div v-if="mobileNavOpen" class="mobile-shell-backdrop" @click="mobileNavOpen = false" />
    </Transition>

    <!-- ─── Sidebar ─────────────────────────────────────────────── -->
    <aside
      class="shell-sidebar"
      :class="{ 'mobile-open': mobileNavOpen }"
      :aria-label="t('layout.navigation', 'Navigation')"
    >
      <div class="sidebar-pane">
        <!-- Brand mark -->
        <NuxtLink to="/" class="shell-brand" @click="mobileNavOpen = false">
          <span class="brand-mark" aria-hidden="true">
            <UIcon name="i-lucide-building-2" class="size-6" />
          </span>
          <Transition name="copy-fade">
            <div v-if="!sidebarCollapsed" class="brand-copy">
              <strong>{{ t('app.title') }}</strong>
              <small>{{ t('layout.brandTagline') }}</small>
            </div>
          </Transition>
        </NuxtLink>

        <!-- Market workspace nav -->
        <section class="sidebar-nav-group">
          <div v-if="!sidebarCollapsed" class="sidebar-section-label">
            {{ t('layout.marketWorkspace') }}
          </div>

          <nav class="shell-nav" :aria-label="t('layout.marketWorkspace')">
            <NuxtLink
              v-for="item in viewerNav"
              :key="item.to"
              :to="item.to"
              class="shell-nav-link"
              :class="{ active: isActive(item.to) }"
              :aria-current="isActive(item.to) ? 'page' : undefined"
              :title="sidebarCollapsed ? item.label : undefined"
              @click="mobileNavOpen = false"
            >
              <span class="shell-nav-icon" aria-hidden="true">
                <UIcon :name="item.icon" class="size-[18px]" />
              </span>
              <Transition name="copy-fade">
                <span v-if="!sidebarCollapsed" class="shell-nav-copy">
                  <strong>{{ item.label }}</strong>
                </span>
              </Transition>
            </NuxtLink>
          </nav>
        </section>

        <!-- Admin workbench nav -->
        <section v-if="adminNav.length" class="sidebar-nav-group">
          <div v-if="!sidebarCollapsed" class="sidebar-section-label">
            {{ t('layout.adminWorkbench') }}
          </div>

          <nav class="shell-nav" :aria-label="t('layout.adminWorkbench')">
            <NuxtLink
              v-for="item in adminNav"
              :key="item.to"
              :to="item.to"
              class="shell-nav-link"
              :class="{ active: isActive(item.to) }"
              :aria-current="isActive(item.to) ? 'page' : undefined"
              :title="sidebarCollapsed ? item.label : undefined"
              @click="mobileNavOpen = false"
            >
              <span class="shell-nav-icon" aria-hidden="true">
                <UIcon :name="item.icon" class="size-[18px]" />
              </span>
              <Transition name="copy-fade">
                <span v-if="!sidebarCollapsed" class="shell-nav-copy">
                  <strong>{{ item.label }}</strong>
                </span>
              </Transition>
            </NuxtLink>
          </nav>
        </section>

        <!-- Spacer -->
        <div class="flex-1" />

        <!-- Collapse toggle (desktop only) -->
        <button
          type="button"
          class="shell-nav-link sidebar-collapse-btn"
          :title="sidebarCollapsed ? t('layout.expandSidebar') : t('layout.collapseSidebar')"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <span class="shell-nav-icon" aria-hidden="true">
            <UIcon
              :name="sidebarCollapsed ? 'i-lucide-panel-left-open' : 'i-lucide-panel-left-close'"
              class="size-[18px]"
            />
          </span>
          <Transition name="copy-fade">
            <span v-if="!sidebarCollapsed" class="shell-nav-copy">
              <strong>{{ t('layout.collapseSidebar') }}</strong>
            </span>
          </Transition>
        </button>
      </div>
    </aside>

    <!-- ─── Main workspace ──────────────────────────────────────── -->
    <div class="shell-workspace">
      <!-- Topbar -->
      <header class="shell-topbar">
        <div class="shell-topbar-inner">
          <div class="shell-heading-row">
            <!-- Left: hamburger (mobile) + page title -->
            <div class="shell-heading-main">
              <button
                type="button"
                class="shell-icon-button hamburger-btn"
                :aria-label="t('layout.navigation', 'Open navigation')"
                @click="mobileNavOpen = true"
              >
                <span class="menu-lines" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
              </button>

              <div class="page-meta">
                <h1 class="page-heading">{{ routeTitle }}</h1>
              </div>
            </div>

            <!-- Right: actions -->
            <div class="shell-header-actions">
              <!-- Language segmented control -->
              <div class="shell-segmented" :aria-label="t('layout.language')">
                <button
                  type="button"
                  class="shell-segmented-option"
                  :class="{ active: locale === 'sl' }"
                  @click="setLocale('sl')"
                >
                  SL
                </button>
                <button
                  type="button"
                  class="shell-segmented-option"
                  :class="{ active: locale === 'en' }"
                  @click="setLocale('en')"
                >
                  EN
                </button>
              </div>

              <!-- Theme toggle -->
              <button
                type="button"
                class="shell-icon-button"
                :aria-label="
                  isDark ? t('ui.lightMode', 'Light mode') : t('ui.darkMode', 'Dark mode')
                "
                @click="toggleTheme"
              >
                <UIcon :name="isDark ? 'i-lucide-sun' : 'i-lucide-moon'" class="size-4" />
              </button>

              <!-- User profile dropdown -->
              <UDropdownMenu :items="userMenuItems" :ui="{ content: 'w-52' }">
                <button type="button" class="profile-pill" :aria-label="userDisplayName">
                  <UAvatar
                    :src="auth.user?.avatar_url ?? undefined"
                    :alt="userDisplayName"
                    :text="userInitials"
                    size="xs"
                    class="profile-avatar"
                  />
                  <span class="profile-copy">
                    <strong>{{ userDisplayName }}</strong>
                    <small>{{ roleLabel }}</small>
                  </span>
                  <UIcon name="i-lucide-chevron-down" class="size-3.5 text-(--ui-text-muted)" />
                </button>
              </UDropdownMenu>
            </div>
          </div>
        </div>
      </header>

      <!-- Page slot -->
      <main class="shell-main">
        <slot />
      </main>

      <!-- Footer -->
      <footer class="shell-footer-bar">
        <div class="shell-footer-inner">
          <div class="footer-copy">Copyright Michel Velkov 2026</div>
          <div class="footer-version">{{ versionLabel }}</div>
        </div>
      </footer>
    </div>

    <!-- ─── Profile modal ──────────────────────────────────────── -->
    <UModal
      v-model:open="profileOpen"
      :title="t('layout.profileTitle')"
      :description="t('layout.profileDescription')"
    >
      <template #body>
        <form class="auth-form" @submit.prevent="saveProfile">
          <div class="field">
            <label for="profile-name" class="form-label">{{ t('layout.profile') }}</label>
            <UInput
              id="profile-name"
              v-model="profileName"
              type="text"
              :placeholder="t('layout.profilePlaceholder')"
              size="lg"
            />
          </div>

          <div class="actions-row">
            <UButton
              type="submit"
              color="primary"
              :loading="profileSaving"
              :disabled="profileSaving"
              icon="i-lucide-check"
            >
              {{ profileSaving ? t('layout.savingProfile') : t('auth.loginButton', 'Save') }}
            </UButton>
            <UButton type="button" color="neutral" variant="soft" @click="profileOpen = false">
              {{ t('auth.cancel', 'Cancel') }}
            </UButton>
          </div>
        </form>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
  /* ── Collapsed sidebar ────────────────────────────────────────────────────── */
  .sidebar-is-collapsed .shell-sidebar {
    --sidebar-width: 5rem;
  }

  .sidebar-is-collapsed .shell-sidebar .sidebar-pane {
    align-items: center;
  }

  .sidebar-is-collapsed .shell-sidebar .shell-brand {
    justify-content: center;
  }

  .sidebar-is-collapsed .shell-sidebar .shell-nav-link {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
  }

  .sidebar-is-collapsed .shell-sidebar .sidebar-collapse-btn {
    justify-content: center;
    padding-left: 0;
    padding-right: 0;
  }

  .sidebar-is-collapsed .shell-sidebar .sidebar-section-label {
    display: none;
  }

  /* ── Hamburger: visible only on mobile (<1024px) ────────────────────────── */
  .hamburger-btn {
    display: inline-flex;
  }

  @media (min-width: 1024px) {
    .hamburger-btn {
      display: none;
    }
  }

  /* ── Sidebar collapse button: visible only on desktop (>=1024px) ────────── */
  .sidebar-collapse-btn {
    display: none;
    margin-top: 0;
    opacity: 0.7;
  }

  @media (min-width: 1024px) {
    .sidebar-collapse-btn {
      display: flex;
    }
  }

  .sidebar-collapse-btn:hover {
    opacity: 1;
  }

  /* ── Copy fade transition ─────────────────────────────────────────────────── */
  .copy-fade-enter-active,
  .copy-fade-leave-active {
    transition:
      opacity 140ms ease,
      width 220ms ease;
    overflow: hidden;
  }

  .copy-fade-enter-from,
  .copy-fade-leave-to {
    opacity: 0;
    width: 0;
  }

  .copy-fade-enter-to,
  .copy-fade-leave-from {
    opacity: 1;
  }

  /* ── Backdrop fade transition ─────────────────────────────────────────────── */
  .backdrop-fade-enter-active,
  .backdrop-fade-leave-active {
    transition: opacity 200ms ease;
  }

  .backdrop-fade-enter-from,
  .backdrop-fade-leave-to {
    opacity: 0;
  }
</style>
