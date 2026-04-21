<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import InputText from 'primevue/inputtext'
  import Tag from 'primevue/tag'
  import { adminNavigation, viewerNavigation } from '../../constants/navigation'
  import {
    buildWorkspaceRoute,
    describeRoute,
    toLocationQuery,
    workspacePageTitleKeys,
  } from '../../constants/workbench'
  import type { WatchlistItem } from '../../types/api'
  import { useAuthStore } from '../../stores/auth'
  import { useUiStore } from '../../stores/ui'
  import { useWorkbenchStore } from '../../stores/workbench'
  import { getApiErrorMessage } from '../../utils/apiError'

  interface PaletteItem {
    id: string
    label: string
    meta: string
    section: 'routes' | 'savedViews' | 'watchlists' | 'recent' | 'compare' | 'actions'
    action: () => unknown
  }

  const SECTION_LIMITS: Record<PaletteItem['section'], number> = {
    routes: 8,
    savedViews: 6,
    watchlists: 6,
    recent: 6,
    compare: 6,
    actions: 4,
  }

  const { t } = useI18n()
  const router = useRouter()
  const auth = useAuthStore()
  const ui = useUiStore()
  const workbench = useWorkbenchStore()

  const query = ref('')
  const activeIndex = ref(0)
  const commandInput = ref()
  const catalogLoading = ref(false)
  const workspaceCatalogError = ref('')
  const watchlistCatalogError = ref('')

  const paletteWorkspaces = computed(() =>
    workspaceCatalogError.value ? [] : workbench.workspaces,
  )

  const paletteWatchlists = computed(() =>
    watchlistCatalogError.value ? [] : workbench.watchlists,
  )

  const catalogError = computed(() => workspaceCatalogError.value || watchlistCatalogError.value)

  function entityTypeLabel(entityType?: string | null) {
    if (entityType === 'region') return t('nav.regions')
    if (entityType === 'municipality') return t('nav.municipalities')
    return entityType || t('common.noData')
  }

  function watchlistMeta(item: WatchlistItem) {
    const region = typeof item.metadata?.region === 'string' ? item.metadata.region : ''
    return region || entityTypeLabel(item.entity_type)
  }

  function watchlistRoute(item: WatchlistItem) {
    const storedLink = typeof item.metadata?.link === 'string' ? item.metadata.link : ''
    if (storedLink) return storedLink
    return item.entity_type === 'region'
      ? { path: '/regije', query: { tab: 'drilldown', region: item.entity_key } }
      : { path: `/obcine/${item.entity_key}` }
  }

  const allPaletteItems = computed<PaletteItem[]>(() => {
    const navItems: PaletteItem[] = [
      ...viewerNavigation,
      ...(auth.isAdmin ? adminNavigation : []),
    ].map((item) => ({
      id: `nav:${item.to}`,
      label: t(item.label),
      meta: t(item.group || 'nav.groupOverview'),
      section: 'routes',
      action: () => router.push(item.to),
    }))

    const workspaceItems: PaletteItem[] = [...paletteWorkspaces.value]
      .sort((left, right) => Number(right.pinned) - Number(left.pinned))
      .map((item) => ({
        id: `workspace:${item.id}`,
        label: item.name,
        meta: t(workspacePageTitleKeys[item.page] || 'app.title'),
        section: 'savedViews',
        action: () =>
          router.push(
            buildWorkspaceRoute(item.page, {
              ...(item.filters || {}),
              ...(item.tab ? { tab: item.tab } : {}),
              ...(item.sort ? { sort: item.sort } : {}),
            }),
          ),
      }))

    const watchlistItems: PaletteItem[] = paletteWatchlists.value.map((item) => ({
      id: `watch:${item.id}`,
      label: item.display_label,
      meta: watchlistMeta(item),
      section: 'watchlists',
      action: () => router.push(watchlistRoute(item)),
    }))

    const recentItems: PaletteItem[] = [
      ...workbench.recentRoutes.map((item, index) => ({
        id: `recent-route:${index}`,
        label: item.label,
        meta: describeRoute(item.path, item.query || {}),
        section: 'recent' as const,
        action: () => router.push({ path: item.path, query: toLocationQuery(item.query || {}) }),
      })),
      ...workbench.recentMunicipalities.map((item) => ({
        id: `recent-municipality:${item.id}`,
        label: item.label,
        meta: item.region || t('nav.municipalities'),
        section: 'recent' as const,
        action: () => router.push({ path: `/obcine/${item.slug || item.id}` }),
      })),
    ]

    const compareItems: PaletteItem[] = workbench.compareTray.map((item) => ({
      id: `compare:${item.id}`,
      label: item.label,
      meta: item.region || entityTypeLabel(item.entity_type),
      section: 'compare',
      action: () =>
        router.push(
          item.entity_type === 'region'
            ? { path: '/regije', query: { tab: 'drilldown', region: item.label } }
            : { path: `/obcine/${item.slug || item.id.replace('municipality:', '')}` },
        ),
    }))

    const actionItems: PaletteItem[] = [
      {
        id: 'action:activity-center',
        label: t('workbench.openActivityCenter'),
        meta: t('workbench.activityCenter'),
        section: 'actions',
        action: () => ui.toggleActivityCenter(true),
      },
      {
        id: 'action:workspace-tray',
        label: t('workbench.openWorkspaceTray'),
        meta: t('workbench.workspaceTray'),
        section: 'actions',
        action: () => ui.toggleWorkspaceTray(true),
      },
    ]

    return [
      ...navItems,
      ...workspaceItems,
      ...watchlistItems,
      ...recentItems,
      ...compareItems,
      ...actionItems,
    ]
  })

  const paletteSections = computed(() => {
    const normalizedQuery = query.value.trim().toLowerCase()
    const filteredItems = !normalizedQuery
      ? allPaletteItems.value
      : allPaletteItems.value.filter((item) =>
          `${item.label} ${item.meta}`.toLowerCase().includes(normalizedQuery),
        )

    const sections: Array<{
      key: PaletteItem['section']
      label: string
      items: Array<PaletteItem & { flatIndex: number }>
    }> = []

    let runningIndex = 0
    for (const key of Object.keys(SECTION_LIMITS) as PaletteItem['section'][]) {
      const items = filteredItems
        .filter((item) => item.section === key)
        .slice(0, SECTION_LIMITS[key])
        .map((item) => ({
          ...item,
          flatIndex: runningIndex++,
        }))

      if (!items.length) continue

      sections.push({
        key,
        label: t(`workbench.section.${key}`),
        items,
      })
    }

    return sections
  })

  const flatPaletteItems = computed(() => paletteSections.value.flatMap((section) => section.items))

  async function refreshPaletteCatalog() {
    catalogLoading.value = true
    workspaceCatalogError.value = ''
    watchlistCatalogError.value = ''

    const [workspacesResult, watchlistsResult] = await Promise.allSettled([
      workbench.fetchWorkspaces(),
      workbench.fetchWatchlists(),
    ])

    if (workspacesResult.status === 'rejected') {
      workspaceCatalogError.value = getApiErrorMessage(workspacesResult.reason, t)
    }

    if (watchlistsResult.status === 'rejected') {
      watchlistCatalogError.value = getApiErrorMessage(watchlistsResult.reason, t)
    }

    catalogLoading.value = false
  }

  watch(
    () => ui.commandPaletteOpen,
    async (open) => {
      if (!open) {
        query.value = ''
        activeIndex.value = 0
        return
      }

      await refreshPaletteCatalog()
      await nextTick()
      commandInput.value?.$el?.querySelector?.('input')?.focus?.()
    },
  )

  watch(
    () => query.value,
    () => {
      activeIndex.value = 0
    },
  )

  watch(
    flatPaletteItems,
    (items) => {
      if (!items.length) {
        activeIndex.value = 0
        return
      }
      if (activeIndex.value >= items.length) {
        activeIndex.value = items.length - 1
      }
    },
    { deep: true },
  )

  function runAction(item: PaletteItem) {
    void item.action()
    ui.toggleCommandPalette(false)
  }

  function moveSelection(direction: 1 | -1) {
    if (!flatPaletteItems.value.length) return
    const nextIndex =
      (activeIndex.value + direction + flatPaletteItems.value.length) %
      flatPaletteItems.value.length
    activeIndex.value = nextIndex
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      moveSelection(1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      moveSelection(-1)
      return
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      const item = flatPaletteItems.value[activeIndex.value]
      if (item) runAction(item)
      return
    }
    if (event.key === 'Escape') {
      ui.toggleCommandPalette(false)
    }
  }
</script>

<template>
  <Dialog
    v-model:visible="ui.commandPaletteOpen"
    modal
    :header="t('workbench.commandPalette')"
    :style="{ width: 'min(92vw, 760px)' }"
  >
    <div class="command-palette" @keydown="handleKeydown">
      <InputText
        ref="commandInput"
        v-model="query"
        autofocus
        class="command-input"
        :placeholder="t('workbench.commandPlaceholder')"
      />

      <p class="command-hint muted">{{ t('workbench.commandNavigationHint') }}</p>

      <div v-if="catalogError" class="command-note" role="status">
        <span>{{ catalogError }}</span>
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          :loading="catalogLoading"
          :disabled="catalogLoading"
          @click="refreshPaletteCatalog"
        />
      </div>

      <div v-if="paletteSections.length" class="command-results">
        <section v-for="section in paletteSections" :key="section.key" class="command-section">
          <div class="command-section__head">
            <h3>{{ section.label }}</h3>
            <Tag :value="String(section.items.length)" severity="secondary" />
          </div>

          <button
            v-for="item in section.items"
            :key="item.id"
            type="button"
            class="command-item"
            :class="{ active: item.flatIndex === activeIndex }"
            @mouseenter="activeIndex = item.flatIndex"
            @click="runAction(item)"
          >
            <div class="command-copy">
              <strong>{{ item.label }}</strong>
              <small>{{ item.meta }}</small>
            </div>
            <Tag :value="section.label" severity="contrast" />
          </button>
        </section>
      </div>

      <p v-else class="muted">
        {{ t('workbench.noCommandResults') }}
      </p>
    </div>
  </Dialog>
</template>

<style scoped>
  .command-palette,
  .command-results,
  .command-section {
    display: grid;
    gap: 0.95rem;
  }

  .command-note {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.75rem 0.9rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--danger) 24%, var(--border) 76%);
    background: color-mix(in srgb, var(--danger) 8%, var(--surface-subtle) 92%);
    color: var(--text-soft);
    flex-wrap: wrap;
  }

  .command-input {
    width: 100%;
  }

  .command-palette {
    gap: 1rem;
  }

  .command-palette :deep(.p-inputtext) {
    min-height: 3.2rem;
    padding-inline: 1rem;
    font-size: 0.98rem;
    border-radius: var(--radius-md);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 95%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
  }

  .command-hint {
    margin: -0.1rem 0 0;
    font-size: 0.82rem;
  }

  .command-section__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .command-section__head h3 {
    margin: 0;
    font-size: 0.9rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-soft);
  }

  .command-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    width: 100%;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow: var(--shadow-sm);
    text-align: left;
    color: inherit;
    transition:
      border-color 140ms ease,
      transform 140ms ease,
      background 140ms ease,
      box-shadow 140ms ease;
  }

  .command-item.active {
    border-color: color-mix(in srgb, var(--primary) 42%, var(--border) 58%);
    background:
      linear-gradient(135deg, color-mix(in srgb, var(--primary) 14%, transparent), transparent 42%),
      color-mix(in srgb, var(--surface-subtle) 84%, var(--primary) 16%);
    transform: translateY(-1px);
    box-shadow: var(--accent-shadow);
  }

  .command-copy {
    display: grid;
    gap: 0.22rem;
    min-width: 0;
  }

  .command-item strong {
    display: block;
    font-size: 0.96rem;
  }

  .command-item small {
    color: var(--text-muted);
  }

  :deep(.p-dialog .p-dialog-content .command-palette) {
    padding-top: 0.15rem;
  }

  @media (max-width: 620px) {
    .command-note :deep(.p-button) {
      width: 100%;
    }
  }
</style>
