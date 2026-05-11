<script setup lang="ts">
  import { computed } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../EmptyState.vue'
  import LoadingSpinner from '../LoadingSpinner.vue'
  import type { AdminRunSummary } from '../../types/api'
  import { formatDateTime, formatNumber } from '../../utils/format'

  const props = withDefaults(
    defineProps<{
      eyebrow: string
      title: string
      description?: string
      items: AdminRunSummary[]
      loading?: boolean
      error?: string
      to: string
      runType: 'prepare' | 'training'
    }>(),
    {
      description: '',
      loading: false,
      error: '',
    },
  )

  const emit = defineEmits<{
    retry: []
  }>()

  const { t } = useI18n()

  const listItems = computed(() => props.items.slice(0, 5))

  function translatedLabel(key: string, fallback: string, params?: Record<string, unknown>) {
    const label = t(key, params || {})
    return label === key ? fallback : label
  }

  function prepareStageLabel(stage?: string | null) {
    if (!stage) return ''
    const unknownYear = t('prepare.unknownYear')
    switch (stage) {
      case 'queued':
        return t('prepare.stageQueued')
      case 'initializing':
        return t('prepare.stageInitializing')
      case 'loading_sources':
        return t('prepare.stageLoadingSources')
      case 'loading_pair':
        return t('prepare.stageLoadingPair', { label: unknownYear })
      case 'building_rows':
        return t('prepare.stageBuildingRows', { label: unknownYear })
      case 'enriching_buildings':
        return t('prepare.stageEnrichingBuildings', { label: unknownYear })
      case 'enriching_land':
        return t('prepare.stageEnrichingLand', { label: unknownYear })
      case 'finalizing_pair':
        return t('prepare.stageFinalizingPair', { label: unknownYear })
      case 'merging_outputs':
        return t('prepare.stageMergingOutputs')
      case 'spatial_enrichment_merged':
        return t('prepare.stageSpatialEnrichmentMerged', { rows: '...' })
      case 'completed':
        return t('prepare.stageCompleted')
      case 'error':
        return t('prepare.stageError')
      default:
        return stage
    }
  }

  function runStageLabel(stage?: string | null) {
    if (!stage) return ''
    if (props.runType === 'prepare') return prepareStageLabel(stage)
    return translatedLabel(`model.stages.${stage}`, stage)
  }

  function runStatusLabel(status?: string | null) {
    return status ? t(`model.status.${status}`) : t('common.noData')
  }

  function runSummaryLabel(item: Pick<AdminRunSummary, 'summary' | 'stage' | 'status'>) {
    return item.summary || runStageLabel(item.stage) || runStatusLabel(item.status)
  }

  function runStatusSeverity(status?: string | null) {
    if (status === 'completed') return 'success'
    if (status === 'failed') return 'danger'
    if (status === 'queued' || status === 'running') return 'warn'
    return 'secondary'
  }

  function progressLabel(value?: number | null) {
    if (value == null || Number.isNaN(Number(value))) return ''
    return `${formatNumber(value, { maximumFractionDigits: 0 })}%`
  }

  function runLink(item: AdminRunSummary) {
    return {
      path: props.to,
      query: {
        run: item.id,
        tab: props.runType === 'prepare' ? 'monitor' : 'history',
      },
    }
  }
</script>

<template>
  <section class="admin-home-run-list">
    <div class="run-list-head">
      <div class="run-list-copy">
        <p class="eyebrow subtle">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
        <p v-if="description" class="run-list-description">{{ description }}</p>
      </div>

      <Button
        :as="RouterLink"
        :to="to"
        severity="secondary"
        outlined
        icon="pi pi-arrow-right"
        icon-pos="right"
        :label="t('common.open')"
      />
    </div>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />

    <div v-else-if="error" class="run-list-state" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
      <Button
        severity="secondary"
        outlined
        icon="pi pi-refresh"
        :label="t('common.retry')"
        @click="emit('retry')"
      />
    </div>

    <div v-else-if="listItems.length" class="run-list-stack">
      <RouterLink v-for="item in listItems" :key="item.id" :to="runLink(item)" class="run-row">
        <div class="run-row-top">
          <div class="run-row-copy">
            <strong>{{ item.title }}</strong>
            <p>{{ runSummaryLabel(item) }}</p>
          </div>
          <Tag :severity="runStatusSeverity(item.status)" :value="runStatusLabel(item.status)" />
        </div>

        <div class="run-row-meta">
          <small>{{ formatDateTime(item.updated_at || item.created_at) }}</small>
          <small v-if="progressLabel(item.progress)">{{ progressLabel(item.progress) }}</small>
        </div>
      </RouterLink>
    </div>

    <EmptyState v-else icon="pi pi-folder-open" :message="t('common.noData')" />
  </section>
</template>

<style scoped>
  .admin-home-run-list {
    display: grid;
    gap: 0.95rem;
    padding: 1.2rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .run-list-head,
  .run-row-top,
  .run-row-meta,
  .run-list-state {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.8rem;
  }

  .run-list-copy {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
  }

  .run-list-copy h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.12rem, 1.8vw, 1.34rem);
    line-height: 1.04;
    text-wrap: balance;
  }

  .run-list-description {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.5;
  }

  .run-list-state {
    flex-direction: column;
  }

  .run-list-stack {
    display: grid;
    gap: 0.8rem;
  }

  .run-row {
    display: grid;
    gap: 0.55rem;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--primary) 26%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 10px 22px color-mix(in srgb, var(--shadow-color) 10%, transparent);
    color: inherit;
    text-decoration: none;
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .run-row:hover,
  .run-row:focus-visible {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 46%, transparent);
    box-shadow: var(--accent-shadow);
  }

  .run-row p,
  .run-row small {
    margin: 0;
    color: var(--text-soft);
  }

  .run-row strong {
    font-size: 0.98rem;
    line-height: 1.3;
  }

  .run-row-meta {
    align-items: center;
    flex-wrap: wrap;
  }

  @media (max-width: 740px) {
    .run-list-head,
    .run-row-top,
    .run-row-meta {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
