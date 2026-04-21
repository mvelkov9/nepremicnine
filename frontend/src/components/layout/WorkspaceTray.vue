<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import Tag from 'primevue/tag'
  import EmptyState from '../EmptyState.vue'
  import LoadingSpinner from '../LoadingSpinner.vue'
  import {
    buildWorkspaceRoute,
    describeRoute,
    toLocationQuery,
    workspacePageTitleKeys,
  } from '../../constants/workbench'
  import type { WatchlistFeedItem } from '../../types/api'
  import { useUiStore } from '../../stores/ui'
  import { useWorkbenchStore } from '../../stores/workbench'
  import { getApiErrorMessage } from '../../utils/apiError'
  import { formatCurrency, formatNumber } from '../../utils/format'

  const { t } = useI18n()
  const router = useRouter()
  const ui = useUiStore()
  const workbench = useWorkbenchStore()
  const watchlistFeedLoading = ref(false)
  const pinnedWorkspacesLoading = ref(false)
  const watchlistFeedError = ref('')
  const pinnedWorkspacesError = ref('')

  const municipalityCompareItems = computed(() =>
    workbench.compareTray.filter((item) => item.entity_type === 'municipality'),
  )

  const trayWatchlistFeed = computed(() =>
    watchlistFeedError.value ? [] : workbench.watchlistFeed,
  )

  const trayPinnedWorkspaces = computed(() =>
    pinnedWorkspacesError.value ? [] : workbench.pinnedWorkspaces,
  )

  async function refreshWorkspaceTray() {
    watchlistFeedLoading.value = true
    pinnedWorkspacesLoading.value = true
    watchlistFeedError.value = ''
    pinnedWorkspacesError.value = ''

    const [watchlistResult, workspacesResult] = await Promise.allSettled([
      workbench.fetchWatchlistFeed(),
      workbench.fetchWorkspaces(),
    ])

    if (watchlistResult.status === 'rejected') {
      watchlistFeedError.value = getApiErrorMessage(watchlistResult.reason, t)
    }

    if (workspacesResult.status === 'rejected') {
      pinnedWorkspacesError.value = getApiErrorMessage(workspacesResult.reason, t)
    }

    watchlistFeedLoading.value = false
    pinnedWorkspacesLoading.value = false
  }

  watch(
    () => ui.workspaceTrayOpen,
    async (open) => {
      if (!open) return
      await refreshWorkspaceTray()
    },
  )

  function closeTray() {
    ui.toggleWorkspaceTray(false)
  }

  function openCommandPalette() {
    closeTray()
    ui.toggleCommandPalette(true)
  }

  function openActivityCenter() {
    closeTray()
    ui.toggleActivityCenter(true)
  }

  function openPinnedWorkspace(item: any) {
    void router.push(
      buildWorkspaceRoute(item.page, {
        ...(item.filters || {}),
        ...(item.tab ? { tab: item.tab } : {}),
      }),
    )
    closeTray()
  }

  function openFeedItem(item: any) {
    if (!item.link) return
    void router.push(item.link)
    closeTray()
  }

  function entityTypeLabel(entityType?: string | null) {
    if (entityType === 'region') return t('nav.regions')
    if (entityType === 'municipality') return t('nav.municipalities')
    return entityType || t('common.noData')
  }

  function watchlistFeedSummary(item: WatchlistFeedItem) {
    if (item.headline_label && item.headline_value != null) {
      return `${item.headline_label}: ${formatCurrency(item.headline_value)}`
    }
    if (item.headline_label) return item.headline_label
    return t('common.noData')
  }

  function watchlistFeedTrend(item: WatchlistFeedItem) {
    if (item.trend_value == null) return ''
    const value = `${formatNumber(item.trend_value, { maximumFractionDigits: 1 })}%`
    return item.trend_label ? `${item.trend_label}: ${value}` : value
  }

  function openRecentRoute(item: any) {
    void router.push({ path: item.path, query: toLocationQuery(item.query || {}) })
    closeTray()
  }

  function recentRouteLabel(item: any) {
    return describeRoute(item.path, item.query || {})
  }

  function openRecentMunicipality(item: any) {
    void router.push({ path: `/obcine/${item.slug}` })
    closeTray()
  }

  function compareMunicipalities() {
    const slugs = municipalityCompareItems.value
      .map((item) => item.slug)
      .filter(Boolean)
      .join(',')
    if (!slugs) return
    void router.push({
      path: '/obcine',
      query: toLocationQuery({ tab: 'compare', compare: slugs }),
    })
    closeTray()
  }
</script>

<template>
  <Dialog
    v-model:visible="ui.workspaceTrayOpen"
    modal
    :header="t('workbench.workspaceTray')"
    :style="{ width: 'min(96vw, 1080px)' }"
  >
    <div class="workspace-tray">
      <section class="tray-column tray-column--wide">
        <div class="tray-head">
          <h3>{{ t('layout.workspace') }}</h3>
          <Tag :value="t('workbench.resumeWork')" severity="contrast" />
        </div>

        <div class="quick-actions">
          <button type="button" class="quick-action" @click="openCommandPalette">
            <strong>{{ t('workbench.commandPalette') }}</strong>
            <small>Ctrl/Cmd + K</small>
          </button>
          <button type="button" class="quick-action" @click="openActivityCenter">
            <strong>{{ t('workbench.activityCenter') }}</strong>
            <small>Alt + A</small>
          </button>
          <div class="quick-action quick-action--static">
            <strong>{{ t('workbench.compareTray') }}</strong>
            <small>{{ workbench.compareTray.length }} {{ t('common.items') }}</small>
          </div>
        </div>
      </section>

      <section class="tray-column">
        <div class="tray-head">
          <h3>{{ t('workbench.compareTray') }}</h3>
          <Tag :value="String(workbench.compareTray.length)" severity="secondary" />
        </div>

        <article v-for="item in workbench.compareTray" :key="item.id" class="tray-card">
          <div>
            <strong>{{ item.label }}</strong>
            <small>{{ item.region || entityTypeLabel(item.entity_type) }}</small>
          </div>
          <Button
            size="small"
            severity="danger"
            text
            icon="pi pi-times"
            @click="workbench.removeCompareItem(item.id)"
          />
        </article>

        <p v-if="!workbench.compareTray.length" class="muted tray-empty">
          {{ t('workbench.noCompareItems') }}
        </p>

        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-arrow-right"
          :label="t('workbench.compareNow')"
          :disabled="municipalityCompareItems.length < 2"
          @click="compareMunicipalities"
        />
      </section>

      <section class="tray-column">
        <div class="tray-head">
          <h3>{{ t('workbench.watchlistFeed') }}</h3>
          <Tag :value="String(trayWatchlistFeed.length)" severity="secondary" />
        </div>

        <LoadingSpinner
          v-if="watchlistFeedLoading && !trayWatchlistFeed.length"
          :label="t('common.loading')"
        />
        <div v-else-if="watchlistFeedError" class="tray-state" role="alert">
          <EmptyState icon="pi pi-exclamation-triangle" :message="watchlistFeedError" />
          <Button
            size="small"
            severity="secondary"
            outlined
            icon="pi pi-refresh"
            :label="t('common.retry')"
            :disabled="watchlistFeedLoading || pinnedWorkspacesLoading"
            @click="refreshWorkspaceTray"
          />
        </div>
        <template v-else-if="trayWatchlistFeed.length">
          <article
            v-for="item in trayWatchlistFeed"
            :key="item.id"
            class="tray-card"
            :class="{ clickable: Boolean(item.link) }"
            @click="item.link && openFeedItem(item)"
          >
            <div>
              <strong>{{ item.display_label }}</strong>
              <small>
                {{ watchlistFeedSummary(item) }}
                <template v-if="watchlistFeedTrend(item)">
                  | {{ watchlistFeedTrend(item) }}
                </template>
              </small>
            </div>
            <Tag
              v-if="item.trend_value != null"
              :value="`${formatNumber(item.trend_value, { maximumFractionDigits: 1 })}%`"
              :severity="item.trend_value >= 0 ? 'success' : 'danger'"
            />
          </article>
        </template>

        <p v-else class="muted tray-empty">
          {{ t('workbench.noWatchlistFeed') }}
        </p>

        <div class="tray-head recent-head">
          <h3>{{ t('workbench.recentRoutes') }}</h3>
          <Tag :value="String(workbench.recentRoutes.length)" severity="secondary" />
        </div>

        <article
          v-for="item in workbench.recentRoutes"
          :key="recentRouteLabel(item)"
          class="tray-card clickable"
          @click="openRecentRoute(item)"
        >
          <div>
            <strong>{{ item.label }}</strong>
            <small>{{ recentRouteLabel(item) }}</small>
          </div>
        </article>

        <p v-if="!workbench.recentRoutes.length" class="muted tray-empty">
          {{ t('workbench.noRecentRoutes') }}
        </p>
      </section>

      <section class="tray-column">
        <div class="tray-head">
          <h3>{{ t('workbench.pinnedWorkspaces') }}</h3>
          <Tag :value="String(trayPinnedWorkspaces.length)" severity="secondary" />
        </div>

        <LoadingSpinner
          v-if="pinnedWorkspacesLoading && !trayPinnedWorkspaces.length"
          :label="t('common.loading')"
        />
        <div v-else-if="pinnedWorkspacesError" class="tray-state" role="alert">
          <EmptyState icon="pi pi-exclamation-triangle" :message="pinnedWorkspacesError" />
          <Button
            size="small"
            severity="secondary"
            outlined
            icon="pi pi-refresh"
            :label="t('common.retry')"
            :disabled="watchlistFeedLoading || pinnedWorkspacesLoading"
            @click="refreshWorkspaceTray"
          />
        </div>
        <template v-else-if="trayPinnedWorkspaces.length">
          <article
            v-for="item in trayPinnedWorkspaces"
            :key="item.id"
            class="tray-card clickable"
            @click="openPinnedWorkspace(item)"
          >
            <div>
              <strong>{{ item.name }}</strong>
              <small>{{ t(workspacePageTitleKeys[item.page] || 'app.title') }}</small>
            </div>
          </article>
        </template>

        <p v-else class="muted tray-empty">
          {{ t('workbench.noPinnedWorkspaces') }}
        </p>

        <div class="tray-head recent-head">
          <h3>{{ t('workbench.recentMunicipalities') }}</h3>
          <Tag :value="String(workbench.recentMunicipalities.length)" severity="secondary" />
        </div>
        <article
          v-for="item in workbench.recentMunicipalities"
          :key="item.id"
          class="tray-card clickable"
          @click="openRecentMunicipality(item)"
        >
          <div>
            <strong>{{ item.label }}</strong>
            <small>{{ item.region || '' }}</small>
          </div>
        </article>

        <p v-if="!workbench.recentMunicipalities.length" class="muted tray-empty">
          {{ t('workbench.noRecentPlaces') }}
        </p>
      </section>
    </div>
  </Dialog>
</template>

<style scoped>
  .workspace-tray {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) repeat(3, minmax(0, 1fr));
    gap: 1rem;
  }

  .tray-column,
  .tray-head {
    display: grid;
    gap: 0.85rem;
  }

  .tray-state {
    display: grid;
    gap: 0.8rem;
  }

  .tray-column {
    align-content: start;
    padding: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--content-border-strong) 24%);
    border-radius: var(--radius-md);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 95%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  .tray-head {
    grid-template-columns: 1fr auto;
    align-items: center;
  }

  .recent-head {
    margin-top: 0.6rem;
  }

  .tray-head h3 {
    margin: 0;
    font-size: 1rem;
  }

  .tray-column--wide {
    align-content: start;
  }

  .quick-actions {
    display: grid;
    gap: 0.85rem;
  }

  .quick-action {
    display: grid;
    gap: 0.25rem;
    text-align: left;
    padding: 1rem 1.05rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    color: inherit;
    box-shadow: var(--shadow-sm);
    transition:
      transform 140ms ease,
      border-color 140ms ease,
      box-shadow 140ms ease;
  }

  .quick-action:not(.quick-action--static) {
    cursor: pointer;
  }

  .quick-action:not(.quick-action--static):hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 18%, var(--border) 82%);
    box-shadow: var(--accent-shadow);
  }

  .quick-action strong {
    font-size: 0.92rem;
  }

  .quick-action small {
    color: var(--text-muted);
  }

  .quick-action--static {
    cursor: default;
  }

  .tray-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow: var(--shadow-sm);
  }

  .tray-card.clickable {
    cursor: pointer;
    transition:
      transform 140ms ease,
      border-color 140ms ease,
      background 140ms ease;
  }

  .tray-card.clickable:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 20%, var(--border) 80%);
    background: color-mix(in srgb, var(--surface-subtle) 92%, var(--primary) 8%);
    box-shadow: var(--accent-shadow);
  }

  .tray-card strong {
    display: block;
  }

  .tray-card small {
    color: var(--text-muted);
  }

  .tray-empty {
    margin: 0;
    padding: 0.35rem 0;
  }

  @media (max-width: 980px) {
    .workspace-tray {
      grid-template-columns: 1fr;
    }
  }
</style>
