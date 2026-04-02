<script setup lang="ts">
  import { computed, nextTick, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
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
  import { useAuthStore } from '../../stores/auth'
  import { useUiStore } from '../../stores/ui'
  import { useWorkbenchStore } from '../../stores/workbench'

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

    const workspaceItems: PaletteItem[] = [...workbench.workspaces]
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

    const watchlistItems: PaletteItem[] = workbench.watchlists.map((item) => ({
      id: `watch:${item.id}`,
      label: item.display_label,
      meta: item.entity_type,
      section: 'watchlists',
      action: () =>
        router.push(
          item.entity_type === 'region'
            ? { path: '/regije', query: { tab: 'drilldown', region: item.entity_key } }
            : { path: `/obcine/${item.entity_key}` },
        ),
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
      meta: item.region || item.entity_type,
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

  watch(
    () => ui.commandPaletteOpen,
    async (open) => {
      if (!open) {
        query.value = ''
        activeIndex.value = 0
        return
      }

      await Promise.allSettled([workbench.fetchWorkspaces(), workbench.fetchWatchlists()])
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
    gap: 0.9rem;
  }

  .command-input {
    width: 100%;
  }

  .command-hint {
    margin: -0.15rem 0 0;
    font-size: 0.8rem;
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
    color: var(--text-muted);
  }

  .command-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    width: 100%;
    padding: 0.85rem 1rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-soft)) 86%,
      transparent
    );
    text-align: left;
    color: inherit;
    transition:
      border-color 140ms ease,
      transform 140ms ease,
      background 140ms ease;
  }

  .command-item.active {
    border-color: color-mix(in srgb, var(--primary) 45%, var(--border) 55%);
    background: color-mix(
      in srgb,
      var(--primary) 8%,
      var(--surface-card-strong, var(--surface-soft)) 92%
    );
    transform: translateY(-1px);
  }

  .command-copy {
    display: grid;
    gap: 0.18rem;
    min-width: 0;
  }

  .command-item strong {
    display: block;
    font-size: 0.94rem;
  }

  .command-item small {
    color: var(--text-muted);
  }
</style>
