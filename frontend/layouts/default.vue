<script setup>
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import ToastStack from '~/components/shell/ToastStack.vue'
  import AppIcon from '~/legacy/components/AppIcon.vue'
  import { viewerNavigation, adminNavigation } from '~/legacy/constants/navigation'
  import { setLocale } from '~/legacy/i18n'
  import { useAuthStore } from '~/legacy/stores/auth'

  const route = useRoute()
  const router = useRouter()
  const runtimeConfig = useRuntimeConfig()
  const { t, locale } = useI18n()
  const auth = useAuthStore()
  const colorMode = useColorMode()
  const mobileNavOpen = ref(false)

  await auth.init()

  const routeMeta = computed(() => {
    const mappings = [
      { match: (path) => path === '/', title: 'nav.dashboard', description: 'layout.page.dashboard' },
      { match: (path) => path === '/napoved', title: 'nav.prediction', description: 'layout.page.prediction' },
      { match: (path) => path === '/zemljevid', title: 'nav.map', description: 'layout.page.map' },
      { match: (path) => path === '/analiza', title: 'nav.analysis', description: 'layout.page.analysis' },
      {
        match: (path) => path.startsWith('/obcine/'),
        title: 'municipality.pageTitle',
        description: 'municipality.pageDescription',
      },
      { match: (path) => path === '/admin', title: 'nav.admin', description: 'layout.page.adminHome' },
      { match: (path) => path === '/admin/podatki', title: 'nav.data', description: 'layout.page.data' },
      {
        match: (path) => path === '/admin/priprava',
        title: 'nav.prepare',
        description: 'layout.page.prepare',
      },
      { match: (path) => path === '/admin/model', title: 'nav.model', description: 'layout.page.model' },
      {
        match: (path) => path === '/admin/diagnostika',
        title: 'nav.diagnostics',
        description: 'layout.page.diagnostics',
      },
      {
        match: (path) => path === '/admin/uporabniki',
        title: 'admin.userManagement',
        description: 'layout.page.adminUsers',
      },
    ]

    return (
      mappings.find((item) => item.match(route.path)) || {
        title: 'app.title',
        description: 'layout.page.default',
      }
    )
  })

  const viewerItems = computed(() => viewerNavigation.map((item) => ({ ...item, label: t(item.label) })))
  const adminItems = computed(() =>
    auth.isAdmin ? adminNavigation.map((item) => ({ ...item, label: t(item.label) })) : [],
  )
  const versionLabel = computed(() =>
    `${locale.value === 'sl' ? 'Verzija' : 'Version'} ${runtimeConfig.public.appVersion}`,
  )
  const roleLabel = computed(() => (auth.isAdmin ? t('layout.roleAdmin') : t('layout.roleViewer')))

  function isActiveRoute(path) {
    if (path === '/' || path === '/admin') return route.path === path
    return route.path === path || route.path.startsWith(`${path}/`)
  }

  function toggleLocale(nextLocale) {
    locale.value = nextLocale
    setLocale(nextLocale)
  }

  function toggleTheme() {
    colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
  }

  async function logout() {
    await auth.logout()
    mobileNavOpen.value = false
    await router.push('/login')
  }
</script>

<template>
  <div class="shell-surface app-shell">
    <ToastStack />

    <div v-if="mobileNavOpen" class="mobile-shell-backdrop" @click="mobileNavOpen = false"></div>

    <aside class="shell-sidebar" :class="{ 'mobile-open': mobileNavOpen }">
      <div class="sidebar-pane">
        <NuxtLink to="/" class="shell-brand">
          <span class="brand-mark">
            <AppIcon name="brand" :size="24" />
          </span>
          <div class="brand-copy">
            <strong>{{ t('app.title') }}</strong>
            <small>{{ t('layout.brandTagline') }}</small>
          </div>
        </NuxtLink>

        <section class="sidebar-nav-group">
          <div class="sidebar-section-label">{{ t('layout.marketWorkspace') }}</div>
          <nav class="shell-nav" :aria-label="t('layout.marketWorkspace')">
            <NuxtLink
              v-for="item in viewerItems"
              :key="item.to"
              :to="item.to"
              class="shell-nav-link"
              :class="{ active: isActiveRoute(item.to) }"
              @click="mobileNavOpen = false"
            >
              <span class="shell-nav-icon">
                <AppIcon :name="item.icon" :size="18" />
              </span>
              <span class="shell-nav-copy">
                <strong>{{ item.label }}</strong>
              </span>
            </NuxtLink>
          </nav>
        </section>

        <section v-if="adminItems.length" class="sidebar-nav-group">
          <div class="sidebar-section-label">{{ t('layout.adminWorkbench') }}</div>
          <nav class="shell-nav" :aria-label="t('layout.adminWorkbench')">
            <NuxtLink
              v-for="item in adminItems"
              :key="item.to"
              :to="item.to"
              class="shell-nav-link"
              :class="{ active: isActiveRoute(item.to) }"
              @click="mobileNavOpen = false"
            >
              <span class="shell-nav-icon">
                <AppIcon :name="item.icon" :size="18" />
              </span>
              <span class="shell-nav-copy">
                <strong>{{ item.label }}</strong>
              </span>
            </NuxtLink>
          </nav>
        </section>
      </div>
    </aside>

    <div class="shell-workspace">
      <header class="shell-topbar">
        <div class="shell-topbar-inner">
          <div class="shell-heading-row">
            <div class="shell-heading-main">
              <button
                type="button"
                class="shell-icon-button lg:hidden"
                @click="mobileNavOpen = true"
              >
                <span class="sr-only">Open navigation</span>
                <span class="menu-lines">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              </button>

              <div class="page-meta">
                <h1 class="page-heading">{{ t(routeMeta.title) }}</h1>
              </div>
            </div>

            <div class="shell-header-actions">
              <div class="shell-segmented" :aria-label="t('layout.language')">
                <button
                  type="button"
                  class="shell-segmented-option"
                  :class="{ active: locale === 'sl' }"
                  @click="toggleLocale('sl')"
                >
                  SL
                </button>
                <button
                  type="button"
                  class="shell-segmented-option"
                  :class="{ active: locale === 'en' }"
                  @click="toggleLocale('en')"
                >
                  EN
                </button>
              </div>

              <button
                type="button"
                class="shell-icon-button"
                :aria-label="colorMode.value === 'dark' ? t('ui.lightMode') : t('ui.darkMode')"
                @click="toggleTheme"
              >
                <AppIcon :name="colorMode.value === 'dark' ? 'sun' : 'moon'" :size="16" />
              </button>

              <div class="profile-pill">
                <span class="profile-avatar">
                  {{ (auth.user?.full_name || t('layout.profile')).slice(0, 1).toUpperCase() }}
                </span>
                <span class="profile-copy">
                  <strong>{{ auth.user?.full_name || t('layout.profile') }}</strong>
                  <small>{{ roleLabel }}</small>
                </span>
              </div>

              <UButton color="neutral" variant="soft" size="lg" @click="logout">
                {{ t('nav.logout') }}
              </UButton>
            </div>
          </div>
        </div>
      </header>

      <main class="shell-main">
        <slot />
      </main>

      <footer class="shell-footer-bar">
        <div class="shell-footer-inner">
          <div class="footer-copy">Copyright Michel Velkov 2026</div>
          <div class="footer-version">{{ versionLabel }}</div>
        </div>
      </footer>
    </div>
  </div>
</template>
