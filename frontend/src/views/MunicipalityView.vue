<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '../components/AppIcon.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import { useStatsStore } from '../stores/stats'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()

  const loading = ref(false)
  const error = ref('')

  function fmt(value: number | null | undefined, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtPercent(value: number | null | undefined) {
    return formatPercent(value)
  }

  function formatType(value: string) {
    return getPropertyTypeLabel(value, t)
  }

  async function loadMunicipality() {
    loading.value = true
    error.value = ''

    try {
      await stats.fetchMunicipalityDetail(route.params.slug)
    } catch (err) {
      stats.resetMunicipalityDetail()
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  watch(
    () => route.params.slug,
    () => {
      loadMunicipality()
    },
    { immediate: true },
  )

  const detail = computed(() => stats.municipalityDetail)

  const yearTrendRows = computed(() =>
    (detail.value?.year_trend || []).map((item: any) => ({
      year: item.year,
      count: item.count,
      median_price: item.median_price,
      median_price_per_m2: item.median_price_per_m2,
    })),
  )

  const heroMetrics = computed(() => [
    {
      label: t('dashboard.transactions'),
      value: fmt(detail.value?.overview?.count),
      meta: t('municipality.coverageWindow', {
        from: detail.value?.overview?.earliest_year || '—',
        to: detail.value?.overview?.latest_year || '—',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(detail.value?.overview?.median_price),
      meta: `${fmt(detail.value?.overview?.avg_area, 1)} m²`,
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(detail.value?.overview?.median_price_per_m2),
      meta: detail.value?.region || '—',
    },
  ])

  const recentTransactions = computed(() => detail.value?.recent_transactions || [])

  function shareStyle(share: number | null | undefined) {
    return { width: `${Math.max(10, Math.round((share || 0) * 100))}%` }
  }

  function openPrediction(transaction: any = null) {
    router.push({
      name: 'prediction',
      query: {
        municipality: detail.value?.municipality || '',
        property_type: transaction?.property_type || 'stanovanje',
        size_m2: transaction?.size_m2 || detail.value?.overview?.avg_area || '',
        year_built: transaction?.year_built || '',
        price_eur: transaction?.price_eur || '',
      },
    })
  }

  function openMap() {
    router.push({
      name: 'map',
      query: {
        municipality: detail.value?.municipality || '',
        region: detail.value?.region || '',
      },
    })
  }
</script>

<template>
  <div class="municipality-page">
    <div v-if="loading" class="state-card">
      <LoadingSpinner :label="t('common.loading')" />
    </div>

    <p v-else-if="error" class="state-card error-text">{{ error }}</p>

    <template v-else-if="detail">
      <section class="municipality-hero">
        <div>
          <span class="eyebrow">{{ t('municipality.pageEyebrow') }}</span>
          <h1>{{ detail.municipality }}</h1>
          <p>
            {{ t('municipality.heroBody', { region: detail.region || '—' }) }}
          </p>

          <div class="hero-actions">
            <Button
              icon="pi pi-calculator"
              :label="t('municipality.openPrediction')"
              @click="openPrediction()"
            />
            <Button
              icon="pi pi-map"
              severity="secondary"
              outlined
              :label="t('municipality.openMap')"
              @click="openMap"
            />
          </div>
        </div>

        <div class="hero-side">
          <MetricCard
            v-for="card in heroMetrics"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :meta="card.meta"
            tone="success"
          />

          <article class="metric-card accent">
            <span>{{ t('municipality.regionStanding') }}</span>
            <strong> #{{ detail.market_position?.region_rank_by_price_per_m2 || '—' }} </strong>
            <p>
              {{
                t('municipality.activityRankLabel', {
                  count: detail.market_position?.region_rank_by_activity || '—',
                })
              }}
            </p>
          </article>
        </div>
      </section>

      <section class="content-grid">
        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow subtle">{{ t('dashboard.priceTrend') }}</span>
              <h2>{{ t('municipality.yearTrend') }}</h2>
            </div>
          </div>

          <DataTable
            v-if="yearTrendRows.length"
            :value="yearTrendRows"
            size="small"
            striped-rows
            responsive-layout="scroll"
          >
            <Column field="year" :header="t('map.yearFilter')" sortable />
            <Column field="count" :header="t('dashboard.transactions')" sortable>
              <template #body="{ data }">{{ fmt(data.count) }}</template>
            </Column>
            <Column field="median_price" :header="t('dashboard.medianPrice')" sortable>
              <template #body="{ data }">{{ formatCurrency(data.median_price) }}</template>
            </Column>
            <Column field="median_price_per_m2" :header="t('dashboard.pricePerM2')" sortable>
              <template #body="{ data }">{{ formatCurrency(data.median_price_per_m2) }}</template>
            </Column>
          </DataTable>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow subtle">{{ t('dashboard.propertyTypes') }}</span>
              <h2>{{ t('municipality.propertyMix') }}</h2>
            </div>
          </div>

          <div v-if="detail.property_type_mix?.length" class="mix-list">
            <div v-for="item in detail.property_type_mix" :key="item.property_type" class="mix-row">
              <div class="mix-copy">
                <strong>{{ formatType(item.property_type) }}</strong>
                <small>{{ fmtPercent(item.share) }}</small>
              </div>
              <div class="mix-bar">
                <span :style="shareStyle(item.share)"></span>
              </div>
            </div>
          </div>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
        </article>
      </section>

      <section class="content-grid bottom-grid">
        <article class="panel panel-wide">
          <div class="panel-head">
            <div>
              <span class="eyebrow subtle">{{ t('municipality.recentTransactions') }}</span>
              <h2>{{ t('municipality.latestTransactions') }}</h2>
            </div>
          </div>

          <DataTable
            v-if="recentTransactions.length"
            :value="recentTransactions"
            size="small"
            striped-rows
            responsive-layout="scroll"
          >
            <Column :header="t('predict.propertyType')">
              <template #body="{ data }">{{ formatType(data.property_type) || '—' }}</template>
            </Column>
            <Column :header="t('predict.size')">
              <template #body="{ data }">{{ fmt(data.size_m2, 1) }} m²</template>
            </Column>
            <Column :header="t('dashboard.medianPrice')">
              <template #body="{ data }">{{ formatCurrency(data.price_eur) }}</template>
            </Column>
            <Column header="€/m²">
              <template #body="{ data }">{{ formatCurrency(data.price_per_m2) }}</template>
            </Column>
            <Column :header="t('map.yearFilter')">
              <template #body="{ data }">{{ data.year || '—' }}</template>
            </Column>
            <Column :header="t('common.actions')">
              <template #body="{ data }">
                <Button
                  size="small"
                  severity="secondary"
                  outlined
                  icon="pi pi-calculator"
                  :label="t('municipality.useForPrediction')"
                  @click="openPrediction(data)"
                />
              </template>
            </Column>
          </DataTable>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow subtle">{{ t('municipality.relatedMarkets') }}</span>
              <h2>{{ t('municipality.nearbyBenchmarks') }}</h2>
            </div>
          </div>

          <div v-if="detail.related_municipalities?.length" class="related-list">
            <RouterLink
              v-for="item in detail.related_municipalities"
              :key="item.slug"
              :to="`/obcine/${item.slug}`"
              class="related-card"
            >
              <div class="related-info">
                <strong>{{ item.municipality }}</strong>
                <small>{{ item.region || '—' }}</small>
                <span class="related-count"
                >{{ fmt(item.count) }} {{ t('dashboard.transactions') }}</span
                >
              </div>
              <div class="related-right">
                <div class="related-metric">
                  <strong>{{ formatCurrency(item.median_price_per_m2) }}</strong>
                  <small>/m²</small>
                </div>
                <i class="pi pi-arrow-right related-arrow"></i>
              </div>
            </RouterLink>
          </div>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .municipality-page {
    display: grid;
    gap: 1.2rem;
  }

  .municipality-hero,
  .panel,
  .metric-card,
  .state-card {
    border-radius: 1.6rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    box-shadow: var(--shadow-sm);
  }

  .municipality-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.95fr);
    gap: 1.1rem;
    padding: 1.35rem;
    background:
      linear-gradient(135deg, var(--surface-strong), var(--surface-soft)),
      radial-gradient(circle at top left, color-mix(in srgb, var(--primary) 15%, transparent), transparent 32%),
      radial-gradient(circle at right, color-mix(in srgb, var(--warning) 12%, transparent), transparent 26%);
  }

  .municipality-hero h1,
  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  .municipality-hero h1 {
    font-size: clamp(2rem, 4vw, 3.2rem);
    line-height: 1.05;
  }

  .municipality-hero p,
  .metric-card p,
  .mix-copy small,
  .related-card small,
  .empty-text {
    color: var(--text-muted);
  }

  .eyebrow {
    display: inline-flex;
    margin-bottom: 0.55rem;
    color: var(--primary-strong);
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.17em;
    text-transform: uppercase;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
    margin-top: 1.2rem;
  }

  .hero-side,
  .mix-list,
  .related-list {
    display: grid;
    gap: 0.8rem;
  }

  .hero-side {
    align-content: start;
  }

  .metric-card,
  .panel {
    padding: 1rem;
  }

  .metric-card span {
    display: block;
    margin-bottom: 0.35rem;
    color: var(--text-soft);
    font-size: 0.82rem;
  }

  .metric-card strong {
    display: block;
    font-size: 1.45rem;
    line-height: 1.1;
  }

  .metric-card.accent {
    background: linear-gradient(
      135deg,
      var(--surface-dark),
      color-mix(in srgb, var(--surface-dark) 80%, var(--primary) 20%)
    );
    color: var(--shell-text);
  }

  .metric-card.accent span,
  .metric-card.accent p {
    color: var(--shell-text-soft);
  }

  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.95fr);
    gap: 1rem;
  }

  .bottom-grid .panel-wide {
    min-width: 0;
  }

  .panel-wide {
    grid-column: span 1;
  }

  .panel-head {
    margin-bottom: 0.95rem;
  }

  .panel-head h2 {
    font-size: 1.25rem;
    line-height: 1.1;
  }

  .mix-row {
    display: grid;
    gap: 0.45rem;
  }

  .mix-copy {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }

  .mix-bar {
    height: 0.72rem;
    overflow: hidden;
    border-radius: 999px;
    background: var(--surface-muted);
  }

  .mix-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--warning), var(--secondary));
  }

  .related-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem;
    border-radius: 1.15rem;
    border: 1px solid var(--border);
    background: var(--surface-soft-muted);
    text-decoration: none;
    color: inherit;
    transition:
      transform 0.15s,
      border-color 0.15s,
      box-shadow 0.15s;
  }

  .related-card:hover {
    transform: translateY(-1px);
    border-color: var(--primary);
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .related-info {
    display: grid;
    gap: 0.1rem;
  }

  .related-count {
    display: inline-flex;
    align-items: center;
    margin-top: 0.25rem;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    background: var(--surface-muted);
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 600;
    width: fit-content;
  }

  .related-right {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    flex-shrink: 0;
  }

  .related-metric {
    text-align: right;
  }

  .related-arrow {
    color: var(--text-soft);
    font-size: 0.85rem;
    transition: transform 0.15s;
  }

  .related-card:hover .related-arrow {
    transform: translateX(3px);
    color: var(--primary);
  }

  .state-card {
    padding: 1.6rem;
  }

  .error-text {
    color: var(--danger);
  }

  @media (max-width: 980px) {
    .municipality-hero,
    .content-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .municipality-hero,
    .panel,
    .metric-card {
      padding: 1rem;
    }
  }
</style>
