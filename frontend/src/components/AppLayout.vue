<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { RouterLink, useRoute } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { useLocalStorage, useWindowScroll } from '@vueuse/core'
  import { adminNavigation, viewerNavigation } from '../constants/navigation'
  import type { NavItem } from '../constants/navigation'
  import AppIcon from './AppIcon.vue'
  import AppSidebar from './layout/AppSidebar.vue'
  import ActivityCenter from './layout/ActivityCenter.vue'
  import CommandPalette from './layout/CommandPalette.vue'
  import ProfileDialog from './layout/ProfileDialog.vue'
  import WorkspaceTray from './layout/WorkspaceTray.vue'
  import { useAuthStore } from '../stores/auth'
  import { useUiStore } from '../stores/ui'
  import { useWorkbenchStore } from '../stores/workbench'

  const { t } = useI18n()
  const auth = useAuthStore()
  const route = useRoute()
  const ui = useUiStore()
  const workbench = useWorkbenchStore()

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

  const workspaceBadge = computed(() => {
    if (workbench.unreadCount) return String(workbench.unreadCount)
    if (workbench.compareTray.length) return String(workbench.compareTray.length)
    return ''
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
      workbench.rememberRoute({
        label: currentTitle.value,
        path: route.path,
        query: route.query as Record<string, unknown>,
        page: String(route.name || ''),
      })
    },
  )

  function handleGlobalShortcuts(event: KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault()
      ui.toggleCommandPalette()
      return
    }
    if (event.altKey && event.key.toLowerCase() === 'a') {
      event.preventDefault()
      ui.toggleActivityCenter()
      return
    }
    if (event.altKey && event.key.toLowerCase() === 't') {
      event.preventDefault()
      ui.toggleWorkspaceTray()
    }
  }

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
    window.addEventListener('keydown', handleGlobalShortcuts)
    if (auth.isAuthenticated) {
      await Promise.allSettled([workbench.fetchUnreadCount(), workbench.fetchWorkspaces()])
    }
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleGlobalShortcuts)
  })

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function openProfile() {
    profileOpen.value = true
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
      <div class="mobile-shell-actions">
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
      </div>

      <RouterLink to="/" class="shell-brand shell-brand-mobile">
        <span class="brand-mark">
          <AppIcon name="brand" :size="22" :stroke="1.9" />
        </span>
        <div class="brand-copy">
          <strong>{{ t('app.title') }}</strong>
          <small>{{ t('layout.brandTagline') }}</small>
        </div>
      </RouterLink>

      <Button
        class="profile-trigger compact"
        text
        rounded
        :aria-label="t('layout.profile')"
        @click="openProfile"
      >
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
      @close="mobileMenuOpen = false"
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
                  <Tag v-if="versionBadge" :value="versionBadge" rounded />
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

              <Button
                class="shell-action-button shell-action-button--badge"
                rounded
                @click="ui.toggleWorkspaceTray()"
                :aria-label="t('layout.workspace')"
              >
                <AppIcon name="market" :size="16" />
                <span>{{ t('layout.workspace') }}</span>
                <small v-if="workspaceBadge" class="shell-badge">{{ workspaceBadge }}</small>
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
          <div class="footer-brand-line">
            <strong>{{ t('app.title') }}</strong>
            <span>{{ footerSummary }}</span>
          </div>

          <div class="footer-meta">
            <span class="footer-meta-chip">{{ workspaceTag }}</span>
            <span class="footer-meta-chip">{{ userRoleLabel }}</span>
            <span v-if="versionBadge" class="footer-meta-chip">{{ versionBadge }}</span>
          </div>
        </div>
      </footer>
    </div>
  </div>

  <!-- Profile Dialog -->
  <ProfileDialog v-model:visible="profileOpen" />
  <CommandPalette />
  <ActivityCenter />
  <WorkspaceTray />
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
    height: 12rem;
    background:
      radial-gradient(circle at top left, var(--app-shell-ambient-start), transparent 42%),
      radial-gradient(circle at top right, var(--app-shell-ambient-end), transparent 36%);
    pointer-events: none;
    z-index: 0;
    opacity: 0.55;
  }

  .shell-workspace::after {
    content: '';
    position: fixed;
    inset: auto 0 0 var(--sidebar-width);
    height: 8rem;
    background: linear-gradient(
      180deg,
      transparent,
      color-mix(in srgb, var(--app-shell-bg) 50%, transparent)
    );
    pointer-events: none;
    z-index: 0;
    opacity: 0.72;
  }

  .shell-topbar,
  .shell-footer-bar {
    position: relative;
    z-index: 5;
    width: 100%;
    background: var(--app-shell-bg);
    color: var(--app-shell-text);
  }

  .shell-topbar {
    position: sticky;
    top: 0;
    border-bottom: 1px solid var(--app-shell-border);
    box-shadow:
      inset 0 1px 0 var(--app-shell-highlight),
      0 12px 26px var(--app-shell-depth-shadow);
    backdrop-filter: blur(18px) saturate(1.08);
    transition:
      box-shadow 160ms ease,
      backdrop-filter 160ms ease;
  }

  .shell-topbar.scrolled {
    box-shadow: var(--app-shell-topbar-shadow);
    backdrop-filter: blur(20px) saturate(1.1);
  }

  .shell-topbar-inner,
  .shell-footer-inner {
    width: 100%;
    padding: 0.9rem 1.15rem;
  }

  .shell-heading-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .shell-heading-main {
    display: flex;
    align-items: flex-start;
    gap: 0.7rem;
    min-width: 0;
  }

  .page-meta {
    min-width: 0;
    display: grid;
    gap: 0.16rem;
  }

  .page-meta-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  .page-kicker {
    color: var(--app-shell-text-muted);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .page-heading {
    margin: 0;
    color: var(--app-shell-text);
    font-family: var(--font-display);
    font-size: clamp(1.24rem, 1.8vw, 1.64rem);
    line-height: 1;
    letter-spacing: -0.05em;
    text-wrap: balance;
  }

  .page-description {
    margin: 0;
    max-width: 48ch;
    color: var(--app-shell-text-soft);
    font-size: 0.8rem;
    line-height: 1.45;
    text-wrap: pretty;
  }

  .shell-header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .shell-link-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.58rem 0.82rem;
    border-radius: 999px;
    text-decoration: none;
    font-weight: 700;
    font-size: var(--text-sm);
    color: var(--app-shell-text);
    background: var(--app-shell-control-bg);
    border: 1px solid var(--app-shell-control-border);
    box-shadow: inset 0 1px 0 var(--app-shell-highlight-soft);
  }

  .shell-main {
    position: relative;
    z-index: 1;
    flex: 1;
    padding: 1.15rem 1.15rem 2rem;
  }

  .workspace-stage {
    position: relative;
    width: min(100%, 1440px);
    margin: 0 auto;
    min-height: 100%;
  }

  .workspace-stage::before {
    content: '';
    position: absolute;
    inset: 0.4rem 0 auto;
    height: 5rem;
    border-radius: 2rem;
    background:
      radial-gradient(circle at 12% 0%, var(--accent-glow-start), transparent 48%),
      radial-gradient(circle at 88% 0%, var(--accent-glow-end), transparent 42%);
    filter: blur(18px);
    pointer-events: none;
    opacity: 0.3;
  }

  .workspace-stage__inner {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 1.45rem;
  }

  .shell-footer-bar {
    border-top: 1px solid var(--app-shell-border);
    margin-top: auto;
    background: color-mix(in srgb, var(--app-shell-bg) 97%, #000 3%);
    backdrop-filter: blur(18px) saturate(1.05);
  }

  .shell-footer-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.8rem 1rem;
    padding-block: 0.62rem;
  }

  .footer-brand-line {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
    color: var(--app-shell-text-soft);
    font-size: 0.78rem;
  }

  .footer-brand-line strong {
    color: var(--app-shell-text);
    font-size: 0.82rem;
  }

  .footer-brand-line span {
    white-space: nowrap;
  }

  .footer-meta {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .footer-meta-chip {
    display: inline-flex;
    align-items: center;
    min-height: 1.85rem;
    padding: 0.28rem 0.72rem;
    border-radius: 999px;
    border: 1px solid var(--app-shell-control-border);
    background: color-mix(in srgb, var(--app-shell-control-bg) 92%, transparent);
    color: var(--app-shell-text-soft);
    font-size: 0.72rem;
    font-weight: 700;
  }

  .mobile-shell-bar,
  .mobile-shell-backdrop {
    display: none;
  }

  .mobile-shell-actions {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
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
    color: var(--app-shell-text);
    font-size: 0.93rem;
    font-weight: 800;
    letter-spacing: 0.01em;
  }

  .brand-copy small {
    color: var(--app-shell-text-soft);
    font-size: var(--text-xs);
  }

  .profile-trigger,
  .shell-action-button,
  .shell-icon-button,
  .shell-link-pill {
    flex-shrink: 0;
  }

  .profile-trigger,
  .shell-action-button,
  .shell-icon-button {
    background: var(--app-shell-control-bg);
    border-color: var(--app-shell-control-border);
    color: var(--app-shell-text);
    box-shadow: inset 0 1px 0 var(--app-shell-highlight-soft);
  }

  .profile-trigger:hover,
  .shell-action-button:hover,
  .shell-icon-button:hover,
  .shell-link-pill:hover {
    transform: translateY(-1px);
    border-color: color-mix(
      in srgb,
      var(--app-shell-active-border) 58%,
      var(--app-shell-control-border) 42%
    );
    box-shadow:
      inset 0 1px 0 var(--app-shell-highlight-strong),
      0 12px 24px var(--app-shell-depth-shadow);
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
    font-size: var(--text-meta);
  }

  .profile-copy small {
    color: var(--app-shell-text-soft);
    font-size: var(--text-xs);
  }

  .avatar-frame {
    width: 2.3rem;
    height: 2.3rem;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(145deg, var(--app-shell-brand-start), var(--app-shell-brand-end));
    color: var(--app-shell-brand-contrast);
    font-weight: 800;
    overflow: hidden;
    box-shadow: 0 10px 22px color-mix(in srgb, var(--primary) 18%, transparent);
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
  :deep(.shell-action-button .p-button-label) {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
  }

  :deep(.shell-icon-button .p-button-label) {
    justify-content: center;
  }

  :deep(.shell-icon-button) {
    min-width: 3rem;
  }

  :deep(.shell-action-button),
  :deep(.profile-trigger) {
    min-height: 2.95rem;
  }

  .shell-action-button--badge {
    position: relative;
  }

  .shell-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.4rem;
    height: 1.4rem;
    padding: 0 0.3rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--danger) 88%, transparent);
    color: var(--primary-contrast);
    font-size: 0.7rem;
    font-weight: 800;
  }

  :deep(.footer-meta .p-tag) {
    background: var(--app-shell-control-bg);
    border: 1px solid var(--app-shell-control-border);
    color: var(--app-shell-text);
    font-size: var(--text-xs);
  }

  :deep(.page-meta-row .p-tag) {
    background: var(--app-shell-control-bg);
    border: 1px solid var(--app-shell-control-border);
    color: var(--app-shell-text-soft);
    font-size: 0.7rem;
  }

  @media (max-width: 1100px) {
    .shell-heading-row,
    .shell-footer-inner {
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

    .shell-workspace::after {
      inset: auto 0 0;
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
      padding: 0.9rem 1rem;
      background: var(--app-shell-bg);
      border-bottom: 1px solid var(--app-shell-border);
      backdrop-filter: blur(16px);
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
    .shell-action-button {
      width: auto;
      justify-content: center;
    }
  }

  @media (max-width: 560px) {
    .page-kicker {
      font-size: 0.66rem;
    }

    .brand-copy small,
    .profile-copy,
    .shell-link-pill span,
    .shell-action-button span {
      display: none;
    }

    .shell-main {
      padding-top: 0.95rem;
    }
  }
</style>
