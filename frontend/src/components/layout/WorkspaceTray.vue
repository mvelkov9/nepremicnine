<script setup lang="ts">
  import { computed, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import Tag from 'primevue/tag'
  import {
    buildWorkspaceRoute,
    describeRoute,
    toLocationQuery,
    workspacePageTitleKeys,
  } from '../../constants/workbench'
  import { useUiStore } from '../../stores/ui'
  import { useWorkbenchStore } from '../../stores/workbench'

  const { t } = useI18n()
  const router = useRouter()
  const ui = useUiStore()
  const workbench = useWorkbenchStore()

  const municipalityCompareItems = computed(() =>
    workbench.compareTray.filter((item) => item.entity_type === 'municipality'),
  )

  watch(
    () => ui.workspaceTrayOpen,
    async (open) => {
      if (!open) return
      await Promise.allSettled([workbench.fetchWatchlistFeed(), workbench.fetchWorkspaces()])
    },
  )

  function closeTray() {
    ui.toggleWorkspaceTray(false)
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
      <section class="tray-column">
        <div class="tray-head">
          <h3>{{ t('workbench.compareTray') }}</h3>
          <Tag :value="String(workbench.compareTray.length)" severity="secondary" />
        </div>

        <article v-for="item in workbench.compareTray" :key="item.id" class="tray-card">
          <div>
            <strong>{{ item.label }}</strong>
            <small>{{ item.region || item.entity_type }}</small>
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
          <Tag :value="String(workbench.watchlistFeed.length)" severity="secondary" />
        </div>

        <article
          v-for="item in workbench.watchlistFeed"
          :key="item.id"
          class="tray-card clickable"
          @click="openFeedItem(item)"
        >
          <div>
            <strong>{{ item.display_label }}</strong>
            <small>{{ item.headline_label }}: {{ item.headline_value ?? '-' }}</small>
          </div>
          <Tag
            v-if="item.trend_value != null"
            :value="`${item.trend_value}%`"
            :severity="item.trend_value >= 0 ? 'success' : 'danger'"
          />
        </article>

        <p v-if="!workbench.watchlistFeed.length" class="muted tray-empty">
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
          <Tag :value="String(workbench.pinnedWorkspaces.length)" severity="secondary" />
        </div>

        <article
          v-for="item in workbench.pinnedWorkspaces"
          :key="item.id"
          class="tray-card clickable"
          @click="openPinnedWorkspace(item)"
        >
          <div>
            <strong>{{ item.name }}</strong>
            <small>{{ t(workspacePageTitleKeys[item.page] || 'app.title') }}</small>
          </div>
        </article>

        <p v-if="!workbench.pinnedWorkspaces.length" class="muted tray-empty">
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
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
  }

  .tray-column,
  .tray-head {
    display: grid;
    gap: 0.85rem;
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

  .tray-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-soft)) 86%,
      transparent
    );
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
    border-color: color-mix(in srgb, var(--primary) 40%, var(--border) 60%);
    background: color-mix(
      in srgb,
      var(--primary) 6%,
      var(--surface-card-strong, var(--surface-soft)) 94%
    );
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
