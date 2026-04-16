<script setup lang="ts">
  import { useI18n } from 'vue-i18n'
  import Tag from 'primevue/tag'
  import SectionPanel from '../SectionPanel.vue'
  import { useFormat } from '../../composables/useFormat'
  import type { BenchmarkSegmentSummary } from '../../types/api'

  const props = defineProps<{
    eyebrow: string
    title: string
    kind: 'region' | 'type' | 'year'
    items: BenchmarkSegmentSummary[]
  }>()

  const { t } = useI18n()
  const { formatCurrency, formatPercent, formatType } = useFormat()

  function segmentLabel(segment: string) {
    return props.kind === 'type' ? formatType(segment) : segment
  }

  function sampleSeverity(count: number) {
    if (count < 10) return 'danger'
    if (count < 25) return 'warning'
    return 'success'
  }

  function sampleLabel(count: number) {
    if (count < 10) return t('benchmark.smallSample')
    if (count < 25) return t('benchmark.moderateSample')
    return t('benchmark.strongSample')
  }
</script>

<template>
  <SectionPanel class="benchmark-segment-panel" :eyebrow="eyebrow" :title="title">
    <div class="benchmark-segment-list">
      <article v-for="(item, index) in items" :key="item.segment" class="benchmark-segment-card">
        <div class="benchmark-segment-index">
          {{ String(index + 1).padStart(2, '0') }}
        </div>

        <div class="benchmark-segment-copy">
          <div class="benchmark-segment-head">
            <strong>{{ segmentLabel(item.segment) }}</strong>
            <Tag
              :value="`${item.count} ${t('map.transactions').toLowerCase()}`"
              :severity="sampleSeverity(item.count)"
            />
          </div>

          <p class="benchmark-segment-summary">
            {{ t('benchmark.avgGainTitle') }}: {{ formatCurrency(item.avg_gain_eur) }} ·
            {{ t('benchmark.winRateTitle') }}:
            {{ formatPercent(item.model_win_rate, { minimumFractionDigits: 0 }) }}
          </p>

          <small class="benchmark-segment-sample">{{ sampleLabel(item.count) }}</small>
        </div>

        <dl class="benchmark-segment-stats">
          <div>
            <dt>{{ t('benchmark.avgGainTitle') }}</dt>
            <dd>{{ formatCurrency(item.avg_gain_eur) }}</dd>
          </div>
          <div>
            <dt>{{ t('benchmark.medianLead') }}</dt>
            <dd>{{ formatCurrency(item.median_gain_eur) }}</dd>
          </div>
          <div>
            <dt>{{ t('benchmark.winRateTitle') }}</dt>
            <dd>{{ formatPercent(item.model_win_rate, { minimumFractionDigits: 0 }) }}</dd>
          </div>
        </dl>
      </article>
    </div>
  </SectionPanel>
</template>

<style scoped>
  .benchmark-segment-list {
    display: grid;
    gap: 0.85rem;
  }

  .benchmark-segment-card {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 1rem;
    align-items: start;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 130%
      ),
      var(--surface-panel-muted);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .benchmark-segment-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.35rem;
    height: 2.35rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 26%, var(--border) 74%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 120%
      ),
      color-mix(in srgb, var(--surface-card-strong) 88%, var(--primary) 12%);
    color: color-mix(in srgb, var(--primary) 72%, var(--text) 28%);
    font-family: var(--font-display);
    font-size: 0.92rem;
    font-weight: 800;
    letter-spacing: 0.08em;
  }

  .benchmark-segment-copy {
    display: grid;
    gap: 0.3rem;
    min-width: 0;
  }

  .benchmark-segment-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .benchmark-segment-head strong {
    min-width: 0;
    font-size: 1rem;
    letter-spacing: -0.02em;
    text-wrap: balance;
  }

  .benchmark-segment-summary,
  .benchmark-segment-sample {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.88rem;
    line-height: 1.5;
  }

  .benchmark-segment-stats {
    display: grid;
    grid-column: 2 / -1;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 0.7rem;
    margin: 0;
  }

  .benchmark-segment-stats div {
    display: grid;
    gap: 0.2rem;
    padding: 0.7rem 0.8rem;
    border-radius: calc(var(--radius-sm) - 2px);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--content-border-strong) 24%);
    background: var(--surface-subtle);
  }

  .benchmark-segment-stats dt {
    color: var(--text-soft);
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .benchmark-segment-stats dd {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 900px) {
    .benchmark-segment-stats {
      grid-column: 1 / -1;
    }
  }

  @media (max-width: 640px) {
    .benchmark-segment-card {
      grid-template-columns: 1fr;
    }

    .benchmark-segment-index {
      width: 2.1rem;
      height: 2.1rem;
    }

    .benchmark-segment-head {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
