<script setup>
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import DataTable from 'primevue/datatable'
  import Column from 'primevue/column'
  import SelectButton from 'primevue/selectbutton'
  import Tag from 'primevue/tag'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import api from '../composables/useApi'
  import { useStatsStore } from '../stores/stats'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const stats = useStatsStore()

  const loading = ref(true)
  const pageError = ref('')
  const selectedPropertyType = ref('')
  const segmentLoading = ref(false)
  const segmentHome = ref(null)
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

    try {
      const marketHomeData = await stats.fetchMarketHome()
      availablePropertyTypes.value = (marketHomeData?.property_type_mix || []).map(
        (item) => item.property_type,
      )
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
    } finally {
      loading.value = false
    }
  }

  onMounted(loadDashboard)

  watch(selectedPropertyType, async (nextType) => {
    if (!nextType) {
      segmentHome.value = null
      return
    }

    segmentLoading.value = true
    try {
      const { data } = await api.get('/api/stats/market-home', {
        params: { property_type: nextType },
      })
      segmentHome.value = data
    } catch {
      segmentHome.value = null
    } finally {
      segmentLoading.value = false
    }
  })

  const marketHome = computed(
    () =>
      stats.marketHome || {
        headline: {},
        largest_markets: [],
        price_leaders: [],
        region_snapshot: [],
        latest_sales: [],
        property_type_mix: [],
      },
  )

  const summaryCards = computed(() => [
    {
      label: t('dashboard.totalRecords'),
      value: fmt(marketHome.value.headline?.total_records),
    },
    {
      label: t('dashboard.medianPrice'),
      value: fmtCurrency(marketHome.value.headline?.median_price),
    },
    {
      label: t('dashboard.pricePerM2'),
      value: fmtCurrency(marketHome.value.headline?.avg_price_per_m2),
    },
    {
      label: t('dashboard.marketMunicipalitiesLabel'),
      value: fmt(marketHome.value.headline?.municipalities_count),
    },
  ])

  const spotlight = computed(() => marketHome.value.largest_markets?.[0] || null)

  const propertyTypeOptions = computed(() =>
    [
      {
        label: t('dashboard.filterAllTypes'),
        value: '',
      },
      ...availablePropertyTypes.value.map((value) => ({
        label: propertyTypeLabel(value),
        value,
      })),
    ],
  )

  const segmentShare = computed(() => {
    const total = marketHome.value.headline?.total_records || 0
    const segmentTotal = segmentHome.value?.headline?.total_records || 0
    if (!total || !segmentTotal) return null
    return segmentTotal / total
  })

  const segmentCards = computed(() => {
    if (!segmentHome.value) return []

    return [
      {
        label: t('dashboard.totalRecords'),
        value: fmt(segmentHome.value.headline?.total_records),
      },
      {
        label: t('dashboard.segmentShare'),
        value: segmentShare.value != null ? fmtPercent(segmentShare.value) : '—',
      },
      {
        label: t('dashboard.medianPrice'),
        value: fmtCurrency(segmentHome.value.headline?.median_price),
      },
      {
        label: t('dashboard.pricePerM2'),
        value: fmtCurrency(segmentHome.value.headline?.avg_price_per_m2),
      },
    ]
  })

  function mixSeverity(share) {
    if (share >= 0.35) return 'success'
    if (share >= 0.15) return 'warn'
    return 'secondary'
  }
</script>

<template>
  <div class="dashboard-page">
    <section class="hero-shell">
      <div class="hero-copy">
        <p class="eyebrow">{{ t('dashboard.consumerKicker') }}</p>
        <h1>{{ t('dashboard.consumerTitle') }}</h1>
        <p class="muted">{{ t('dashboard.consumerBody') }}</p>

        <div class="hero-actions">
          <RouterLink to="/napoved" class="hero-link">
            <Button icon="pi pi-bolt" :label="t('dashboard.quickPrediction')" />
          </RouterLink>
          <RouterLink to="/zemljevid" class="hero-link">
            <Button severity="secondary" outlined icon="pi pi-map" :label="t('dashboard.quickMap')" />
          </RouterLink>
          <RouterLink v-if="spotlight?.slug" :to="`/obcine/${spotlight.slug}`" class="hero-link">
            <Button
              severity="contrast"
              outlined
              icon="pi pi-building"
              :label="t('dashboard.municipalitySpotlight')"
            />
          </RouterLink>
        </div>
      </div>

      <div class="hero-summary">
        <article v-for="card in summaryCards" :key="card.label" class="summary-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
        </article>
      </div>
    </section>

    <section class="filter-shell">
      <div>
        <p class="eyebrow">{{ t('dashboard.filterByType') }}</p>
        <h2>{{ selectedPropertyType ? propertyTypeLabel(selectedPropertyType) : t('dashboard.filterAllTypes') }}</h2>
        <p class="muted">{{ t('dashboard.filterCompareHint') }}</p>
      </div>

      <SelectButton
        v-model="selectedPropertyType"
        :options="propertyTypeOptions"
        optionLabel="label"
        optionValue="value"
        :allowEmpty="false"
      />
    </section>

    <div v-if="loading" class="state-card">
      <LoadingSpinner :label="t('common.loading')" />
    </div>
    <p v-else-if="pageError" class="state-card error-text">{{ pageError }}</p>

    <template v-else>
      <section v-if="selectedPropertyType" class="panel segment-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow subtle">{{ t('dashboard.segmentSpotlight') }}</p>
            <h2>{{ t('dashboard.segmentSpotlightTitle', { type: propertyTypeLabel(selectedPropertyType) }) }}</h2>
            <p class="muted">{{ t('dashboard.segmentTopMarketsTitle') }}</p>
          </div>
        </div>

        <div v-if="segmentLoading" class="state-card compact">
          <LoadingSpinner :label="t('common.loading')" />
        </div>

        <template v-else-if="segmentHome">
          <div class="hero-summary segment-summary">
            <article v-for="card in segmentCards" :key="card.label" class="summary-card">
              <span>{{ card.label }}</span>
              <strong>{{ card.value }}</strong>
            </article>
          </div>

          <div class="leader-list" v-if="segmentHome.largest_markets?.length">
            <RouterLink
              v-for="item in segmentHome.largest_markets.slice(0, 4)"
              :key="`${selectedPropertyType}-${item.slug}`"
              :to="`/obcine/${item.slug}`"
              class="leader-row"
            >
              <div>
                <strong>{{ item.municipality }}</strong>
                <p class="muted">{{ item.region || '—' }}</p>
              </div>
              <Tag severity="success" :value="`${fmt(item.count)} ${t('dashboard.transactions')}`" />
            </RouterLink>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </template>
      </section>

      <section class="grid-two">
        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.largestMarkets') }}</p>
              <h2>{{ t('dashboard.marketTableTitle') }}</h2>
            </div>
          </div>

          <DataTable
            :value="marketHome.largest_markets.slice(0, 8)"
            size="small"
            stripedRows
            tableStyle="min-width: 100%"
          >
            <Column :header="t('dashboard.municipality')">
              <template #body="{ data }">
                <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                  {{ data.municipality }}
                </RouterLink>
              </template>
            </Column>
            <Column field="count" :header="t('dashboard.transactions')">
              <template #body="{ data }">{{ fmt(data.count) }}</template>
            </Column>
            <Column :header="t('dashboard.medianPrice')">
              <template #body="{ data }">{{ fmtCurrency(data.median_price) }}</template>
            </Column>
            <Column header="€/m²">
              <template #body="{ data }">{{ fmtCurrency(data.median_price_per_m2) }}</template>
            </Column>
          </DataTable>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.regionSnapshot') }}</p>
              <h2>{{ t('dashboard.regionTableTitle') }}</h2>
            </div>
          </div>

          <DataTable
            :value="marketHome.region_snapshot.slice(0, 8)"
            size="small"
            stripedRows
            tableStyle="min-width: 100%"
          >
            <Column field="region" :header="t('map.region')" />
            <Column field="count" :header="t('dashboard.transactions')">
              <template #body="{ data }">{{ fmt(data.count) }}</template>
            </Column>
            <Column :header="t('dashboard.pricePerM2')">
              <template #body="{ data }">{{ fmtCurrency(data.median_price_per_m2) }}</template>
            </Column>
          </DataTable>
        </article>
      </section>

      <section class="grid-two">
        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.propertyMix') }}</p>
              <h2>{{ t('dashboard.propertyMixTitle') }}</h2>
            </div>
          </div>

          <div class="mix-list" v-if="marketHome.property_type_mix.length">
            <div v-for="item in marketHome.property_type_mix.slice(0, 6)" :key="item.property_type" class="mix-row">
              <div>
                <strong>{{ propertyTypeLabel(item.property_type) }}</strong>
                <p class="muted">{{ fmt(item.count) }} {{ t('dashboard.transactions') }}</p>
              </div>
              <Tag :severity="mixSeverity(item.share)" :value="fmtPercent(item.share)" />
            </div>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.priceLeaders') }}</p>
              <h2>{{ t('dashboard.priceLeadersTitle') }}</h2>
            </div>
          </div>

          <div class="leader-list" v-if="marketHome.price_leaders.length">
            <RouterLink
              v-for="item in marketHome.price_leaders.slice(0, 6)"
              :key="item.slug"
              :to="`/obcine/${item.slug}`"
              class="leader-row"
            >
              <div>
                <strong>{{ item.municipality }}</strong>
                <p class="muted">{{ item.region || '—' }}</p>
              </div>
              <Tag severity="success" :value="`${fmtCurrency(item.median_price_per_m2)}/m²`" />
            </RouterLink>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow subtle">{{ t('dashboard.recentSales') }}</p>
            <h2>{{ t('dashboard.latestTransactions') }}</h2>
          </div>
        </div>

        <DataTable
          :value="marketHome.latest_sales"
          size="small"
          stripedRows
          tableStyle="min-width: 100%"
        >
          <Column :header="t('dashboard.municipality')">
            <template #body="{ data }">
              <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                {{ data.municipality }}
              </RouterLink>
            </template>
          </Column>
          <Column :header="t('predict.propertyType')">
            <template #body="{ data }">{{ propertyTypeLabel(data.property_type) }}</template>
          </Column>
          <Column :header="t('predict.size')">
            <template #body="{ data }">{{ fmt(data.size_m2, 1) }} m²</template>
          </Column>
          <Column :header="t('dashboard.medianPrice')">
            <template #body="{ data }">{{ fmtCurrency(data.price_eur) }}</template>
          </Column>
          <Column header="€/m²">
            <template #body="{ data }">{{ fmtCurrency(data.price_per_m2) }}</template>
          </Column>
          <Column :header="t('map.year')">
            <template #body="{ data }">{{ data.year || '—' }}</template>
          </Column>
        </DataTable>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .dashboard-page {
    display: grid;
    gap: 1rem;
  }

  .hero-shell,
  .filter-shell,
  .panel,
  .state-card {
    border: 1px solid var(--border);
    border-radius: 1.5rem;
    background: var(--surface);
    box-shadow: var(--shadow-sm);
  }

  .hero-shell,
  .filter-shell,
  .panel {
    padding: 1.2rem;
  }

  .hero-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.8fr);
    gap: 1rem;
    background:
      linear-gradient(135deg, var(--surface-strong), var(--surface-soft)),
      radial-gradient(circle at top left, rgb(16 185 129 / 14%), transparent 34%);
  }

  .hero-copy h1,
  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
    line-height: 1.05;
  }

  .hero-copy h1 {
    font-size: clamp(2rem, 4vw, 3rem);
    max-width: 11ch;
  }

  .hero-copy p {
    max-width: 56ch;
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .hero-link {
    text-decoration: none;
  }

  .hero-summary {
    display: grid;
    gap: 0.75rem;
  }

  .summary-card {
    padding: 0.95rem 1rem;
    border-radius: 1.1rem;
    background: var(--surface-elevated);
    display: grid;
    gap: 0.25rem;
  }

  .summary-card span {
    color: var(--text-muted);
    font-size: 0.84rem;
  }

  .summary-card strong {
    font-size: 1.35rem;
  }

  .filter-shell {
    display: grid;
    gap: 0.8rem;
  }

  .filter-shell h2 {
    margin: 0;
  }

  .filter-shell :deep(.p-selectbutton) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .filter-shell :deep(.p-togglebutton) {
    border-radius: 999px;
  }

  .segment-panel {
    display: grid;
    gap: 1rem;
  }

  .segment-summary {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .compact {
    padding: 0.75rem;
  }

  .grid-two {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.85rem;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  .mix-list,
  .leader-list {
    display: grid;
    gap: 0.7rem;
  }

  .mix-row,
  .leader-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    background: var(--surface-muted);
  }

  .leader-row {
    color: inherit;
    text-decoration: none;
  }

  .table-link {
    color: inherit;
    text-decoration: none;
    font-weight: 700;
  }

  .table-link:hover,
  .leader-row:hover {
    text-decoration: underline;
  }

  .state-card {
    padding: 1.2rem;
  }

  @media (max-width: 900px) {
    .hero-shell,
    .grid-two,
    .segment-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
