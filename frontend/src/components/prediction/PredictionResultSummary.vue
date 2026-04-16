<script setup lang="ts">
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import { useFormat } from '../../composables/useFormat'
  import type { PredictionFormData, PredictionResultPayload } from './types'

  const props = defineProps<{
    result: PredictionResultPayload
    form: PredictionFormData
    comparisonUrl: string
    currentMunicipality: string
    municipalityRegion?: string | null
    effectiveSize: number | null
    propertyTypeLabel: string
  }>()

  const emit = defineEmits<{
    'open-market': []
    'open-map': []
    'open-analysis': []
    'refresh-context': []
  }>()

  const { t } = useI18n()
  const { fmt, fmtCurrency, formatType } = useFormat()

  const featureEntries = computed(() => Object.entries(props.result.features_used || {}))
  const sizeLabel = computed(() =>
    props.effectiveSize ? `${fmt(props.effectiveSize, 1)} m²` : t('common.noData'),
  )
</script>

<template>
  <section class="prediction-result-shell">
    <div class="prediction-result-head">
      <div class="prediction-result-copy">
        <p class="eyebrow subtle">{{ t('predict.result') }}</p>
        <h3>{{ t('predict.valuationStory') }}</h3>
        <p class="result-copy">{{ t('predict.valuationBody') }}</p>
      </div>

      <div class="prediction-result-rail">
        <span>{{ t('predict.modelUsed') }}</span>
        <strong>{{ props.result.model_used }}</strong>
        <small v-if="props.result.routing_mode">{{ props.result.routing_mode }}</small>
        <small v-else>{{ t('predict.previewReadinessBody') }}</small>
      </div>
    </div>

    <div class="prediction-result-value">
      <span>{{ t('predict.predictedPrice') }}</span>
      <strong>{{ fmtCurrency(props.result.predicted_price_eur) }}</strong>
    </div>

    <div class="prediction-result-meta">
      <article>
        <span>{{ t('predict.propertyType') }}</span>
        <strong>{{ props.propertyTypeLabel || formatType(props.form.property_type) || '-' }}</strong>
      </article>
      <article>
        <span>{{ t('predict.municipality') }}</span>
        <strong>{{ props.currentMunicipality || t('predict.municipalityPlaceholder') }}</strong>
        <small>{{ props.municipalityRegion || t('common.noData') }}</small>
      </article>
      <article>
        <span>{{ t('predict.size') }}</span>
        <strong>{{ sizeLabel }}</strong>
      </article>
    </div>

    <div class="prediction-result-actions">
      <Button
        severity="primary"
        icon="pi pi-table"
        :label="t('nav.market')"
        @click="emit('open-market')"
      />
      <Button
        severity="secondary"
        text
        icon="pi pi-map"
        :label="t('nav.map')"
        @click="emit('open-map')"
      />
      <Button
        severity="secondary"
        text
        icon="pi pi-search"
        :label="t('nav.analysis')"
        @click="emit('open-analysis')"
      />
      <a :href="props.comparisonUrl" target="_blank" rel="noreferrer" class="result-link">
        {{ t('predict.compareOnPortal') }}
      </a>
    </div>

    <div class="prediction-result-features">
      <div class="prediction-result-features-head">
        <h4>{{ t('predict.featuresUsed') }}</h4>
        <Button
          severity="secondary"
          text
          :label="t('common.retry')"
          @click="emit('refresh-context')"
        />
      </div>
      <div v-if="featureEntries.length" class="feature-chip-grid">
        <span v-for="[key, value] in featureEntries" :key="key" class="feature-chip">
          {{ key }}: {{ value }}
        </span>
      </div>
      <p v-else class="feature-empty">{{ t('common.noData') }}</p>
    </div>
  </section>
</template>

<style scoped>
  .prediction-result-shell {
    display: grid;
    gap: 1rem;
    padding: 1.15rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--primary) 16%, transparent), transparent 36%),
      radial-gradient(circle at top right, color-mix(in srgb, var(--secondary) 12%, transparent), transparent 30%),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 92%, var(--primary) 8%),
        var(--surface-panel)
      );
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 18px 36px color-mix(in srgb, var(--shadow-color) 15%, transparent);
  }

  .prediction-result-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .prediction-result-copy {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
  }

  .prediction-result-copy h3,
  .prediction-result-features h4 {
    margin: 0;
    font-family: var(--font-display);
    letter-spacing: -0.03em;
  }

  .prediction-result-copy h3 {
    font-size: clamp(1.35rem, 2.2vw, 1.85rem);
  }

  .result-copy,
  .prediction-result-rail small,
  .feature-empty {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .prediction-result-rail {
    display: grid;
    justify-items: end;
    gap: 0.2rem;
    text-align: right;
  }

  .prediction-result-rail span,
  .prediction-result-value span,
  .prediction-result-meta span {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--text-soft);
  }

  .prediction-result-rail strong {
    font-size: 0.98rem;
    letter-spacing: -0.02em;
  }

  .prediction-result-value {
    display: grid;
    gap: 0.15rem;
  }

  .prediction-result-value strong {
    font-size: clamp(2.15rem, 4vw, 3.15rem);
    line-height: 1.02;
    letter-spacing: -0.05em;
  }

  .prediction-result-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.75rem;
  }

  .prediction-result-meta article {
    display: grid;
    gap: 0.25rem;
    padding: 0.9rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--primary) 26%);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 94%, var(--primary) 6%);
    box-shadow: inset 0 1px 0 var(--content-glow);
  }

  .prediction-result-meta article strong {
    font-size: 1rem;
    line-height: 1.25;
  }

  .prediction-result-meta article small {
    color: var(--text-muted);
  }

  .prediction-result-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    align-items: center;
  }

  .result-link {
    display: inline-flex;
    align-items: center;
    min-height: 2.6rem;
    padding: 0.2rem 0.15rem;
    color: var(--primary);
    text-decoration: none;
    font-weight: 700;
  }

  .result-link:hover {
    color: var(--primary-strong);
    text-decoration: underline;
    text-underline-offset: 0.2em;
  }

  .prediction-result-features {
    display: grid;
    gap: 0.7rem;
    padding-top: 0.2rem;
    border-top: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
  }

  .prediction-result-features-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .prediction-result-features-head h4 {
    font-size: 0.98rem;
  }

  .feature-chip-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .feature-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.42rem 0.68rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 92%, var(--primary) 8%);
    color: var(--text);
    font-size: 0.88rem;
  }

  @media (max-width: 900px) {
    .prediction-result-head,
    .prediction-result-rail {
      justify-items: start;
      text-align: left;
    }

    .prediction-result-head {
      flex-direction: column;
    }
    .prediction-result-actions,
    .prediction-result-features-head {
      align-items: stretch;
    }

    .prediction-result-actions :deep(.p-button),
    .result-link {
      width: 100%;
      justify-content: center;
    }
  }
</style>
