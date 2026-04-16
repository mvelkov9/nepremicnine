<script setup lang="ts">
  import { RouterLink, type RouteLocationRaw } from 'vue-router'
  import Button from 'primevue/button'
  import EmptyState from '../../components/EmptyState.vue'
  import LoadingSpinner from '../../components/LoadingSpinner.vue'
  import { useI18n } from 'vue-i18n'

  type WorkspaceItem = {
    id: number
    name: string
    subtitle: string
    to: RouteLocationRaw
  }

  type FeedItem = {
    id: string
    label: string
    summary: string
    trend?: string
    to?: RouteLocationRaw | null
  }

  type WorkflowItem = {
    id: string
    label: string
    subtitle: string
    to: RouteLocationRaw
  }

  defineProps<{
    pinnedWorkspaces: WorkspaceItem[]
    watchlistFeed: FeedItem[]
    recentWorkflows: WorkflowItem[]
    workspacesLoading: boolean
    workspacesError: string
    watchlistLoading: boolean
    watchlistError: string
  }>()

  const emit = defineEmits<{
    (event: 'retry-workspaces'): void
    (event: 'retry-watchlist'): void
  }>()

  const { t } = useI18n()
</script>

<template>
  <div class="workspace-hub">
    <article class="workspace-column">
      <div class="workspace-column-head">
        <div>
          <span class="workspace-column-kicker">{{ t('workbench.pinnedWorkspaces') }}</span>
          <h3>{{ t('workbench.resumeWork') }}</h3>
        </div>
      </div>

      <LoadingSpinner
        v-if="workspacesLoading && !pinnedWorkspaces.length"
        :label="t('common.loading')"
      />
      <div
        v-else-if="workspacesError && !pinnedWorkspaces.length"
        class="state-card state-card-stack"
        role="alert"
      >
        <EmptyState icon="pi pi-exclamation-triangle" :message="workspacesError" />
        <div class="state-card-actions">
          <Button
            icon="pi pi-refresh"
            severity="secondary"
            outlined
            :label="t('common.retry')"
            @click="emit('retry-workspaces')"
          />
        </div>
      </div>
      <div v-else-if="pinnedWorkspaces.length" class="workspace-list">
        <RouterLink
          v-for="item in pinnedWorkspaces"
          :key="item.id"
          :to="item.to"
          class="workspace-card"
        >
          <strong>{{ item.name }}</strong>
          <small>{{ item.subtitle }}</small>
        </RouterLink>
      </div>
      <EmptyState v-else :message="t('workbench.noPinnedWorkspaces')" />
    </article>

    <article class="workspace-column">
      <div class="workspace-column-head">
        <div>
          <span class="workspace-column-kicker">{{ t('workbench.watchlistFeed') }}</span>
          <h3>{{ t('workbench.watchlistFeed') }}</h3>
        </div>
      </div>

      <LoadingSpinner
        v-if="watchlistLoading && !watchlistFeed.length"
        :label="t('common.loading')"
      />
      <div
        v-else-if="watchlistError && !watchlistFeed.length"
        class="state-card state-card-stack"
        role="alert"
      >
        <EmptyState icon="pi pi-exclamation-triangle" :message="watchlistError" />
        <div class="state-card-actions">
          <Button
            icon="pi pi-refresh"
            severity="secondary"
            outlined
            :label="t('common.retry')"
            @click="emit('retry-watchlist')"
          />
        </div>
      </div>
      <div v-else-if="watchlistFeed.length" class="workspace-list">
        <template v-for="item in watchlistFeed" :key="item.id">
          <RouterLink v-if="item.to" :to="item.to" class="workspace-card workspace-card--feed">
            <strong>{{ item.label }}</strong>
            <small>
              {{ item.summary }}
              <template v-if="item.trend"> | {{ item.trend }} </template>
            </small>
          </RouterLink>
          <article v-else class="workspace-card workspace-card--feed workspace-card--static">
            <strong>{{ item.label }}</strong>
            <small>
              {{ item.summary }}
              <template v-if="item.trend"> | {{ item.trend }} </template>
            </small>
          </article>
        </template>
      </div>
      <EmptyState v-else :message="t('workbench.noWatchlistFeed')" />
    </article>

    <article class="workspace-column">
      <div class="workspace-column-head">
        <div>
          <span class="workspace-column-kicker">{{ t('workbench.recentWorkflows') }}</span>
          <h3>{{ t('workbench.recentWorkflows') }}</h3>
        </div>
      </div>

      <div v-if="recentWorkflows.length" class="workspace-list">
        <RouterLink
          v-for="item in recentWorkflows"
          :key="item.id"
          :to="item.to"
          class="workspace-card"
        >
          <strong>{{ item.label }}</strong>
          <small>{{ item.subtitle }}</small>
        </RouterLink>
      </div>
      <EmptyState v-else :message="t('workbench.noRecentWorkflows')" />
    </article>
  </div>
</template>

<style scoped>
  .workspace-hub {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .workspace-column {
    display: grid;
    gap: 0.85rem;
    align-content: start;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      var(--shadow-sm);
  }

  .workspace-column:last-child {
    grid-column: 1 / -1;
  }

  .workspace-column-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .workspace-column-kicker {
    display: inline-flex;
    margin-bottom: 0.2rem;
    color: var(--text-soft);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .workspace-column h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 800;
    letter-spacing: -0.01em;
  }

  .workspace-list {
    display: grid;
    gap: 0.65rem;
  }

  .workspace-card {
    position: relative;
    display: grid;
    gap: 0.28rem;
    min-height: 5.5rem;
    padding: 0.9rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    background: var(--surface-subtle);
    color: inherit;
    text-decoration: none;
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease;
  }

  .workspace-card::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 0.24rem;
    background: linear-gradient(180deg, var(--primary), var(--secondary));
    opacity: 0.9;
  }

  .workspace-card:hover,
  .workspace-card:focus-visible {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border) 66%);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .workspace-card strong {
    font-size: 0.95rem;
  }

  .workspace-card small {
    color: var(--text-muted);
    line-height: 1.5;
  }

  .workspace-card--feed {
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 10%, transparent),
        transparent 32%
      ),
      var(--surface-subtle);
  }

  .workspace-card--static {
    cursor: default;
  }

  .workspace-card--static:hover,
  .workspace-card--static:focus-visible {
    transform: none;
  }

  @media (max-width: 1100px) {
    .workspace-hub {
      grid-template-columns: 1fr;
    }

    .workspace-column:last-child {
      grid-column: auto;
    }
  }
</style>
