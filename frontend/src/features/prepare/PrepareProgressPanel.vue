<script setup lang="ts">
  import Button from 'primevue/button'
  import ProgressBar from 'primevue/progressbar'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../../components/EmptyState.vue'
  import PageHeader from '../../components/PageHeader.vue'
  import type { PrepareTimelineStep } from './types'
  import { formatNumber } from '../../utils/format'

  const props = defineProps<{
    eyebrow: string
    title: string
    description: string
    statusLabel: string
    statusSeverity: string
    progress: number
    currentLabel?: string | null
    timeline: PrepareTimelineStep[]
    error?: string | null
  }>()

  const emit = defineEmits<{
    retry: []
  }>()

  const { t } = useI18n()

  function progressLabel(value: number | null | undefined) {
    if (value == null || Number.isNaN(Number(value))) return '0%'
    return `${formatNumber(value, { maximumFractionDigits: 0 })}%`
  }
</script>

<template>
  <section class="prepare-progress-panel">
    <PageHeader compact :eyebrow="eyebrow" :title="title" :description="description">
      <template #actions>
        <Tag :severity="statusSeverity" :value="statusLabel" />
      </template>
    </PageHeader>

    <div class="prepare-progress-summary">
      <div class="prepare-progress-head">
        <span class="prepare-progress-pct">{{ progressLabel(progress) }}</span>
        <div class="prepare-progress-copy">
          <span class="prepare-progress-stage">{{ title }}</span>
          <span v-if="currentLabel" class="prepare-progress-subtitle">{{ currentLabel }}</span>
        </div>
      </div>

      <div class="prepare-progress-tags">
        <Tag :severity="statusSeverity" :value="statusLabel" />
        <Tag :severity="'info'" :value="progressLabel(progress)" />
        <Tag :severity="'contrast'" :value="currentLabel || title || t('common.noData')" />
      </div>
    </div>

    <ProgressBar :value="progress" :show-value="false" class="prepare-progress-bar" />

    <div class="prepare-timeline-shell">
      <div class="prepare-timeline">
        <div
          v-for="step in timeline"
          :key="step.key"
          class="prepare-timeline-step"
          :class="`prepare-timeline-step--${step.state}`"
        >
          <span class="prepare-timeline-dot" />
          <div class="prepare-timeline-copy">
            <div class="prepare-timeline-label-row">
              <span class="prepare-timeline-label">{{ step.label }}</span>
              <span v-if="step.meta" class="prepare-timeline-meta">{{ step.meta }}</span>
            </div>
            <span v-if="step.detail" class="prepare-timeline-detail">{{ step.detail }}</span>

            <div v-if="step.substeps?.length" class="prepare-spatial-substeps">
              <div
                v-for="substep in step.substeps"
                :key="substep.key"
                class="prepare-spatial-sub"
                :class="`prepare-spatial-sub--${substep.state}`"
              >
                <span class="prepare-spatial-dot" />
                <span class="prepare-spatial-name">{{ substep.label }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="error" class="state-card state-card-stack" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
      <div class="state-card-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="emit('retry')"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
  .prepare-progress-panel {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .prepare-progress-summary {
    display: grid;
    gap: 0.75rem;
  }

  .prepare-progress-head {
    display: flex;
    align-items: center;
    gap: 0.95rem;
  }

  .prepare-progress-pct {
    min-width: 4.25rem;
    font-size: 2rem;
    line-height: 1;
    font-weight: 800;
    color: var(--primary);
  }

  .prepare-progress-copy {
    display: grid;
    gap: 0.15rem;
    min-width: 0;
  }

  .prepare-progress-stage {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--text);
  }

  .prepare-progress-subtitle {
    font-size: 0.8rem;
    color: var(--text-muted);
    word-break: break-word;
  }

  .prepare-progress-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .prepare-progress-bar {
    margin-bottom: 0.15rem;
  }

  .prepare-timeline-shell {
    padding: 0.85rem 1rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 82%, var(--content-border-strong) 18%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      color-mix(in srgb, var(--surface-muted) 76%, var(--surface));
  }

  .prepare-timeline {
    display: grid;
    gap: 0.15rem;
  }

  .prepare-timeline-step {
    position: relative;
    display: flex;
    gap: 0.85rem;
    padding: 0.6rem 0;
  }

  .prepare-timeline-step:not(:last-child)::before {
    content: '';
    position: absolute;
    left: 0.6rem;
    top: 1.55rem;
    bottom: -0.4rem;
    width: 2px;
    background: var(--border);
  }

  .prepare-timeline-step--done:not(:last-child)::before {
    background: var(--success);
  }

  .prepare-timeline-step--active:not(:last-child)::before {
    background: color-mix(in srgb, var(--primary) 40%, var(--border));
  }

  .prepare-timeline-dot {
    width: 1.2rem;
    height: 1.2rem;
    margin-top: 0.1rem;
    border-radius: 50%;
    border: 2px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
    position: relative;
    z-index: 1;
  }

  .prepare-timeline-step--done .prepare-timeline-dot {
    background: var(--success);
    border-color: var(--success);
  }

  .prepare-timeline-step--done .prepare-timeline-dot::after {
    content: '';
    position: absolute;
    inset: 3px;
    background: var(--surface-strong);
    clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
  }

  .prepare-timeline-step--active .prepare-timeline-dot {
    border-color: var(--primary);
    background: var(--primary);
    animation: pulse-dot 1.4s ease-in-out infinite;
  }

  .prepare-timeline-step--error .prepare-timeline-dot {
    border-color: var(--danger);
    background: var(--danger);
  }

  .prepare-timeline-copy {
    display: grid;
    gap: 0.15rem;
    min-width: 0;
  }

  .prepare-timeline-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .prepare-timeline-label {
    font-weight: 700;
    font-size: 0.88rem;
  }

  .prepare-timeline-step--pending .prepare-timeline-label {
    color: var(--text-muted);
  }

  .prepare-timeline-meta,
  .prepare-timeline-detail {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .prepare-timeline-detail {
    color: var(--primary);
  }

  .prepare-spatial-substeps {
    display: grid;
    gap: 0.35rem;
    margin-top: 0.35rem;
    padding-left: 0.1rem;
  }

  .prepare-spatial-sub {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.8rem;
  }

  .prepare-spatial-dot {
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 50%;
    border: 2px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }

  .prepare-spatial-sub--done .prepare-spatial-dot {
    border-color: var(--success);
    background: var(--success);
  }

  .prepare-spatial-sub--active .prepare-spatial-dot {
    border-color: var(--primary);
    background: var(--primary);
    animation: pulse-dot 1.4s ease-in-out infinite;
  }

  .prepare-spatial-sub--pending .prepare-spatial-name {
    color: var(--text-muted);
  }

  .prepare-spatial-sub--active .prepare-spatial-name {
    color: var(--primary);
    font-weight: 700;
  }

  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }

  .state-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  @keyframes pulse-dot {
    0%,
    100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--primary) 40%, transparent);
    }
    50% {
      box-shadow: 0 0 0 5px transparent;
    }
  }

  @media (max-width: 720px) {
    .prepare-progress-head,
    .prepare-timeline-label-row {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
