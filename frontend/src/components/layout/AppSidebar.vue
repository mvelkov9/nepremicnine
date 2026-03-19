<script setup lang="ts">
  import { computed } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '../AppIcon.vue'
  import type { NavItem } from '../../constants/navigation'

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
  <aside
    class="shell-sidebar"
    :class="{ 'mobile-open': mobileOpen, collapsed: collapsed }"
  >
    <div class="sidebar-pane">
      <RouterLink to="/" class="shell-brand">
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
        <div
          v-for="(group, gi) in navGroups"
          :key="group.key || gi"
          class="shell-nav-group"
        >
          <span v-if="group.key && !collapsed" class="sidebar-section-label">{{ t(group.key) }}</span>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="shell-nav-link"
            :class="{ active: isActiveRoute(item) }"
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
    background: var(--shell-chrome-bg);
    color: var(--shell-text);
    border-right: 1px solid var(--shell-chrome-border);
    box-shadow: inset -1px 0 0 rgb(255 255 255 / 2%);
    transition:
      width 180ms ease,
      transform 180ms ease;
    z-index: 18;
  }

  .sidebar-pane {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.1rem 0.85rem 0.9rem;
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
    width: 2.7rem;
    height: 2.7rem;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 1.1rem;
    background: linear-gradient(145deg, var(--shell-brand-start), var(--shell-brand-end));
    color: var(--shell-brand-contrast);
    border: 1px solid rgb(255 255 255 / 10%);
    box-shadow: 0 16px 30px rgb(0 0 0 / 22%);
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

  .sidebar-context {
    display: grid;
    gap: 0.3rem;
    padding: 0.9rem;
    border-radius: 1.05rem;
    border: 1px solid var(--shell-panel-border);
    background: var(--shell-panel-bg);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 4%);
  }

  .sidebar-context strong {
    color: var(--shell-text);
    font-size: 0.92rem;
  }

  .sidebar-context p {
    margin: 0;
    color: var(--shell-text-soft);
    font-size: 0.78rem;
    line-height: 1.45;
  }

  .sidebar-section-label {
    color: var(--shell-text-muted);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .shell-nav {
    display: grid;
    gap: 0.65rem;
  }

  .shell-nav-group {
    display: grid;
    gap: 0.4rem;
  }

  .shell-nav-group + .shell-nav-group {
    padding-top: 0.55rem;
    border-top: 1px solid var(--shell-divider);
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
    padding: 0.68rem 0.72rem;
    border-radius: 0.95rem;
    border: 1px solid transparent;
    text-decoration: none;
    color: var(--shell-text-soft);
    transition:
      background 160ms ease,
      border-color 160ms ease,
      color 160ms ease,
      transform 160ms ease;
  }

  .shell-nav-link:hover,
  .shell-switch-link:hover,
  .shell-nav-link.active {
    background: var(--shell-active-bg);
    border-color: var(--shell-active-border);
    color: var(--shell-text);
    transform: translateX(2px);
  }

  .shell-nav-icon {
    width: 2.35rem;
    height: 2.35rem;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.95rem;
    background: var(--shell-control-bg);
    border: 1px solid var(--shell-control-border);
    color: var(--shell-icon-color);
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
    font-size: 0.86rem;
    font-weight: 700;
  }

  .sidebar-footer {
    margin-top: auto;
    display: grid;
    gap: 0.65rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--shell-divider);
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

    .collapsed .brand-copy,
    .collapsed .shell-nav-copy,
    .collapsed .sidebar-context {
      display: initial;
    }
  }
</style>
