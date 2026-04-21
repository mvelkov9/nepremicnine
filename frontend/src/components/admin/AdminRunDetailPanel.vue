<script setup lang="ts">
  import { computed } from 'vue'
  import Button from 'primevue/button'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../EmptyState.vue'
  import type { AdminRunDetail, AdminRunSummary } from '../../types/api'
  import { formatDateTime, formatNumber } from '../../utils/format'

  const props = defineProps<{
    title: string
    eyebrow?: string
    description?: string
    runs?: AdminRunSummary[]
    selectedRun?: AdminRunDetail | null
    selectedRunId?: string | null
    loading?: boolean
    error?: string | null
    runType?: 'prepare' | 'training'
  }>()

  const emit = defineEmits<{
    select: [runId: string]
  }>()

  const { t } = useI18n()

  const metrics = computed(() => props.selectedRun?.metrics || [])
  const timeline = computed(() => props.selectedRun?.timeline || [])
  const artifacts = computed(() => props.selectedRun?.artifacts || [])
  const activeRunId = computed(() => props.selectedRunId || props.selectedRun?.id || '')
  const contextRows = computed(() => {
    const context = props.selectedRun?.context || {}
    return Object.entries(context)
      .filter(
        ([, value]) => value != null && value !== '' && (!Array.isArray(value) || value.length),
      )
      .slice(0, 8)
  })

  function metricValue(metric: Record<string, unknown>) {
    const suffix = metric.suffix ? ` ${metric.suffix}` : ''
    return `${metric.value ?? 0}${suffix}`
  }

  function contextValue(value: unknown) {
    if (Array.isArray(value)) return `${value.length} ${t('common.items')}`
    if (typeof value === 'object' && value) return JSON.stringify(value)
    return String(value)
  }

  function timelineSeverity(state: unknown) {
    if (state === 'done') return 'success'
    if (state === 'active') return 'warn'
    if (state === 'error') return 'danger'
    return 'secondary'
  }

  function timelineStateLabel(state: unknown) {
    if (state === 'done') return t('model.stages.done')
    if (state === 'active') return t('admin.active')
    if (state === 'error') return t('common.error')
    return t('workbench.pending')
  }

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

  function runSummaryLabel(item: {
    summary?: string | null
    stage?: string | null
    status?: string | null
  }) {
    return item.summary || runStageLabel(item.stage) || runStatusLabel(item.status)
  }

  function progressLabel(value: unknown) {
    if (value == null || Number.isNaN(Number(value))) return '0%'
    return `${formatNumber(value, { maximumFractionDigits: 0 })}%`
  }
</script>

<template>
  <section class="card run-detail-panel">
    <div class="run-detail-head">
      <div>
        <p v-if="eyebrow" class="eyebrow subtle">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
        <p v-if="description" class="muted">{{ description }}</p>
      </div>
    </div>

    <div class="run-detail-shell">
      <div class="run-detail-list">
        <Button
          v-for="item in runs || []"
          :key="item.id"
          class="run-list-item"
          :severity="activeRunId === item.id ? 'contrast' : 'secondary'"
          :outlined="activeRunId !== item.id"
          :aria-pressed="activeRunId === item.id"
          @click="emit('select', item.id)"
        >
          <div class="run-list-copy">
            <strong>{{ item.title }}</strong>
            <small>{{ runSummaryLabel(item) }}</small>
            <small>{{ formatDateTime(item.updated_at || item.created_at) }}</small>
          </div>
          <span class="run-list-meta">{{ progressLabel(item.progress) }}</span>
        </Button>

        <EmptyState
          v-if="!(runs || []).length"
          icon="pi pi-folder-open"
          :message="t('workbench.noRuns')"
        />
      </div>

      <div class="run-detail-body">
        <div v-if="loading" class="muted">{{ t('common.loading') }}</div>

        <template v-else-if="selectedRun">
          <div class="run-detail-summary">
            <div>
              <strong>{{ selectedRun.title }}</strong>
              <p class="muted">
                {{ runSummaryLabel(selectedRun) }}
              </p>
              <small class="muted">{{
                formatDateTime(selectedRun.updated_at || selectedRun.created_at)
              }}</small>
            </div>
            <span class="run-progress">{{ progressLabel(selectedRun.progress) }}</span>
          </div>

          <div v-if="metrics.length" class="run-metric-grid">
            <article v-for="metric in metrics" :key="String(metric.label)" class="run-metric-card">
              <span>{{ metric.label }}</span>
              <strong>{{ metricValue(metric) }}</strong>
            </article>
          </div>

          <div class="run-section-grid">
            <section class="run-section">
              <h3>{{ t('workbench.timeline') }}</h3>
              <div v-if="timeline.length" class="timeline-list">
                <div v-for="item in timeline" :key="String(item.label)" class="timeline-row">
                  <strong>{{ item.label }}</strong>
                  <Tag
                    :severity="timelineSeverity(item.state)"
                    :value="timelineStateLabel(item.state)"
                  />
                </div>
              </div>
              <p v-else class="muted">{{ t('common.noData') }}</p>
            </section>

            <section class="run-section">
              <h3>{{ t('workbench.artifacts') }}</h3>
              <div v-if="artifacts.length" class="artifact-list">
                <div v-for="item in artifacts" :key="String(item.label)" class="artifact-row">
                  <strong>{{ item.label }}</strong>
                  <code>{{ item.value }}</code>
                </div>
              </div>
              <p v-else class="muted">{{ t('common.noData') }}</p>
            </section>
          </div>

          <section class="run-section">
            <h3>{{ t('workbench.runContext') }}</h3>
            <div v-if="contextRows.length" class="context-grid">
              <div v-for="[key, value] in contextRows" :key="key" class="context-row">
                <span>{{ key }}</span>
                <strong>{{ contextValue(value) }}</strong>
              </div>
            </div>
            <p v-else class="muted">{{ t('common.noData') }}</p>
          </section>
        </template>

        <EmptyState v-else-if="error" icon="pi pi-exclamation-triangle" :message="error" />

        <EmptyState v-else icon="pi pi-compass" :message="t('workbench.selectRunHint')" />
      </div>
    </div>
  </section>
</template>

<style scoped>
  .run-detail-panel,
  .run-detail-head,
  .run-detail-list,
  .run-detail-body,
  .run-section,
  .timeline-list,
  .artifact-list,
  .context-grid {
    display: grid;
    gap: 1rem;
  }

  .run-detail-head h2,
  .run-section h3 {
    margin: 0;
    font-family: var(--font-display);
  }

  .run-detail-shell {
    display: grid;
    grid-template-columns: minmax(320px, 0.92fr) minmax(0, 1.08fr);
    gap: 1rem;
    align-items: start;
  }

  :deep(.run-list-item.p-button) {
    justify-content: space-between;
    align-items: flex-start;
    text-align: left;
    white-space: normal;
    padding: 0.9rem 1rem;
    border-radius: 1rem;
  }

  .run-list-copy {
    display: grid;
    gap: 0.2rem;
    min-width: 0;
  }

  .run-list-copy small,
  .run-detail-summary p {
    color: var(--text-soft);
  }

  .run-list-copy strong,
  .run-list-copy small,
  .run-detail-summary strong,
  .context-row strong {
    overflow-wrap: anywhere;
    word-break: break-word;
  }

  .run-list-meta,
  .run-progress {
    font-size: 1.1rem;
    font-weight: 800;
    color: var(--primary);
  }

  .run-detail-summary {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-subtle);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .run-metric-grid,
  .run-section-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .run-metric-card,
  .run-section,
  .context-row {
    padding: 0.9rem 1rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
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

  .run-metric-card span,
  .context-row span {
    display: block;
    margin-bottom: 0.3rem;
    color: var(--text-muted);
    font-size: var(--text-sm);
    font-weight: 700;
  }

  .timeline-row,
  .artifact-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.85rem;
  }

  .run-list-item :deep(.p-button-label) {
    width: 100%;
    min-width: 0;
  }

  .artifact-row code {
    max-width: 100%;
    overflow-wrap: anywhere;
    font-size: var(--text-sm);
  }

  @media (max-width: 1120px) {
    .run-detail-shell,
    .run-metric-grid,
    .run-section-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
