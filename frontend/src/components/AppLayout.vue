<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { useLocalStorage, useWindowScroll } from '@vueuse/core'
  import { setLocale } from '../i18n'
  import { adminNavigation, viewerNavigation } from '../constants/navigation'
  import type { NavItem } from '../constants/navigation'
  import AppIcon from './AppIcon.vue'
  import AppSidebar from './layout/AppSidebar.vue'
  import ProfileDialog from './layout/ProfileDialog.vue'
  import { useDarkMode } from '../composables/useDarkMode'
  import { useAuthStore } from '../stores/auth'

  const { t, locale } = useI18n()
  const auth = useAuthStore()
  const route = useRoute()
  const router = useRouter()
  const { isDark, toggleDark } = useDarkMode()

  const { y: scrollY } = useWindowScroll()
  const isScrolled = computed(() => scrollY.value > 16)

  const mobileMenuOpen = ref(false)
  const profileOpen = ref(false)
  const appVersion = ref('')
  const sidebarCollapsed = useLocalStorage('sidebar_collapsed', false)

  const isAdminArea = computed(() => route.path.startsWith('/admin'))
  const currentNavItems = computed(() => (isAdminArea.value ? adminNavigation : viewerNavigation))
  const shellStyle = computed(() => ({
    '--sidebar-width': sidebarCollapsed.value ? '5.4rem' : '16.8rem',
  }))

  const currentItem = computed(
    () =>
      currentNavItems.value.find((item) => isActiveRoute(item)) ||
      currentNavItems.value[0] ||
      viewerNavigation[0],
  )

  const currentTitle = computed(() =>
    route.meta.titleKey
      ? t(route.meta.titleKey as string)
      : currentItem.value
        ? t(currentItem.value.label)
        : t('app.title'),
  )

  const currentDescription = computed(() =>
    route.meta.descriptionKey ? t(route.meta.descriptionKey as string) : t('layout.page.default'),
  )

  const workspaceLabel = computed(() =>
    isAdminArea.value ? t('layout.adminWorkbench') : t('layout.marketWorkspace'),
  )

  const workspaceTag = computed(() =>
    isAdminArea.value ? t('layout.adminWorkbenchShort') : t('layout.marketWorkspaceShort'),
  )

  const footerSummary = computed(() =>
    isAdminArea.value ? t('layout.footerAdminSummary') : t('layout.footerViewerSummary'),
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

  const userRoleLabel = computed(() =>
    auth.isAdmin ? t('layout.roleAdmin') : t('layout.roleViewer'),
  )

  const versionBadge = computed(() =>
    appVersion.value ? t('layout.versionBadge', { version: appVersion.value }) : '',
  )

  const localeOptions = computed(() => [
    { label: 'SL', value: 'sl' },
    { label: 'EN', value: 'en' },
  ])

  const localeChoice = computed({
    get: () => locale.value,
    set: (nextLocale: string) => changeLocale(nextLocale),
  })

  const profileInitials = computed(() => {
    const source = auth.user?.full_name || ''
    if (!source.trim()) return '?'
    return source
      .split(' ')
      .map((part: string) => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  })

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

  function changeLocale(nextLocale: string) {
    if (!nextLocale || nextLocale === locale.value) return
    locale.value = nextLocale
    setLocale(nextLocale)
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function openProfile() {
    profileOpen.value = true
  }

  async function handleLogout() {
    await auth.logout()
    router.push('/login')
  }

  function isActiveRoute(item: NavItem): boolean {
    if (item.to === '/' || item.to === '/admin') return route.path === item.to
    return route.path === item.to || route.path.startsWith(`${item.to}/`)
  }
</script>

<template>
  <div class="app-shell" :style="shellStyle" :class="{ collapsed: sidebarCollapsed }">
    <!-- Mobile Top Bar -->
    <div class="mobile-shell-bar">
      <Button
        class="shell-icon-button mobile-menu-button"
        text
        rounded
        @click="mobileMenuOpen = !mobileMenuOpen"
        :aria-label="mobileMenuOpen ? t('ui.closeMenu') : t('ui.openMenu')"
        :aria-expanded="mobileMenuOpen"
      >
        <i :class="mobileMenuOpen ? 'pi pi-times' : 'pi pi-bars'" aria-hidden="true"></i>
      </Button>

      <RouterLink to="/" class="shell-brand shell-brand-mobile">
        <span class="brand-mark">
          <AppIcon name="brand" :size="22" :stroke="1.9" />
        </span>
        <div class="brand-copy">
          <strong>{{ t('app.title') }}</strong>
          <small>{{ t('layout.brandTagline') }}</small>
        </div>
      </RouterLink>

      <Button class="profile-trigger compact" text rounded @click="openProfile">
        <span class="avatar-frame">
          <img
            v-if="avatarUrl"
            :src="avatarUrl"
            :alt="auth.user?.full_name || t('layout.profile')"
          />
          <span v-else>{{ profileInitials }}</span>
        </span>
      </Button>
    </div>

    <div v-if="mobileMenuOpen" class="mobile-shell-backdrop" @click="mobileMenuOpen = false"></div>

    <!-- Sidebar -->
    <AppSidebar
      :nav-items="currentNavItems"
      :collapsed="sidebarCollapsed"
      :mobile-open="mobileMenuOpen"
      :workspace-label="workspaceLabel"
      :footer-summary="footerSummary"
      :switch-link="switchLink"
      :is-active-route="isActiveRoute"
    />

    <!-- Main Workspace -->
    <div class="shell-workspace">
      <header class="shell-topbar" :class="{ scrolled: isScrolled }">
        <div class="shell-topbar-inner">
          <div class="shell-heading-row">
            <div class="shell-heading-main">
              <Button
                class="shell-icon-button desktop-sidebar-toggle"
                text
                rounded
                @click="toggleSidebar"
                :aria-label="
                  sidebarCollapsed ? t('layout.expandSidebar') : t('layout.collapseSidebar')
                "
                v-tooltip.bottom="
                  sidebarCollapsed ? t('layout.expandSidebar') : t('layout.collapseSidebar')
                "
              >
                <i
                  :class="sidebarCollapsed ? 'pi pi-angle-double-right' : 'pi pi-angle-double-left'"
                  aria-hidden="true"
                ></i>
              </Button>

              <div class="page-meta">
                <div class="page-meta-row">
                  <span class="page-kicker">{{ workspaceLabel }}</span>
                </div>
                <h1 class="page-heading">{{ currentTitle }}</h1>
                <p class="page-description">{{ currentDescription }}</p>
              </div>
            </div>

            <div class="shell-header-actions">
              <RouterLink v-if="switchLink" :to="switchLink.to" class="shell-link-pill">
                <AppIcon :name="switchLink.icon" :size="16" />
                <span>{{ switchLink.label }}</span>
              </RouterLink>

              <SelectButton
                v-model="localeChoice"
                :options="localeOptions"
                option-label="label"
                option-value="value"
                :allow-empty="false"
                class="language-toggle"
                :aria-label="t('layout.language')"
              />

              <Button
                class="shell-action-button"
                rounded
                @click="() => toggleDark()"
                :aria-label="isDark ? t('ui.lightMode') : t('ui.darkMode')"
              >
                <AppIcon :name="isDark ? 'sun' : 'moon'" :size="16" />
                <span>{{ isDark ? t('ui.lightMode') : t('ui.darkMode') }}</span>
              </Button>

              <Button class="profile-trigger" rounded @click="openProfile">
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
              </Button>

              <Button class="logout-button" outlined rounded @click="handleLogout">
                <AppIcon name="logout" :size="16" />
                <span>{{ t('nav.logout') }}</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main id="main-content" class="shell-main">
        <div class="workspace-stage">
          <div class="workspace-stage__inner">
            <slot />
          </div>
        </div>
      </main>

      <footer class="shell-footer-bar">
        <div class="shell-footer-inner">
          <div class="footer-brand-block">
            <span class="brand-mark footer-brand-mark">
              <AppIcon name="brand" :size="18" :stroke="1.95" />
            </span>
            <div>
              <strong>{{ t('app.title') }}</strong>
              <p>{{ t('app.subtitle') }}</p>
            </div>
          </div>

          <p class="footer-summary">{{ footerSummary }}</p>

          <div class="footer-meta">
            <Tag :value="workspaceTag" severity="contrast" rounded />
            <Tag :value="userRoleLabel" severity="secondary" rounded />
            <Tag v-if="versionBadge" :value="versionBadge" rounded />
          </div>
        </div>
      </footer>
    </div>
  </div>

  <!-- Profile Dialog -->
  <ProfileDialog v-model:visible="profileOpen" />
</template>

<style scoped>
  .shell-workspace {
    min-width: 0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    position: relative;
  }

  .shell-workspace::before {
    content: '';
    position: fixed;
    inset: 0 0 auto var(--sidebar-width);
    height: 16rem;
    background:
      radial-gradient(circle at top left, var(--shell-ambient-start), transparent 34%),
      radial-gradient(circle at top right, var(--shell-ambient-end), transparent 28%);
    pointer-events: none;
    z-index: 0;
  }

  .shell-topbar,
  .shell-footer-bar {
    position: relative;
    z-index: 5;
    width: 100%;
    background: var(--shell-chrome-bg);
    color: var(--shell-text);
  }

  .shell-topbar {
    position: sticky;
    top: 0;
    border-bottom: 1px solid var(--shell-chrome-border);
    box-shadow: inset 0 1px 0 var(--shell-highlight);
    transition:
      box-shadow 160ms ease,
      backdrop-filter 160ms ease;
  }

  .shell-topbar.scrolled {
    box-shadow: var(--shell-topbar-shadow);
    backdrop-filter: blur(16px);
  }

  .shell-topbar-inner,
  .shell-footer-inner {
    width: 100%;
    padding: 0.9rem 1.25rem;
  }

  .shell-heading-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .shell-heading-main {
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
    min-width: 0;
  }

  .page-meta {
    min-width: 0;
    display: grid;
    gap: 0.22rem;
  }

  .page-meta-row {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  .page-kicker {
    color: var(--shell-text-muted);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .page-heading {
    margin: 0;
    color: var(--shell-text);
    font-family: var(--font-display);
    font-size: clamp(1.28rem, 2vw, 1.72rem);
    line-height: 1.04;
    letter-spacing: -0.03em;
  }

  .page-description {
    margin: 0;
    max-width: 62ch;
    color: var(--shell-text-soft);
    font-size: 0.84rem;
  }

  .shell-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  .shell-link-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 0.82rem;
    border-radius: 999px;
    text-decoration: none;
    font-weight: 700;
    font-size: 0.83rem;
    color: var(--shell-text);
    background: var(--shell-control-bg);
    border: 1px solid var(--shell-control-border);
    box-shadow: inset 0 1px 0 var(--shell-highlight);
  }

  .shell-main {
    position: relative;
    z-index: 1;
    flex: 1;
    padding: 1.2rem 1.35rem 1.8rem;
  }

  .workspace-stage {
    position: relative;
    width: min(100%, 1600px);
    margin: 0 auto;
    min-height: 100%;
  }

  .workspace-stage::before {
    content: '';
    position: absolute;
    inset: 0.4rem 0 auto;
    height: 8rem;
    border-radius: 2rem;
    background:
      radial-gradient(circle at 12% 0%, var(--accent-glow-start), transparent 42%),
      radial-gradient(circle at 88% 0%, var(--accent-glow-end), transparent 34%);
    filter: blur(18px);
    pointer-events: none;
    opacity: 0.95;
  }

  .workspace-stage__inner {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 1.25rem;
  }

  .shell-footer-bar {
    border-top: 1px solid var(--shell-chrome-border);
    margin-top: auto;
  }

  .shell-footer-inner {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr) auto;
    align-items: center;
    gap: 1rem;
  }

  .footer-brand-block {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    min-width: 0;
  }

  .brand-mark {
    width: 2.7rem;
    height: 2.7rem;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 1.1rem;
    background: linear-gradient(145deg, var(--shell-brand-start), var(--shell-brand-end));
    color: var(--shell-brand-contrast);
    border: 1px solid var(--shell-control-border);
    box-shadow: 0 16px 30px var(--shell-depth-shadow-strong);
  }

  .footer-brand-mark {
    width: 2.3rem;
    height: 2.3rem;
    border-radius: 0.85rem;
  }

  .footer-brand-block strong {
    display: block;
    color: var(--shell-text);
    font-size: 0.88rem;
  }

  .footer-brand-block p,
  .footer-summary {
    margin: 0;
    color: var(--shell-text-soft);
    font-size: 0.78rem;
  }

  .footer-meta {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .mobile-shell-bar,
  .mobile-shell-backdrop {
    display: none;
  }

  .shell-brand {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    text-decoration: none;
    color: inherit;
    min-width: 0;
  }

  .brand-copy {
    min-width: 0;
    display: grid;
    gap: 0.1rem;
  }

  .brand-copy strong {
    color: var(--shell-text);
    font-size: 0.93rem;
    font-weight: 800;
    letter-spacing: 0.01em;
  }

  .brand-copy small {
    color: var(--shell-text-soft);
    font-size: 0.74rem;
  }

  .profile-trigger,
  .shell-action-button,
  .shell-icon-button,
  .logout-button,
  .language-toggle,
  .shell-link-pill {
    flex-shrink: 0;
  }

  .profile-trigger,
  .shell-action-button,
  .logout-button,
  .shell-icon-button {
    background: var(--shell-control-bg);
    border-color: var(--shell-control-border);
    color: var(--shell-text);
    box-shadow: inset 0 1px 0 var(--shell-highlight);
  }

  .profile-trigger {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    padding-inline: 0.5rem 0.9rem;
  }

  .profile-trigger.compact {
    min-width: auto;
    padding-inline: 0.35rem;
  }

  .profile-copy {
    display: grid;
    gap: 0.12rem;
    min-width: 0;
    text-align: left;
  }

  .profile-copy strong {
    max-width: 12rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.86rem;
  }

  .profile-copy small {
    color: var(--shell-text-soft);
    font-size: 0.72rem;
  }

  .avatar-frame {
    width: 2.3rem;
    height: 2.3rem;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(145deg, var(--shell-brand-start), var(--shell-brand-end));
    color: var(--shell-brand-contrast);
    font-weight: 800;
    overflow: hidden;
    box-shadow: 0 14px 30px color-mix(in srgb, var(--primary) 24%, transparent);
  }

  .avatar-frame img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .desktop-sidebar-toggle {
    margin-top: 0.1rem;
  }

  :deep(.shell-icon-button .p-button-label),
  :deep(.profile-trigger .p-button-label),
  :deep(.shell-action-button .p-button-label),
  :deep(.logout-button .p-button-label) {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
  }

  :deep(.shell-icon-button .p-button-label) {
    justify-content: center;
  }

  :deep(.shell-icon-button) {
    min-width: 2.9rem;
  }

  :deep(.shell-action-button),
  :deep(.logout-button),
  :deep(.profile-trigger) {
    min-height: 2.85rem;
  }

  :deep(.language-toggle .p-togglebutton) {
    background: var(--shell-control-bg);
    border-color: var(--shell-control-border);
    color: var(--shell-text-soft);
  }

  :deep(.language-toggle .p-togglebutton.p-togglebutton-checked) {
    background: var(--shell-active-bg);
    border-color: var(--shell-active-border);
    color: var(--shell-text);
  }

  :deep(.footer-meta .p-tag) {
    background: var(--shell-control-bg);
    border: 1px solid var(--shell-control-border);
    color: var(--shell-text);
    font-size: 0.72rem;
  }

  @media (max-width: 1100px) {
    .shell-heading-row,
    .shell-footer-inner {
      grid-template-columns: 1fr;
      flex-direction: column;
      align-items: stretch;
    }

    .shell-header-actions,
    .footer-meta {
      justify-content: flex-start;
    }
  }

  @media (max-width: 960px) {
    .shell-workspace::before {
      inset: 0;
    }

    .mobile-shell-bar,
    .mobile-shell-backdrop {
      display: flex;
    }

    .mobile-shell-bar {
      position: sticky;
      top: 0;
      z-index: 30;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      padding: 0.85rem 1rem;
      background: var(--shell-chrome-bg);
      border-bottom: 1px solid var(--shell-chrome-border);
    }

    .mobile-shell-backdrop {
      position: fixed;
      inset: 0;
      background: var(--backdrop-scrim);
      z-index: 35;
    }

    .shell-brand-mobile {
      flex: 1;
    }

    .desktop-sidebar-toggle,
    .shell-header-actions .profile-trigger {
      display: none;
    }
  }

  @media (max-width: 760px) {
    .shell-topbar-inner,
    .shell-main,
    .shell-footer-inner {
      padding-inline: 1rem;
    }

    .page-description {
      max-width: none;
    }

    .shell-header-actions {
      gap: 0.55rem;
    }

    .shell-link-pill,
    .shell-action-button,
    .logout-button {
      width: 100%;
      justify-content: center;
    }
  }

  @media (max-width: 560px) {
    .brand-copy small,
    .footer-summary,
    .profile-copy,
    .shell-link-pill span,
    .shell-action-button span,
    .logout-button span {
      display: none;
    }

    .shell-main {
      padding-top: 0.95rem;
    }
  }
</style>
