<script setup lang="ts">
  import { computed } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '../AppIcon.vue'
  import type { NavItem } from '../../constants/navigation'

  const emit = defineEmits<{
    close: []
  }>()

  const props = defineProps<{
    navItems: NavItem[]
    collapsed: boolean
    mobileOpen: boolean
    workspaceLabel: string
    footerSummary: string
    switchLink: { to: string; icon: string; label: string } | null
    isActiveRoute: (item: NavItem) => boolean
  }>()

  const { t } = useI18n()

  interface NavGroup {
    key: string
    items: NavItem[]
  }

  const navGroups = computed<NavGroup[]>(() => {
    const groups: NavGroup[] = []
    let currentKey = ''
    for (const item of props.navItems) {
      const key = item.group ?? ''
      if (key !== currentKey || groups.length === 0) {
        currentKey = key
        groups.push({ key, items: [item] })
      } else {
        groups[groups.length - 1].items.push(item)
      }
    }
    return groups
  })

  function sidebarTooltip(label: string) {
    return props.collapsed ? { value: label, showDelay: 120, autoHide: true } : null
  }
</script>

<template>
  <aside class="shell-sidebar" :class="{ 'mobile-open': mobileOpen, collapsed: collapsed }">
    <div class="sidebar-pane">
      <div class="sidebar-mobile-header">
        <RouterLink to="/" class="shell-brand">
          <span class="brand-mark">
            <AppIcon name="brand" :size="24" :stroke="1.95" />
          </span>
          <div class="brand-copy">
            <strong>{{ t('app.title') }}</strong>
            <small>{{ t('layout.brandTagline') }}</small>
          </div>
        </RouterLink>

        <Button
          class="sidebar-close-button shell-icon-button"
          text
          rounded
          :aria-label="t('ui.closeMenu')"
          @click="emit('close')"
        >
          <i class="pi pi-times" aria-hidden="true"></i>
        </Button>
      </div>

      <RouterLink to="/" class="shell-brand shell-brand-desktop">
        <span class="brand-mark">
          <AppIcon name="brand" :size="24" :stroke="1.95" />
        </span>
        <div class="brand-copy">
          <strong>{{ t('app.title') }}</strong>
          <small>{{ t('layout.brandTagline') }}</small>
        </div>
      </RouterLink>

      <section class="sidebar-context" :class="{ compact: collapsed }">
        <span class="sidebar-section-label">{{ t('layout.workspaceMode') }}</span>
        <strong>{{ workspaceLabel }}</strong>
        <p>{{ footerSummary }}</p>
      </section>

      <nav class="shell-nav" :aria-label="t('layout.navigation')">
        <div v-for="(group, gi) in navGroups" :key="group.key || gi" class="shell-nav-group">
          <span v-if="group.key && !collapsed" class="sidebar-section-label">{{
            t(group.key)
          }}</span>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="shell-nav-link"
            :class="{ active: isActiveRoute(item) }"
            :aria-current="isActiveRoute(item) ? 'page' : undefined"
            v-tooltip.right="sidebarTooltip(t(item.label))"
          >
            <span class="shell-nav-icon">
              <AppIcon :name="item.icon" :size="18" />
            </span>
            <span class="shell-nav-copy">
              <strong>{{ t(item.label) }}</strong>
            </span>
          </RouterLink>
        </div>
      </nav>

      <div class="sidebar-footer">
        <RouterLink
          v-if="switchLink"
          :to="switchLink.to"
          class="shell-switch-link"
          v-tooltip.right="sidebarTooltip(switchLink.label)"
        >
          <span class="shell-nav-icon subtle">
            <AppIcon :name="switchLink.icon" :size="16" />
          </span>
          <span class="shell-nav-copy">
            <strong>{{ switchLink.label }}</strong>
          </span>
        </RouterLink>
      </div>
    </div>
  </aside>
</template>

<style scoped>
  .shell-sidebar {
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
    background: var(--app-shell-bg);
    color: var(--app-shell-text);
    border-right: 1px solid var(--app-shell-border);
    box-shadow:
      inset -1px 0 0 var(--app-shell-highlight-soft),
      inset 0 1px 0 var(--app-shell-highlight);
    transition:
      width 180ms ease,
      transform 180ms ease;
    z-index: 18;
  }

  .sidebar-pane {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    gap: 0.84rem;
    padding: 1rem 0.9rem 0.98rem;
    background:
      radial-gradient(circle at 0% 0%, var(--app-shell-ambient-start), transparent 40%),
      radial-gradient(circle at 100% 12%, var(--app-shell-ambient-end), transparent 32%);
  }

  .sidebar-mobile-header {
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

  .brand-mark {
    width: 2.45rem;
    height: 2.45rem;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    background: linear-gradient(145deg, var(--app-shell-brand-start), var(--app-shell-brand-end));
    color: var(--app-shell-brand-contrast);
    border: 1px solid var(--app-shell-control-border);
    box-shadow: 0 10px 20px var(--app-shell-depth-shadow-strong);
  }

  .brand-copy {
    min-width: 0;
    display: grid;
    gap: 0.1rem;
  }

  .brand-copy strong {
    color: var(--app-shell-text);
    font-size: 0.9rem;
    font-weight: 800;
    letter-spacing: 0.01em;
  }

  .brand-copy small {
    color: var(--app-shell-text-soft);
    font-size: var(--text-xs);
  }

  .sidebar-context {
    display: grid;
    gap: 0.24rem;
    padding: 0.74rem 0.82rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--app-shell-panel-border);
    background: color-mix(in srgb, var(--app-shell-panel-bg) 94%, transparent);
    box-shadow:
      inset 0 1px 0 var(--app-shell-highlight-soft),
      0 10px 20px var(--app-shell-depth-shadow);
  }

  .sidebar-context strong {
    color: var(--app-shell-text);
    font-size: 0.86rem;
  }

  .sidebar-context p {
    margin: 0;
    color: var(--app-shell-text-soft);
    font-size: 0.74rem;
    line-height: 1.4;
  }

  .sidebar-section-label {
    color: var(--app-shell-text-muted);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .shell-nav {
    display: grid;
    gap: 0.5rem;
  }

  .shell-nav-group {
    display: grid;
    gap: 0.4rem;
  }

  .shell-nav-group + .shell-nav-group {
    padding-top: 0.45rem;
    border-top: 1px solid var(--app-shell-divider);
  }

  .shell-nav-group > .sidebar-section-label {
    padding-inline: 0.72rem;
    padding-bottom: 0.1rem;
  }

  .shell-nav-link,
  .shell-switch-link {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    min-width: 0;
    padding: 0.62rem 0.72rem;
    border-radius: 1rem;
    border: 1px solid transparent;
    text-decoration: none;
    color: var(--app-shell-text-soft);
    background: transparent;
    box-shadow: inset 0 1px 0 transparent;
    transition:
      background 160ms ease,
      border-color 160ms ease,
      color 160ms ease,
      transform 160ms ease,
      box-shadow 160ms ease;
  }

  .shell-nav-link:hover,
  .shell-switch-link:hover,
  .shell-nav-link.active {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--app-shell-active-bg) 86%, transparent),
      color-mix(in srgb, var(--app-shell-highlight) 62%, transparent)
    );
    border-color: var(--app-shell-active-border);
    color: var(--app-shell-text);
    transform: translateX(2px);
    box-shadow:
      inset 0 1px 0 var(--app-shell-highlight-strong),
      0 12px 24px var(--app-shell-depth-shadow);
  }

  .shell-nav-link.active {
    border-color: color-mix(
      in srgb,
      var(--app-shell-active-border) 76%,
      var(--app-shell-control-border) 24%
    );
  }

  .shell-nav-link.active::before {
    content: '';
    width: 0.3rem;
    align-self: stretch;
    margin: -0.28rem 0 -0.28rem -0.12rem;
    border-radius: 999px;
    background: linear-gradient(180deg, var(--app-shell-brand-start), var(--app-shell-brand-end));
    box-shadow: 0 0 0 1px color-mix(in srgb, var(--app-shell-brand-start) 40%, transparent);
  }

  .shell-nav-icon {
    width: 2.1rem;
    height: 2.1rem;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-xs);
    background: var(--app-shell-control-bg);
    border: 1px solid var(--app-shell-control-border);
    color: var(--app-shell-icon-color);
    box-shadow:
      inset 0 1px 0 var(--app-shell-highlight-soft),
      0 8px 18px var(--app-shell-depth-shadow);
  }

  .shell-nav-icon.subtle {
    width: 2.15rem;
    height: 2.15rem;
  }

  .shell-nav-copy {
    min-width: 0;
    display: flex;
    align-items: center;
  }

  .shell-nav-copy strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.84rem;
    font-weight: 700;
  }

  .sidebar-footer {
    margin-top: auto;
    display: grid;
    gap: 0.5rem;
    padding-top: 0.7rem;
    border-top: 1px solid var(--app-shell-divider);
  }

  .collapsed .sidebar-context,
  .collapsed .shell-nav-copy,
  .collapsed .brand-copy {
    display: none;
  }

  .collapsed .sidebar-pane {
    padding-inline: 0.75rem;
  }

  .collapsed .shell-brand,
  .collapsed .shell-nav-link,
  .collapsed .shell-switch-link {
    justify-content: center;
  }

  .collapsed .shell-nav-link,
  .collapsed .shell-switch-link {
    padding-inline: 0.5rem;
  }

  .shell-nav-link:focus-visible,
  .shell-switch-link:focus-visible,
  .shell-brand:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
  }

  @media (max-width: 960px) {
    .shell-sidebar {
      position: fixed;
      inset: 0 auto 0 0;
      width: min(90vw, 21rem);
      transform: translateX(-102%);
      z-index: 40;
    }

    .shell-sidebar.mobile-open {
      transform: translateX(0);
    }

    .sidebar-mobile-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 0.75rem;
    }

    .shell-brand-desktop {
      display: none;
    }

    .collapsed .brand-copy,
    .collapsed .shell-nav-copy,
    .collapsed .sidebar-context {
      display: initial;
    }

    .collapsed .shell-brand-desktop {
      display: none;
    }

    .sidebar-close-button {
      align-self: flex-start;
    }
  }
</style>
