<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import InputText from 'primevue/inputtext'
  import SelectButton from 'primevue/selectbutton'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import api from '../composables/useApi'
  import { useAuthStore } from '../stores/auth'
  import { useStatsStore } from '../stores/stats'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const auth = useAuthStore()
  const stats = useStatsStore()

  const loading = ref(true)
  const pageError = ref('')
  const dashboardSearch = ref('')
  const selectedPropertyType = ref('')
  const segmentLoading = ref(false)
  const segmentHome = ref<any | null>(null)

  const marketHome = computed<any>(
    () =>
      stats.marketHome || {
        headline: {},
        market_coverage: {},
        largest_markets: [],
        price_leaders: [],
        region_snapshot: [],
        latest_sales: [],
        property_type_mix: [],
      },
  )

  const spotlight = computed(() => marketHome.value.largest_markets?.[0] || null)

  const propertyTypeOptions = computed(() => {
    const values = (marketHome.value.property_type_mix || []).map((item: any) => item.property_type)
    return [
      { label: t('dashboard.filterAllTypes'), value: '' },
      ...values.map((value: string) => ({
        label: getPropertyTypeLabel(value, t),
        value,
      })),
    ]
  })

  const summaryCards = computed(() => [
    {
      label: t('dashboard.totalRecords'),
      value: formatNumber(marketHome.value.headline?.total_records),
      meta: t('dashboard.marketCoverageYears', {
        from: marketHome.value.headline?.earliest_year || '—',
        to: marketHome.value.headline?.latest_year || '—',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(marketHome.value.headline?.median_price),
      meta: t('dashboard.latestYearLabel', {
        year: marketHome.value.headline?.latest_year || '—',
      }),
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(marketHome.value.headline?.avg_price_per_m2),
      meta: spotlight.value?.municipality || t('common.noData'),
      tone: 'success',
    },
    {
      label: t('dashboard.marketCoverageLabel'),
      value: `${formatNumber(marketHome.value.market_coverage?.present)} / ${formatNumber(marketHome.value.market_coverage?.official_total)}`,
      meta: t('dashboard.marketMunicipalities', {
        count: formatNumber(marketHome.value.market_coverage?.present),
      }),
      tone: 'warning',
    },
  ])

  const segmentShare = computed(() => {
    const total = Number(marketHome.value.headline?.total_records || 0)
    const segmentTotal = Number(segmentHome.value?.headline?.total_records || 0)
    if (!total || !segmentTotal) return null
    return segmentTotal / total
  })

  const segmentCards = computed(() => {
    if (!segmentHome.value) return []

    return [
      {
        label: t('dashboard.totalRecords'),
        value: formatNumber(segmentHome.value.headline?.total_records),
        meta: getPropertyTypeLabel(selectedPropertyType.value, t),
      },
      {
        label: t('dashboard.segmentShare'),
        value:
          segmentShare.value == null
            ? '—'
            : formatPercent(segmentShare.value, { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
        meta: t('dashboard.segmentSpotlight'),
        tone: 'success',
      },
      {
        label: t('dashboard.medianPrice'),
        value: formatCurrency(segmentHome.value.headline?.median_price),
        meta: t('dashboard.marketTableTitle'),
      },
      {
        label: t('dashboard.pricePerM2'),
        value: formatCurrency(segmentHome.value.headline?.avg_price_per_m2),
        meta: t('dashboard.regionSnapshot'),
      },
    ]
  })

  const matchesSearch = (...values: unknown[]) => {
    const query = dashboardSearch.value.trim().toLowerCase()
    if (!query) return true
    return values.some((value) => String(value || '').toLowerCase().includes(query))
  }

  const largestMarketsRows = computed(() =>
    (marketHome.value.largest_markets || []).filter((item: any) =>
      matchesSearch(item.municipality, item.region),
    ),
  )

  const regionSnapshotRows = computed(() =>
    (marketHome.value.region_snapshot || []).filter((item: any) => matchesSearch(item.region)),
  )

  const latestSalesRows = computed(() =>
    (marketHome.value.latest_sales || []).filter((item: any) =>
      matchesSearch(item.municipality, getPropertyTypeLabel(item.property_type, t), item.year),
    ),
  )

  async function loadDashboard() {
    loading.value = true
    pageError.value = ''

    try {
      await stats.fetchMarketHome()
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
    } finally {
      loading.value = false
    }
  }

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

  onMounted(() => {
    void loadDashboard()
  })
</script>

<template>
  <div class="dashboard-page">
    <section class="hero-shell dashboard-hero">
      <PageHeader
        :eyebrow="t('dashboard.consumerKicker')"
        :title="t('dashboard.consumerTitle')"
        :description="t('dashboard.consumerBody')"
      >
        <template #actions>
          <RouterLink to="/napoved" class="hero-link">
            <Button icon="pi pi-bolt" :label="t('dashboard.quickPrediction')" />
          </RouterLink>
          <RouterLink to="/zemljevid" class="hero-link">
            <Button severity="secondary" outlined icon="pi pi-map" :label="t('dashboard.quickMap')" />
          </RouterLink>
          <RouterLink to="/analiza" class="hero-link">
            <Button
              severity="secondary"
              outlined
              icon="pi pi-chart-line"
              :label="t('nav.analysis')"
            />
          </RouterLink>
          <RouterLink v-if="auth.isAdmin" to="/admin" class="hero-link">
            <Button severity="contrast" outlined icon="pi pi-cog" :label="t('nav.admin')" />
          </RouterLink>
        </template>
      </PageHeader>

      <div class="hero-layout">
        <div class="hero-summary">
          <MetricCard
            v-for="card in summaryCards"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :meta="card.meta"
            :tone="card.tone || 'default'"
          />
        </div>

        <aside class="spotlight-card municipality-spotlight">
          <div class="spotlight-top">
            <p class="eyebrow subtle">{{ t('dashboard.municipalitySpotlight') }}</p>
            <Tag severity="contrast" :value="t('dashboard.marketTableTitle')" />
          </div>
          <template v-if="spotlight">
            <h2>{{ spotlight.municipality }}</h2>
            <p class="spotlight-copy">{{ spotlight.region || t('common.noData') }}</p>
            <div class="spotlight-metrics">
              <div>
                <span>{{ t('dashboard.transactions') }}</span>
                <strong>{{ formatNumber(spotlight.count) }}</strong>
              </div>
              <div>
                <span>{{ t('dashboard.pricePerM2') }}</span>
                <strong>{{ formatCurrency(spotlight.median_price_per_m2) }}</strong>
              </div>
            </div>
            <RouterLink :to="`/obcine/${spotlight.slug}`" class="hero-link">
              <Button severity="contrast" outlined icon="pi pi-arrow-right" :label="t('common.open')" />
            </RouterLink>
          </template>
          <EmptyState v-else :message="t('common.noData')" />
        </aside>
      </div>
    </section>

    <section class="filter-shell dashboard-filter-shell">
      <div>
        <p class="eyebrow subtle">{{ t('dashboard.filterByType') }}</p>
        <h2>{{ selectedPropertyType ? getPropertyTypeLabel(selectedPropertyType, t) : t('dashboard.filterAllTypes') }}</h2>
        <p class="page-subtitle">{{ t('dashboard.filterCompareHint') }}</p>
      </div>

      <div class="filter-actions">
        <InputText v-model="dashboardSearch" :placeholder="t('common.search')" class="dashboard-search" />
        <SelectButton
          v-model="selectedPropertyType"
          :options="propertyTypeOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
        />
      </div>
    </section>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />
    <p v-else-if="pageError" class="state-card error-text">{{ pageError }}</p>

    <template v-else>
      <section v-if="selectedPropertyType" class="panel segment-panel">
        <PageHeader
          compact
          :eyebrow="t('dashboard.segmentSpotlight')"
          :title="t('dashboard.segmentSpotlightTitle', { type: getPropertyTypeLabel(selectedPropertyType, t) })"
          :description="t('dashboard.segmentTopMarketsTitle')"
        />

        <LoadingSpinner v-if="segmentLoading" :label="t('common.loading')" />
        <template v-else-if="segmentHome">
          <div class="segment-summary">
            <MetricCard
              v-for="card in segmentCards"
              :key="card.label"
              :label="card.label"
              :value="card.value"
              :meta="card.meta"
              :tone="card.tone || 'default'"
            />
          </div>

          <div class="leader-list segment-leaders" v-if="segmentHome.largest_markets?.length">
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
              <Tag severity="success" :value="`${formatNumber(item.count)} ${t('dashboard.transactions')}`" />
            </RouterLink>
          </div>
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
            :value="largestMarketsRows"
            paginator
            :rows="8"
            size="small"
            striped-rows
            responsive-layout="scroll"
            table-style="min-width: 100%"
          >
            <Column field="municipality" :header="t('dashboard.municipality')" sortable>
              <template #body="{ data }">
                <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                  {{ data.municipality }}
                </RouterLink>
              </template>
            </Column>
            <Column field="region" :header="t('map.region')" sortable />
            <Column field="count" :header="t('dashboard.transactions')" sortable>
              <template #body="{ data }">{{ formatNumber(data.count) }}</template>
            </Column>
            <Column field="median_price" :header="t('dashboard.medianPrice')" sortable>
              <template #body="{ data }">{{ formatCurrency(data.median_price) }}</template>
            </Column>
            <Column field="median_price_per_m2" header="€/m²" sortable>
              <template #body="{ data }">{{ formatCurrency(data.median_price_per_m2) }}</template>
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
            :value="regionSnapshotRows"
            paginator
            :rows="8"
            size="small"
            striped-rows
            responsive-layout="scroll"
            table-style="min-width: 100%"
          >
            <Column field="region" :header="t('map.region')" sortable />
            <Column field="count" :header="t('dashboard.transactions')" sortable>
              <template #body="{ data }">{{ formatNumber(data.count) }}</template>
            </Column>
            <Column field="median_price_per_m2" :header="t('dashboard.pricePerM2')" sortable>
              <template #body="{ data }">{{ formatCurrency(data.median_price_per_m2) }}</template>
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

          <div v-if="marketHome.property_type_mix.length" class="mix-list">
            <article
              v-for="item in marketHome.property_type_mix.slice(0, 6)"
              :key="item.property_type"
              class="mix-row"
            >
              <div>
                <strong>{{ getPropertyTypeLabel(item.property_type, t) }}</strong>
                <p class="muted">{{ formatNumber(item.count) }} {{ t('dashboard.transactions') }}</p>
              </div>
              <Tag severity="secondary" :value="formatPercent(item.share, { minimumFractionDigits: 1, maximumFractionDigits: 1 })" />
            </article>
          </div>
          <EmptyState v-else :message="t('common.noData')" />
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.priceLeaders') }}</p>
              <h2>{{ t('dashboard.priceLeadersTitle') }}</h2>
            </div>
          </div>

          <div v-if="marketHome.price_leaders.length" class="leader-list">
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
              <Tag severity="success" :value="`${formatCurrency(item.median_price_per_m2)}/m²`" />
            </RouterLink>
          </div>
          <EmptyState v-else :message="t('common.noData')" />
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
          :value="latestSalesRows"
          paginator
          :rows="10"
          size="small"
          striped-rows
          responsive-layout="scroll"
          table-style="min-width: 100%"
        >
          <Column field="municipality" :header="t('dashboard.municipality')" sortable>
            <template #body="{ data }">
              <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                {{ data.municipality }}
              </RouterLink>
            </template>
          </Column>
          <Column field="property_type" :header="t('predict.propertyType')" sortable>
            <template #body="{ data }">{{ getPropertyTypeLabel(data.property_type, t) }}</template>
          </Column>
          <Column field="size_m2" :header="t('predict.size')" sortable>
            <template #body="{ data }">{{ formatNumber(data.size_m2, { maximumFractionDigits: 1 }) }} m²</template>
          </Column>
          <Column field="price_eur" :header="t('dashboard.medianPrice')" sortable>
            <template #body="{ data }">{{ formatCurrency(data.price_eur) }}</template>
          </Column>
          <Column field="price_per_m2" header="€/m²" sortable>
            <template #body="{ data }">{{ formatCurrency(data.price_per_m2) }}</template>
          </Column>
          <Column field="year" :header="t('map.year')" sortable>
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
    gap: 1.2rem;
  }

  .dashboard-hero,
  .dashboard-filter-shell,
  .panel,
  .state-card {
    border: 1px solid var(--border);
    border-radius: 1.6rem;
  }

  .dashboard-hero,
  .dashboard-filter-shell,
  .panel {
    background:
      linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft)),
      var(--surface-soft);
    box-shadow: var(--shadow-sm);
  }

  .dashboard-hero,
  .dashboard-filter-shell,
  .panel {
    padding: 1.25rem;
  }

  .hero-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
    gap: 1rem;
    align-items: stretch;
  }

  .hero-summary,
  .segment-summary {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .municipality-spotlight {
    display: grid;
    gap: 0.9rem;
    align-content: start;
    padding: 1.1rem;
    border-radius: 1.45rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--primary-overlay) 86%, transparent), var(--surface-soft)),
      var(--surface-soft);
  }

  .spotlight-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .municipality-spotlight h2,
  .panel h2,
  .dashboard-filter-shell h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.35rem, 2vw, 1.9rem);
    line-height: 1.02;
  }

  .spotlight-copy {
    margin: 0;
    color: var(--text-muted);
  }

  .spotlight-metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.8rem;
  }

  .spotlight-metrics div,
  .mix-row,
  .leader-row {
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: 1.15rem;
    padding: 0.9rem 1rem;
    background: color-mix(in srgb, var(--surface-strong) 88%, white 12%);
  }

  .spotlight-metrics span {
    display: block;
    color: var(--text-soft);
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 800;
  }

  .spotlight-metrics strong {
    display: block;
    margin-top: 0.38rem;
    font-size: 1.2rem;
    letter-spacing: -0.04em;
  }

  .dashboard-filter-shell {
    display: flex;
    align-items: end;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--warning-overlay) 78%, transparent), var(--surface-soft)),
      var(--surface-soft);
  }

  .filter-actions {
    display: grid;
    gap: 0.85rem;
    justify-items: end;
  }

  .dashboard-search {
    width: min(100%, 22rem);
  }

  .segment-panel,
  .leader-list,
  .mix-list {
    display: grid;
    gap: 0.9rem;
  }

  .segment-panel {
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--primary-overlay) 76%, transparent), var(--surface-soft)),
      var(--surface-soft);
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

  .mix-row,
  .leader-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    text-decoration: none;
    color: inherit;
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .leader-row:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .mix-row p,
  .leader-row p {
    margin: 0.2rem 0 0;
  }

  .segment-leaders {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-link,
  .table-link {
    text-decoration: none;
  }

  .dashboard-hero :deep(.page-header-actions) {
    gap: 0.65rem;
  }

  .filter-actions :deep(.p-selectbutton) {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.55rem;
  }

  .table-link {
    font-weight: 700;
    color: inherit;
  }

  .state-card {
    padding: 1.1rem 1.2rem;
  }

  @media (max-width: 1080px) {
    .hero-layout,
    .grid-two,
    .segment-leaders {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .hero-summary,
    .segment-summary,
    .spotlight-metrics {
      grid-template-columns: 1fr;
    }

    .dashboard-filter-shell,
    .filter-actions {
      align-items: stretch;
      justify-items: stretch;
    }

    .dashboard-hero :deep(.page-header-actions) {
      display: grid;
      grid-template-columns: 1fr;
      width: 100%;
    }

    .dashboard-hero :deep(.page-header-actions > *) {
      width: 100%;
    }

    .dashboard-hero :deep(.page-header-actions .p-button),
    .filter-actions :deep(.p-selectbutton) {
      width: 100%;
    }

    .filter-actions :deep(.p-selectbutton) {
      justify-content: stretch;
    }
  }
</style>