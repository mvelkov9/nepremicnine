<script setup lang="ts">
  import { computed } from 'vue'
  import Button from 'primevue/button'
  import ProgressBar from 'primevue/progressbar'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../../components/EmptyState.vue'
  import MetricCard from '../../components/MetricCard.vue'
  import SectionPanel from '../../components/SectionPanel.vue'
  import { formatDateTime, formatNumber } from '../../utils/format'
  import type {
    ModelSourceMeta,
    ModelSourceOption,
    ModelTrainingCard,
    ModelTrainingStatus,
  } from './types'

  const props = withDefaults(
    defineProps<{
      eyebrow: string
      title: string
      description: string
      modelValue: string
      options: ModelSourceOption[]
      selectedSourceMeta?: ModelSourceMeta | null
      selectedSourcePath?: string
      trainingLocked?: boolean
      activeStatus?: ModelTrainingStatus | null
      statusLabel?: string
      statusSeverity?: string
      stageLabel?: string
      runCards?: ModelTrainingCard[]
      actionLabel: string
      actionHint: string
      lockedHint: string
      error?: string
    }>(),
    {
      options: () => [],
      selectedSourceMeta: null,
      selectedSourcePath: '',
      trainingLocked: false,
      activeStatus: null,
      statusLabel: '',
      statusSeverity: 'secondary',
      stageLabel: '',
      runCards: () => [],
      error: '',
    },
  )

  const emit = defineEmits<{
    'update:modelValue': [value: string]
    train: []
    retry: []
  }>()

  const { t } = useI18n()

  const selectedSource = computed({
    get: () => props.modelValue,
    set: (value: string) => emit('update:modelValue', value),
  })

  const sourceSummary = computed(() => {
    const source = props.selectedSourceMeta
    if (!source) return null
    const rows = source.row_count ?? source.rows ?? 0
    const updatedAt = source.uploaded_at || source.updated_at
    return {
      title: source.original_name || source.name || t('common.noData'),
      rows: `${formatNumber(rows)} ${t('data.rows')}`,
      updatedAt: updatedAt ? formatDateTime(updatedAt) : t('common.noData'),
      path: props.selectedSourcePath || source.relative_path || t('common.noData'),
    }
  })

  const progressValue = computed(() => {
    const value = Number(props.activeStatus?.progress ?? 0)
    if (Number.isNaN(value)) return 0
    return Math.max(0, Math.min(100, value))
  })

  const currentError = computed(() => props.error || props.activeStatus?.error || '')

  function progressLabel(value?: number | null) {
    if (value == null || Number.isNaN(Number(value))) return '0%'
    return `${formatNumber(value, { maximumFractionDigits: 0 })}%`
  }
</script>

<template>
  <SectionPanel
    class="model-workspace"
    :eyebrow="eyebrow"
    :title="title"
    :description="description"
  >
    <div class="workspace-grid">
      <div class="workspace-source">
        <label class="workspace-field">
          <span>{{ t('model.selectDataset') }}</span>
          <Select
            v-model="selectedSource"
            :options="options"
            option-label="label"
            option-value="value"
            class="w-full"
            :placeholder="t('model.selectDataset')"
            :disabled="trainingLocked"
          />
        </label>

        <div v-if="sourceSummary" class="workspace-source-card">
          <span class="eyebrow subtle">{{ t('model.selectedSource') }}</span>
          <strong>{{ sourceSummary.title }}</strong>
          <p>{{ sourceSummary.path }}</p>
          <p class="muted">{{ sourceSummary.rows }} &middot; {{ sourceSummary.updatedAt }}</p>
        </div>
      </div>

      <aside class="workspace-actions">
        <Button
          class="workspace-train-btn"
          icon="pi pi-play"
          :label="actionLabel"
          :disabled="!modelValue || trainingLocked"
          @click="emit('train')"
        />
        <p class="muted">
          {{ trainingLocked ? lockedHint : actionHint }}
        </p>
      </aside>
    </div>

    <div v-if="activeStatus" class="workspace-live">
      <div class="workspace-live-head">
        <div class="workspace-live-copy">
          <span class="eyebrow subtle">{{ t('model.trainingStatus') }}</span>
          <h3>{{ stageLabel || t('common.loading') }}</h3>
        </div>
        <Tag :severity="statusSeverity" :value="statusLabel || t('common.loading')" rounded />
      </div>

      <ProgressBar :value="progressValue" :show-value="false" />

      <div class="workspace-live-meta">
        <div>
          <span>{{ t('model.trainingProgress') }}</span>
          <strong>{{ progressLabel(activeStatus.progress) }}</strong>
        </div>
        <div>
          <span>{{ t('model.elapsed') }}</span>
          <strong>
            {{
              activeStatus.elapsed_sec != null
                ? `${formatNumber(activeStatus.elapsed_sec, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
                : t('common.noData')
            }}
          </strong>
        </div>
        <div>
          <span>{{ t('model.currentModel') }}</span>
          <strong>
            {{
              activeStatus.current_model
                ? activeStatus.current_model === 'global'
                  ? t('model.globalModel')
                  : activeStatus.current_model === 'done'
                    ? t('model.completedStage')
                    : activeStatus.current_model
                : t('common.noData')
            }}
          </strong>
        </div>
        <div>
          <span>{{ t('model.currentModelProgress') }}</span>
          <strong>{{ progressLabel(activeStatus.current_model_progress) }}</strong>
        </div>
      </div>

      <div v-if="runCards.length" class="workspace-metric-grid">
        <MetricCard
          v-for="card in runCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
          :meta="card.meta"
          :tone="card.tone || 'default'"
        />
      </div>
    </div>

    <div v-if="currentError" class="workspace-error" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="currentError" />
      <Button
        size="small"
        severity="secondary"
        outlined
        icon="pi pi-refresh"
        :label="t('common.retry')"
        @click="emit('retry')"
      />
    </div>
  </SectionPanel>
</template>

<style scoped>
  .model-workspace {
    gap: 1rem;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 14%, transparent),
        transparent 24%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
  }

  .workspace-grid,
  .workspace-source,
  .workspace-actions,
  .workspace-live,
  .workspace-live-copy,
  .workspace-error {
    display: grid;
    gap: 0.9rem;
  }

  .workspace-grid {
    grid-template-columns: minmax(0, 1.15fr) minmax(240px, 0.7fr);
    align-items: start;
  }

  .workspace-source,
  .workspace-actions {
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--primary) 22%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-panel-muted);
    box-shadow: var(--shadow-sm);
  }

  .workspace-field {
    display: grid;
    gap: 0.45rem;
  }

  .workspace-field > span {
    color: var(--text-soft);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .workspace-source-card {
    display: grid;
    gap: 0.3rem;
    padding-top: 0.35rem;
    border-top: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
  }

  .workspace-source-card strong {
    font-size: 1.02rem;
    line-height: 1.2;
  }

  .workspace-source-card p {
    margin: 0;
    color: var(--text-soft);
    word-break: break-word;
  }

  .workspace-train-btn {
    width: 100%;
  }

  .workspace-live {
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--warning) 24%, var(--border) 76%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--warning) 12%, transparent),
        transparent 26%
      ),
      var(--surface-panel-muted);
    box-shadow: var(--shadow-sm);
  }

  .workspace-live-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .workspace-live-copy h3 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.18rem, 2vw, 1.6rem);
    line-height: 1;
  }

  .workspace-live-meta {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .workspace-live-meta div {
    display: grid;
    gap: 0.22rem;
    padding: 0.8rem 0.85rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(in srgb, var(--surface-card-strong) 94%, var(--primary) 6%);
  }

  .workspace-live-meta span {
    color: var(--text-soft);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .workspace-live-meta strong {
    font-size: 0.98rem;
    line-height: 1.2;
  }

  .workspace-metric-grid {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .workspace-error {
    padding-top: 0.4rem;
  }

  @media (max-width: 980px) {
    .workspace-grid,
    .workspace-live-meta,
    .workspace-metric-grid {
      grid-template-columns: 1fr 1fr;
    }
  }

  @media (max-width: 720px) {
    .workspace-grid,
    .workspace-live-meta,
    .workspace-metric-grid {
      grid-template-columns: 1fr;
    }

    .workspace-live-head {
      flex-direction: column;
    }
  }
</style>
