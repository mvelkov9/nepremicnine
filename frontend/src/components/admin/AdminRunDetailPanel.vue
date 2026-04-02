<script setup lang="ts">
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Tag from 'primevue/tag'
  import EmptyState from '../EmptyState.vue'
  import type { AdminRunDetail, AdminRunSummary } from '../../types/api'
  import { formatDateTime } from '../../utils/format'

  const props = defineProps<{
    title: string
    eyebrow?: string
    description?: string
    runs?: AdminRunSummary[]
    selectedRun?: AdminRunDetail | null
    loading?: boolean
  }>()

  const emit = defineEmits<{
    select: [runId: string]
  }>()

  const { t } = useI18n()

  const metrics = computed(() => props.selectedRun?.metrics || [])
  const timeline = computed(() => props.selectedRun?.timeline || [])
  const artifacts = computed(() => props.selectedRun?.artifacts || [])
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
          severity="secondary"
          outlined
          @click="emit('select', item.id)"
        >
          <div class="run-list-copy">
            <strong>{{ item.title }}</strong>
            <small>{{ item.summary || item.stage || item.status }}</small>
            <small>{{ formatDateTime(item.updated_at || item.created_at) }}</small>
          </div>
          <span class="run-list-meta">{{ item.progress ?? 0 }}%</span>
        </Button>

        <EmptyState v-if="!(runs || []).length" icon="📁" :message="t('workbench.noRuns')" />
      </div>

      <div class="run-detail-body">
        <div v-if="loading" class="muted">{{ t('common.loading') }}</div>

        <template v-else-if="selectedRun">
          <div class="run-detail-summary">
            <div>
              <strong>{{ selectedRun.title }}</strong>
              <p class="muted">
                {{ selectedRun.summary || selectedRun.stage || selectedRun.status }}
              </p>
              <small class="muted">{{
                formatDateTime(selectedRun.updated_at || selectedRun.created_at)
              }}</small>
            </div>
            <span class="run-progress">{{ selectedRun.progress ?? 0 }}%</span>
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
                    :value="String(item.state || 'pending')"
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

        <EmptyState v-else icon="🧭" :message="t('workbench.selectRunHint')" />
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
    grid-template-columns: minmax(260px, 0.7fr) minmax(0, 1.3fr);
    gap: 1rem;
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
  }

  .run-list-copy small,
  .run-detail-summary p,
  .eyebrow.subtle {
    color: var(--text-soft);
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
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface-soft-subtle) 82%, white 18%);
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
    border: 1px solid var(--border);
    background: linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft));
  }

  .run-metric-card span,
  .context-row span {
    display: block;
    margin-bottom: 0.3rem;
    color: var(--text-muted);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .timeline-row,
  .artifact-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.85rem;
  }

  .artifact-row code {
    max-width: 100%;
    overflow-wrap: anywhere;
    font-size: 0.78rem;
  }

  @media (max-width: 980px) {
    .run-detail-shell,
    .run-metric-grid,
    .run-section-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
