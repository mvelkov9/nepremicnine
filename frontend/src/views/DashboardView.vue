<script setup>
  import { computed, onMounted, ref } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import api from '../composables/useApi'
  import AppIcon from '../components/AppIcon.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { useStatsStore } from '../stores/stats'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const stats = useStatsStore()

  const loading = ref(true)
  const modelInfo = ref(null)
  const modelError = ref('')
  const pageError = ref('')
  const selectedPropertyType = ref('')
  const availablePropertyTypes = ref([])

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value, decimals = 0) {
    return formatCurrency(value, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  function fmtPercent(value) {
    return formatPercent(value)
  }

  function propertyTypeLabel(value) {
    return getPropertyTypeLabel(value, t)
  }

  async function loadDashboard() {
    loading.value = true
    pageError.value = ''
    modelError.value = ''

    try {
      const params = selectedPropertyType.value ? { property_type: selectedPropertyType.value } : {}
      const requests = [
        stats.fetchMarketHome(params),
        dataStore.fetchTrainingDataset().catch(() => null),
        api
          .get('/api/model/info')
          .then((response) => {
            modelInfo.value = response.data
          })
          .catch((error) => {
            modelInfo.value = null
            modelError.value = getApiErrorMessage(error, t)
          }),
      ]

      const [marketHomeData] = await Promise.all(requests)
      if (!selectedPropertyType.value || !availablePropertyTypes.value.length) {
        availablePropertyTypes.value = (marketHomeData?.property_type_mix || []).map(
          (item) => item.property_type,
        )
      }
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
    } finally {
      loading.value = false
    }
  }

  onMounted(loadDashboard)

  const marketHome = computed(
    () =>
      stats.marketHome || {
        headline: {},
        active_property_type: null,
        largest_markets: [],
        price_leaders: [],
        region_snapshot: [],
        latest_sales: [],
        year_coverage: [],
        property_type_mix: [],
      },
  )

  const propertyTypeOptions = computed(() =>
    availablePropertyTypes.value.map((value) => ({
      value,
      label: propertyTypeLabel(value),
    })),
  )

  const activeFilterLabel = computed(() =>
    selectedPropertyType.value
      ? propertyTypeLabel(selectedPropertyType.value)
      : t('dashboard.filterAllTypes'),
  )

  const filterSummary = computed(() =>
    selectedPropertyType.value
      ? t('dashboard.filterActive', { type: activeFilterLabel.value })
      : t('dashboard.filterAllHint'),
  )

  const coverageEndYear = computed(() => {
    const years = marketHome.value.year_coverage || []
    return years.length ? years[years.length - 1].year : '—'
  })

  const heroCards = computed(() => [
    {
      label: t('dashboard.totalRecords'),
      value: fmt(marketHome.value.headline?.total_records),
      detail: t('dashboard.marketCoverageYears', {
        from: marketHome.value.year_coverage?.[0]?.year || '—',
        to: coverageEndYear.value,
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: fmtCurrency(marketHome.value.headline?.median_price),
      detail: t('dashboard.latestYearLabel', {
        year: marketHome.value.headline?.latest_year || '—',
      }),
    },
    {
      label: t('dashboard.pricePerM2'),
      value: fmtCurrency(marketHome.value.headline?.avg_price_per_m2),
      detail: t('dashboard.marketMunicipalities', {
        count: fmt(marketHome.value.headline?.municipalities_count),
      }),
    },
    {
      label: t('dashboard.modelR2'),
      value: modelInfo.value?.global_metrics?.r2?.toFixed(3) || '—',
      detail: modelInfo.value?.rows
        ? t('dashboard.modelRowsDetail', { count: fmt(modelInfo.value.rows) })
        : t('dashboard.modelMissingDetail'),
    },
  ])

  const quickActions = computed(() => {
    const items = [
      {
        to: '/napoved',
        icon: 'prediction',
        title: t('dashboard.quickPrediction'),
        description: t('dashboard.quickPredictionDesc'),
      },
      {
        to: '/zemljevid',
        icon: 'map',
        title: t('dashboard.quickMap'),
        description: t('dashboard.quickMapDesc'),
      },
    ]

    const spotlight = marketHome.value.largest_markets?.[0]
    if (spotlight?.slug) {
      items.push({
        to: `/obcine/${spotlight.slug}`,
        icon: 'market',
        title: t('dashboard.municipalitySpotlight'),
        description: spotlight.municipality,
      })
    }

    if (auth.isAdmin) {
      items.push(
        {
          to: '/priprava',
          icon: 'prepare',
          title: t('dashboard.quickPrepare'),
          description: t('dashboard.quickPrepareDesc'),
        },
        {
          to: '/model',
          icon: 'model',
          title: t('dashboard.quickTrain'),
          description: t('dashboard.quickTrainDesc'),
        },
      )
    }

    return items
  })

  const statusCards = computed(() => [
    {
      label: t('dashboard.preparedDataset'),
      title: dataStore.trainingDataset?.exists
        ? t('dashboard.preparedReady')
        : t('dashboard.preparedMissing'),
      detail: dataStore.trainingDataset?.exists
        ? `${fmt(dataStore.trainingDataset.rows)} ${t('data.rows')}`
        : t('dashboard.preparedMissingDetail'),
    },
    {
      label: t('dashboard.modelStatus'),
      title: modelInfo.value ? t('dashboard.modelReady') : t('dashboard.modelMissing'),
      detail: modelInfo.value?.trained_at
        ? formatDateTime(modelInfo.value.trained_at)
        : modelError.value || t('dashboard.modelMissingDetail'),
    },
  ])

  const workflowCopy = computed(() =>
    auth.isAdmin
      ? {
          title: t('dashboard.workflowAdmin'),
          detail: t('dashboard.workflowAdminDetail'),
        }
      : {
          title: t('dashboard.workflowViewer'),
          detail: t('dashboard.workflowViewerDetail'),
        },
  )

  function shareStyle(share) {
    return { width: `${Math.max(8, Math.round((share || 0) * 100))}%` }
  }

  function applyPropertyTypeFilter(nextType) {
    if (selectedPropertyType.value === nextType) return
    selectedPropertyType.value = nextType
    loadDashboard()
  }
</script>

<template>
  <div class="dashboard-page">
    <section class="hero-shell">
      <div class="hero-copy">
        <span class="hero-kicker">{{ t('dashboard.heroKicker') }}</span>
        <h1>{{ t('dashboard.marketCommandTitle') }}</h1>
        <p>{{ t('dashboard.marketCommandBody') }}</p>

        <div class="hero-actions">
          <RouterLink
            v-for="action in quickActions"
            :key="action.to"
            :to="action.to"
            class="hero-action"
          >
            <span class="hero-action-icon">
              <AppIcon :name="action.icon" :size="18" />
            </span>
            <span>
              <strong>{{ action.title }}</strong>
              <small>{{ action.description }}</small>
            </span>
          </RouterLink>
        </div>
      </div>

      <div class="hero-side">
        <article v-for="card in statusCards" :key="card.label" class="pulse-card">
          <span class="pulse-label">{{ card.label }}</span>
          <strong>{{ card.title }}</strong>
          <p>{{ card.detail }}</p>
        </article>

        <article class="pulse-card accent">
          <span class="pulse-label">{{ t('dashboard.workflowTitle') }}</span>
          <strong>{{ workflowCopy.title }}</strong>
          <p>{{ workflowCopy.detail }}</p>
        </article>
      </div>
    </section>

    <div v-if="loading" class="loading-wrap">
      <LoadingSpinner :label="t('common.loading')" />
    </div>

    <p v-else-if="pageError" class="page-error">{{ pageError }}</p>

    <template v-else>
      <section class="lens-shell">
        <div>
          <span class="panel-kicker">{{ t('dashboard.filterByType') }}</span>
          <h2>{{ activeFilterLabel }}</h2>
          <p>{{ filterSummary }}</p>
        </div>

        <div class="lens-actions">
          <button
            type="button"
            class="lens-chip"
            :class="{ active: !selectedPropertyType }"
            @click="applyPropertyTypeFilter('')"
          >
            {{ t('dashboard.filterAllTypes') }}
          </button>
          <button
            v-for="option in propertyTypeOptions"
            :key="option.value"
            type="button"
            class="lens-chip"
            :class="{ active: selectedPropertyType === option.value }"
            @click="applyPropertyTypeFilter(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </section>

      <section class="metric-band">
        <article v-for="card in heroCards" :key="card.label" class="metric-card">
          <span class="metric-label">{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.detail }}</p>
        </article>
      </section>

      <section class="grid-shell">
        <article class="panel panel-wide">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">{{ t('dashboard.dataLens') }}</span>
              <h2>{{ t('dashboard.largestMarkets') }}</h2>
            </div>
            <span class="panel-note">{{ t('dashboard.transactions') }}</span>
          </div>

          <div v-if="marketHome.largest_markets?.length" class="table-shell">
            <table>
              <thead>
                <tr>
                  <th>{{ t('dashboard.municipality') }}</th>
                  <th>{{ t('dashboard.transactions') }}</th>
                  <th>{{ t('dashboard.medianPrice') }}</th>
                  <th>€/m²</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in marketHome.largest_markets.slice(0, 8)" :key="item.slug">
                  <td>
                    <RouterLink :to="`/obcine/${item.slug}`" class="table-link">
                      {{ item.municipality }}
                    </RouterLink>
                    <small>{{ item.region || '—' }}</small>
                  </td>
                  <td>{{ fmt(item.count) }}</td>
                  <td>{{ fmtCurrency(item.median_price) }}</td>
                  <td>{{ fmtCurrency(item.median_price_per_m2) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="panel-empty">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">{{ t('dashboard.pricePerM2') }}</span>
              <h2>{{ t('dashboard.priceLeaders') }}</h2>
            </div>
          </div>

          <div v-if="marketHome.price_leaders?.length" class="stack-list">
            <RouterLink
              v-for="item in marketHome.price_leaders.slice(0, 6)"
              :key="item.slug"
              :to="`/obcine/${item.slug}`"
              class="rank-card"
            >
              <div>
                <strong>{{ item.municipality }}</strong>
                <small>{{ item.region || '—' }}</small>
              </div>
              <div class="rank-metric">
                <strong>{{ fmtCurrency(item.median_price_per_m2) }}</strong>
                <small>{{ fmt(item.count) }} {{ t('dashboard.transactions') }}</small>
              </div>
            </RouterLink>
          </div>
          <p v-else class="panel-empty">{{ t('common.noData') }}</p>
        </article>
      </section>

      <section class="grid-shell">
        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">{{ t('dashboard.regionPrices') }}</span>
              <h2>{{ t('dashboard.regionSnapshot') }}</h2>
            </div>
          </div>

          <div v-if="marketHome.region_snapshot?.length" class="stack-list compact">
            <div
              v-for="region in marketHome.region_snapshot.slice(0, 6)"
              :key="region.region"
              class="rank-card muted-card"
            >
              <div>
                <strong>{{ region.region }}</strong>
                <small>{{ fmt(region.count) }} {{ t('dashboard.transactions') }}</small>
              </div>
              <div class="rank-metric">
                <strong>{{ fmtCurrency(region.median_price_per_m2) }}</strong>
                <small>{{ fmtCurrency(region.median_price) }}</small>
              </div>
            </div>
          </div>
          <p v-else class="panel-empty">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">{{ t('dashboard.priceTrend') }}</span>
              <h2>{{ t('dashboard.yearCoverage') }}</h2>
            </div>
          </div>

          <div v-if="marketHome.year_coverage?.length" class="timeline-grid">
            <div v-for="item in marketHome.year_coverage" :key="item.year" class="timeline-card">
              <strong>{{ item.year }}</strong>
              <span>{{ fmt(item.count) }} {{ t('dashboard.transactions') }}</span>
              <small>{{ fmtCurrency(item.median_price) }}</small>
              <small>{{ fmtCurrency(item.median_price_per_m2) }}/m²</small>
            </div>
          </div>
          <p v-else class="panel-empty">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="panel-kicker">{{ t('dashboard.propertyTypes') }}</span>
              <h2>{{ t('dashboard.propertyMix') }}</h2>
            </div>
          </div>

          <div v-if="marketHome.property_type_mix?.length" class="mix-list">
            <div
              v-for="item in marketHome.property_type_mix.slice(0, 6)"
              :key="item.property_type"
              class="mix-row"
            >
              <div class="mix-copy">
                <strong>{{ propertyTypeLabel(item.property_type) }}</strong>
                <small>{{ fmtPercent(item.share) }}</small>
              </div>
              <div class="mix-bar">
                <span :style="shareStyle(item.share)"></span>
              </div>
            </div>
          </div>
          <p v-else class="panel-empty">{{ t('common.noData') }}</p>
        </article>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <span class="panel-kicker">{{ t('dashboard.recentSales') }}</span>
            <h2>{{ t('dashboard.latestTransactions') }}</h2>
          </div>
        </div>

        <div v-if="marketHome.latest_sales?.length" class="sales-grid">
          <article
            v-for="sale in marketHome.latest_sales"
            :key="`${sale.slug}-${sale.price_eur}-${sale.year}`"
            class="sale-card"
          >
            <div class="sale-head">
              <RouterLink :to="`/obcine/${sale.slug}`" class="table-link">
                {{ sale.municipality }}
              </RouterLink>
              <span>{{ sale.year || '—' }}</span>
            </div>
            <strong>{{ fmtCurrency(sale.price_eur) }}</strong>
            <p>
              {{ propertyTypeLabel(sale.property_type) || '—' }} · {{ fmt(sale.size_m2, 1) }} m²
            </p>
            <small>{{ fmtCurrency(sale.price_per_m2) }}/m²</small>
          </article>
        </div>
        <p v-else class="panel-empty">{{ t('common.noData') }}</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .dashboard-page {
    display: grid;
    gap: 1.4rem;
  }

  .lens-shell {
    display: grid;
    gap: 0.9rem;
    padding: 1rem 1.15rem;
    border: 1px solid var(--border);
    border-radius: 1.5rem;
    background:
      linear-gradient(135deg, rgb(255 255 255 / 84%), rgb(255 255 255 / 72%)),
      radial-gradient(circle at top right, rgb(37 99 235 / 10%), transparent 30%);
    box-shadow: var(--shadow-sm);
  }

  .lens-shell h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  .lens-shell p {
    margin: 0.45rem 0 0;
    color: var(--text-muted);
  }

  .lens-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .lens-chip {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: rgb(255 255 255 / 78%);
    color: var(--text);
    padding: 0.55rem 0.9rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    transition:
      transform 140ms ease,
      border-color 140ms ease,
      box-shadow 140ms ease,
      background-color 140ms ease;
  }

  .lens-chip:hover {
    transform: translateY(-1px);
    border-color: rgb(37 99 235 / 24%);
    box-shadow: var(--shadow-sm);
  }

  .lens-chip.active {
    border-color: rgb(37 99 235 / 34%);
    background: linear-gradient(135deg, rgb(37 99 235 / 14%), rgb(245 158 11 / 14%));
    color: var(--primary-strong);
  }

  .hero-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.9fr);
    gap: 1.2rem;
    padding: 1.6rem;
    border-radius: 2rem;
    border: 1px solid var(--border);
    background:
      linear-gradient(135deg, rgb(255 255 255 / 82%), rgb(255 255 255 / 68%)),
      radial-gradient(circle at top left, rgb(37 99 235 / 14%), transparent 34%),
      radial-gradient(circle at right, rgb(245 158 11 / 14%), transparent 28%);
    box-shadow: var(--shadow-sm);
  }

  .hero-copy h1,
  .panel-head h2 {
    margin: 0;
    font-family: var(--font-display);
    line-height: 1.05;
  }

  .hero-copy h1 {
    max-width: 11ch;
    font-size: clamp(2rem, 4vw, 3.45rem);
  }

  .hero-copy p {
    max-width: 58ch;
    margin: 0.85rem 0 0;
    color: var(--text-muted);
    font-size: 1rem;
  }

  .hero-kicker,
  .panel-kicker,
  .pulse-label {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    margin-bottom: 0.65rem;
    color: var(--primary-strong);
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }

  .hero-actions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.9rem;
    margin-top: 1.35rem;
  }

  .hero-action {
    display: flex;
    gap: 0.8rem;
    align-items: flex-start;
    padding: 0.95rem 1rem;
    border-radius: 1.2rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 72%);
    text-decoration: none;
    transition:
      transform 140ms ease,
      border-color 140ms ease,
      box-shadow 140ms ease;
  }

  .hero-action:hover {
    transform: translateY(-2px);
    border-color: rgb(37 99 235 / 28%);
    box-shadow: var(--shadow-sm);
  }

  .hero-action span {
    display: grid;
  }

  .hero-action strong {
    font-size: 0.96rem;
  }

  .hero-action small,
  .pulse-card p,
  .metric-card p,
  .panel-empty,
  .timeline-card span,
  .timeline-card small,
  .rank-card small,
  .sale-card p,
  .sale-card small,
  td small {
    color: var(--text-muted);
  }

  .hero-action-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 0.95rem;
    background: linear-gradient(145deg, rgb(37 99 235 / 16%), rgb(245 158 11 / 15%));
    color: var(--primary-strong);
  }

  .hero-side,
  .stack-list,
  .mix-list {
    display: grid;
    gap: 0.8rem;
  }

  .pulse-card,
  .panel,
  .metric-card {
    border-radius: 1.45rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 78%);
    box-shadow: var(--shadow-sm);
  }

  .pulse-card {
    padding: 1rem 1.05rem;
  }

  .pulse-card strong,
  .metric-card strong,
  .rank-metric strong,
  .sale-card strong {
    display: block;
    font-size: 1.05rem;
  }

  .pulse-card.accent {
    background: linear-gradient(135deg, rgb(15 23 42 / 94%), rgb(28 39 63 / 94%));
    color: #eff6ff;
  }

  .pulse-card.accent p,
  .pulse-card.accent .pulse-label {
    color: rgb(255 255 255 / 72%);
  }

  .metric-band,
  .grid-shell {
    display: grid;
    gap: 1rem;
  }

  .metric-band {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .metric-card {
    padding: 1rem 1.05rem;
  }

  .metric-label {
    display: block;
    margin-bottom: 0.45rem;
    color: var(--text-muted);
    font-size: 0.86rem;
  }

  .metric-card strong {
    font-size: 1.55rem;
    line-height: 1.1;
  }

  .grid-shell {
    grid-template-columns: minmax(0, 1.6fr) repeat(2, minmax(0, 1fr));
  }

  .panel {
    padding: 1.15rem;
  }

  .panel-wide {
    grid-column: span 2;
  }

  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .panel-note {
    margin: 0;
    color: var(--text-soft);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .table-shell {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    padding: 0.8rem 0.4rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }

  th {
    color: var(--text-soft);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .table-link {
    color: var(--text);
    font-weight: 700;
    text-decoration: none;
  }

  .table-link:hover {
    color: var(--primary-strong);
  }

  td small {
    display: block;
    margin-top: 0.2rem;
  }

  .rank-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1.1rem;
    border: 1px solid var(--border);
    text-decoration: none;
    background: rgb(255 255 255 / 72%);
  }

  .rank-card.muted-card {
    text-decoration: none;
  }

  .rank-metric {
    text-align: right;
  }

  .timeline-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.8rem;
  }

  .timeline-card,
  .sale-card {
    display: grid;
    gap: 0.25rem;
    padding: 0.9rem;
    border-radius: 1.15rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 76%);
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
    height: 0.7rem;
    overflow: hidden;
    border-radius: 999px;
    background: rgb(15 23 42 / 8%);
  }

  .mix-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--primary), #7dd3fc);
  }

  .sales-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 0.85rem;
  }

  .sale-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.7rem;
    font-size: 0.84rem;
  }

  .loading-wrap,
  .page-error {
    padding: 2rem;
    border-radius: 1.4rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 70%);
  }

  .page-error {
    color: var(--danger);
  }

  @media (max-width: 1100px) {
    .lens-shell,
    .hero-shell,
    .grid-shell {
      grid-template-columns: 1fr;
    }

    .panel-wide {
      grid-column: auto;
    }

    .metric-band {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .lens-shell,
    .hero-shell,
    .panel,
    .metric-card {
      padding: 1rem;
    }

    .metric-band {
      grid-template-columns: 1fr;
    }

    .hero-actions {
      grid-template-columns: 1fr;
    }
  }
</style>
