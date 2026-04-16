<script setup lang="ts">
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import Tag from 'primevue/tag'
  import ComparableCard from '../ComparableCard.vue'
  import EmptyState from '../EmptyState.vue'
  import LoadingSpinner from '../LoadingSpinner.vue'
  import MetricCard from '../MetricCard.vue'
  import { useFormat } from '../../composables/useFormat'
  import type { TransactionRecord } from '../../types/api'

  type MapBuildingFlagKey =
    | 'novogradnja'
    | 'has_garaza'
    | 'has_klet'
    | 'has_shramba'
    | 'has_terasa'
    | 'stavba_je_dokoncana'
    | 'ddv_vkljucen'

  interface MapOverviewRecord {
    municipality: string
    slug?: string
    region?: string
    avg_price?: number | null
    avg_price_per_m2?: number | null
    count?: number
    latest_year?: string | null
    median_price?: number | null
    price_band?: string | null
    year?: string | null
    source_label?: string | null
  }

  interface MapDetailCommonRecord {
    count?: number
    price_band?: string | null
    year?: string | null
    source_label?: string | null
    property_type?: string | null
    size_m2?: number | null
    price_eur?: number | null
    avg_price?: number | null
    price_per_m2?: number | null
    avg_price_per_m2?: number | null
    latest_year?: string | null
    year_built?: number | null
    rooms?: number | null
    floor?: number | null
    lega_v_stavbi?: string | null
    median_price?: number | null
  }

  type MapDetailRecord =
    | (TransactionRecord & MapDetailCommonRecord & Partial<Record<MapBuildingFlagKey, number | boolean | null>>)
    | (MapOverviewRecord & MapDetailCommonRecord & Partial<Record<MapBuildingFlagKey, number | boolean | null>>)

  const props = defineProps<{
    record: MapDetailRecord | null
    detailMode: 'transaction' | 'overview'
    detailLoading: boolean
    comparables: TransactionRecord[]
    defaultYear: string | number | null
    comparisonUrl: string
    dialogTitle: string
    canOpenMunicipality: boolean
    municipalityDisabledReason: string
    canUseForPrediction: boolean
    predictionDisabledReason: string
    canOpenAnalysis: boolean
    analysisDisabledReason: string
  }>()

  const visible = defineModel<boolean>('visible', { required: true })

  const emit = defineEmits<{
    openMunicipality: []
    useForPrediction: []
    openAnalysis: []
  }>()

  const { t } = useI18n()
  const { fmt, fmtCurrency, formatType } = useFormat()

  const buildingFlags = computed(() => [
    { key: 'novogradnja', label: t('predict.novogradnja') },
    { key: 'has_garaza', label: t('predict.hasGaraza') },
    { key: 'has_klet', label: t('predict.hasKlet') },
    { key: 'has_shramba', label: t('predict.hasShramba') },
    { key: 'has_terasa', label: t('predict.hasTerasa') },
    { key: 'stavba_je_dokoncana', label: t('predict.stavbaDokoncana') },
    { key: 'ddv_vkljucen', label: t('predict.ddvVkljucen') },
  ] as const)

  function toNumber(value: unknown): number | null {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value)
      return Number.isFinite(parsed) ? parsed : null
    }
    return null
  }

  function displayValue(value: unknown, fallback = '-') {
    if (value === null || value === undefined) return fallback
    if (typeof value === 'string') return value.trim() || fallback
    return String(value)
  }

  function metricNumber(value: unknown, decimals = 0) {
    const numeric = toNumber(value)
    return numeric == null ? '-' : fmt(numeric, decimals)
  }

  function metricCurrency(value: unknown, decimals = 0) {
    const numeric = toNumber(value)
    return numeric == null ? '-' : fmtCurrency(numeric, decimals)
  }

  function propertyTypeLabel(value: unknown) {
    const normalized = displayValue(value, '')
    return normalized ? formatType(normalized) : '-'
  }

  function recordYearLabel(record: MapDetailRecord) {
    return displayValue(record.year || record.source_label)
  }
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    maximizable
    class="map-detail-dialog"
    :header="dialogTitle"
    :style="{ width: 'min(98vw, 1280px)' }"
    :breakpoints="{ '1280px': '96vw', '768px': '100vw' }"
  >
    <div v-if="props.record" class="detail-dialog">
      <div class="detail-summary">
        <div>
          <span class="eyebrow">{{
            props.detailMode === 'transaction' ? t('map.transactions') : t('map.topMunicipalities')
          }}</span>
          <h2>{{ props.record.municipality }}</h2>
          <p class="muted">{{ displayValue(props.record.region) }}</p>
        </div>
        <Tag
          v-if="props.record.price_band"
          :value="t(`map.${props.record.price_band}`)"
          :severity="
            props.record.price_band === 'high'
              ? 'danger'
              : props.record.price_band === 'mid'
                ? 'warn'
                : 'success'
          "
        />
      </div>

      <div class="detail-metrics">
        <MetricCard
          :label="t('map.price')"
          :value="metricCurrency(props.detailMode === 'transaction' ? props.record.price_eur : props.record.avg_price)"
        />
        <MetricCard
          :label="t('dashboard.pricePerM2')"
          :value="metricCurrency(props.detailMode === 'transaction' ? props.record.price_per_m2 : props.record.avg_price_per_m2)"
        />
        <MetricCard
          :label="props.detailMode === 'transaction' ? t('predict.size') : t('map.transactions')"
          :value="props.detailMode === 'transaction' ? `${metricNumber(props.record.size_m2, 1)} m²` : metricNumber(props.record.count)"
        />
        <MetricCard
          :label="t('map.year')"
          :value="props.detailMode === 'transaction' ? recordYearLabel(props.record) : displayValue(props.record.latest_year || props.defaultYear)"
        />
      </div>

      <div class="detail-grid">
        <section class="detail-section detail-section-main">
          <h3>{{ t('map.detailTitle') }}</h3>
          <dl class="detail-list">
            <div v-if="props.detailMode === 'transaction'">
              <dt>{{ t('predict.propertyType') }}</dt>
              <dd>{{ propertyTypeLabel(props.record.property_type) }}</dd>
            </div>
            <div>
              <dt>{{ t('map.region') }}</dt>
              <dd>{{ displayValue(props.record.region) }}</dd>
            </div>
            <div v-if="props.detailMode === 'transaction'">
              <dt>{{ t('predict.yearBuilt') }}</dt>
              <dd>{{ displayValue(props.record.year_built) }}</dd>
            </div>
            <div v-if="props.detailMode === 'transaction'">
              <dt>{{ t('predict.rooms') }}</dt>
              <dd>{{ displayValue(props.record.rooms) }}</dd>
            </div>
            <div v-if="props.detailMode === 'transaction'">
              <dt>{{ t('predict.floor') }}</dt>
              <dd>{{ displayValue(props.record.floor) }}</dd>
            </div>
            <div v-if="props.detailMode === 'transaction'">
              <dt>{{ t('predict.legaVStavbi') }}</dt>
              <dd>{{ displayValue(props.record.lega_v_stavbi) }}</dd>
            </div>
            <div v-if="props.detailMode === 'transaction'">
              <dt>{{ t('map.sourceYear') }}</dt>
              <dd>{{ recordYearLabel(props.record) }}</dd>
            </div>
            <div v-if="props.detailMode === 'overview'">
              <dt>{{ t('map.medianPrice') }}</dt>
              <dd>{{ metricCurrency(props.record.median_price) }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="props.detailMode === 'transaction'" class="detail-section detail-section-flags">
          <h3>{{ t('predict.buildingFlags') }}</h3>
          <div class="flag-grid">
            <span
              v-for="flag in buildingFlags"
              :key="flag.key"
              class="flag-chip"
              :class="{ active: props.record[flag.key] }"
            >
              {{ flag.label }}
            </span>
          </div>
        </section>

        <section class="detail-section detail-section-comparables" :aria-busy="props.detailLoading">
          <h3>{{ t('predict.comparablesTitle') }}</h3>
          <LoadingSpinner v-if="props.detailLoading" :label="t('common.loading')" />
          <div v-else-if="props.comparables.length" class="comparables-list">
            <ComparableCard
              v-for="item in props.comparables"
              :key="`${item.slug}-${item.price_eur}-${item.size_m2}`"
              :item="item"
            />
          </div>
          <EmptyState
            v-else
            icon="pi pi-info-circle"
            :message="props.detailMode === 'transaction' ? t('predict.noComparables') : t('map.municipalitySummaryHint')"
          />
        </section>
      </div>

      <section class="detail-actions-panel">
        <div class="detail-action">
          <Button
            icon="pi pi-building"
            :label="t('map.openMunicipality')"
            :disabled="!props.canOpenMunicipality"
            :aria-describedby="!props.canOpenMunicipality ? 'map-municipality-hint' : undefined"
            @click="emit('openMunicipality')"
          />
          <small v-if="!props.canOpenMunicipality" id="map-municipality-hint" class="action-hint">
            {{ props.municipalityDisabledReason || t('common.noData') }}
          </small>
        </div>
        <div class="detail-action">
          <Button
            severity="secondary"
            outlined
            icon="pi pi-chart-line"
            :label="t('map.useForPrediction')"
            :disabled="!props.canUseForPrediction"
            :aria-describedby="!props.canUseForPrediction ? 'map-prediction-hint' : undefined"
            @click="emit('useForPrediction')"
          />
          <small v-if="!props.canUseForPrediction" id="map-prediction-hint" class="action-hint">
            {{ props.predictionDisabledReason || t('map.drawerHint') }}
          </small>
        </div>
        <div class="detail-action">
          <Button
            severity="secondary"
            outlined
            icon="pi pi-search"
            :label="t('nav.analysis')"
            :disabled="!props.canOpenAnalysis"
            :aria-describedby="!props.canOpenAnalysis ? 'map-analysis-hint' : undefined"
            @click="emit('openAnalysis')"
          />
          <small v-if="!props.canOpenAnalysis" id="map-analysis-hint" class="action-hint">
            {{ props.analysisDisabledReason || t('map.drawerHint') }}
          </small>
        </div>
        <Button
          as="a"
          :href="props.comparisonUrl"
          target="_blank"
          rel="noreferrer"
          class="detail-link"
          severity="contrast"
          outlined
          icon="pi pi-external-link"
          :label="t('predict.compareOnPortal')"
        />
      </section>
    </div>
  </Dialog>
</template>

<style scoped>
  .detail-dialog,
  .detail-metrics {
    display: grid;
    gap: 1rem;
  }

  .detail-summary,
  .detail-actions,
  .comparable-top,
  .comparable-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .detail-summary {
    align-items: flex-start;
  }

  .detail-summary h2 {
    margin: 0.2rem 0 0;
    font-size: clamp(1.28rem, 2vw, 1.58rem);
    line-height: 1.04;
    text-wrap: balance;
  }

  .detail-summary > div {
    min-width: 0;
  }

  .detail-summary .muted {
    margin: 0.25rem 0 0;
  }

  .detail-metrics {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .detail-grid {
    display: grid;
    grid-template-columns: minmax(0, 0.95fr) minmax(0, 1fr) minmax(320px, 1.1fr);
    gap: 1rem;
    align-items: start;
  }

  .detail-section {
    display: grid;
    gap: 0.9rem;
    padding: 1rem 1.05rem;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 94%, transparent);
    min-width: 0;
    box-shadow: var(--shadow-sm);
  }

  .detail-section-main {
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 92%, var(--primary) 8%);
  }

  .detail-section-comparables {
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--secondary) 8%
    );
  }

  .detail-section h3 {
    margin: 0;
  }

  .detail-list {
    display: grid;
    gap: 0.75rem;
    margin: 0;
    min-width: 0;
  }

  .detail-list div {
    display: grid;
    gap: 0.2rem;
  }

  .detail-list dt {
    color: var(--text-muted);
    font-size: var(--text-sm);
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .detail-list dd {
    margin: 0;
    font-weight: 600;
  }

  .flag-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.65rem;
  }

  .flag-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.6rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 72%, transparent);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-muted)) 94%, transparent);
    color: var(--text-muted);
    font-weight: 700;
  }

  .flag-chip.active {
    color: var(--text);
    border-color: color-mix(in srgb, var(--success) 24%, transparent);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-muted)) 92%,
      var(--success) 8%
    );
  }

  .comparables-list {
    display: grid;
    gap: 0.75rem;
    min-width: 0;
  }

  .detail-actions-panel {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
    padding: 1rem 1.05rem;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    border-radius: var(--radius-md);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 94%,
      var(--primary) 6%
    );
    box-shadow: var(--shadow-sm);
  }

  .detail-actions-panel :deep(.p-button) {
    width: 100%;
    justify-content: center;
  }

  .detail-action {
    display: grid;
    gap: 0.4rem;
    min-width: 0;
  }

  .action-hint {
    color: var(--text-muted);
    font-size: var(--text-xs);
    line-height: 1.4;
  }

  .detail-link {
    text-decoration: none;
    display: block;
  }

  .map-detail-dialog :deep(.p-dialog-header) {
    align-items: flex-start;
    padding: 1.15rem 1.35rem;
    border-bottom: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--primary) 16%, transparent), transparent 46%),
      linear-gradient(180deg, color-mix(in srgb, var(--primary-overlay) 72%, transparent), transparent 42%),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, var(--primary) 4%),
        color-mix(in srgb, var(--surface-strong) 94%, var(--surface-card-strong) 6%)
      );
    color: var(--text);
    box-shadow: inset 0 1px 0 var(--content-glow);
  }

  .map-detail-dialog :deep(.p-dialog-title),
  .map-detail-dialog :deep(.p-dialog-header-icon) {
    color: inherit;
  }

  .map-detail-dialog :deep(.p-dialog-header-actions .p-button) {
    background: color-mix(in srgb, var(--surface-elevated) 92%, var(--primary) 8%);
    border-color: color-mix(in srgb, var(--control-border) 72%, var(--primary) 28%);
    color: var(--text);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 8px 18px color-mix(in srgb, var(--shadow-color) 10%, transparent);
  }

  .map-detail-dialog :deep(.p-dialog-header-actions .p-button:hover) {
    background: color-mix(in srgb, var(--surface-elevated) 78%, var(--primary) 22%);
    border-color: color-mix(in srgb, var(--control-border-hover) 68%, var(--primary) 32%);
    transform: translateY(-1px);
  }

  .map-detail-dialog :deep(.p-dialog-header-actions .p-button:focus-visible) {
    outline: none;
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 0 0 4px color-mix(in srgb, var(--primary) 22%, transparent);
  }

  .map-detail-dialog :deep(.p-dialog-content) {
    padding: 1.25rem 1.35rem 1.35rem;
    background: color-mix(in srgb, var(--surface-card-strong) 94%, transparent);
  }

  @media (max-width: 1280px) {
    .detail-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .detail-section-comparables {
      grid-column: 1 / -1;
    }

    .detail-metrics,
    .detail-actions-panel {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 900px) {
    .detail-grid,
    .detail-actions-panel,
    .detail-metrics {
      grid-template-columns: 1fr;
    }

    .detail-section-comparables {
      grid-column: auto;
    }

    .map-detail-dialog :deep(.p-dialog-content) {
      padding: 1rem;
    }
  }
</style>


