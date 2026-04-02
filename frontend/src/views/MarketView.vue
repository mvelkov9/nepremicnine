<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import InputNumber from 'primevue/inputnumber'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import TabPanel from 'primevue/tabpanel'
  import TabView from 'primevue/tabview'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import FeatureImportanceChart from '../components/charts/FeatureImportanceChart.vue'
  import PriceDistributionChart from '../components/charts/PriceDistributionChart.vue'
  import PropertyTypePieChart from '../components/charts/PropertyTypePieChart.vue'
  import TrendLineChart from '../components/charts/TrendLineChart.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import TableWorkbenchToolbar from '../components/workbench/TableWorkbenchToolbar.vue'
  import { toLocationQuery } from '../constants/workbench'
  import { useExport } from '../composables/useExport'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import api from '../composables/useApi'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const stats = useStatsStore()
  const workbench = useWorkbenchStore()
  const { exportToCSV } = useExport()
  const viewerQuery = useViewerQueryState({
    tab: 'overview',
    property_type: '',
    region: '',
    municipality: '',
    year: '',
    search: '',
  })

  const loading = ref(true)
  const pageError = ref('')
  const allMunicipalities = ref<Array<{ municipality: string; region?: string }>>([])
  const trendData = ref<any[]>([])
  const distributionData = ref<any>(null)
  const transactions = ref<any>({ items: [], total: 0, page: 1, page_size: 12 })
  const largestMarkets = ref<any>({ items: [], total: 0, page: 1, page_size: 8 })
  const priceLeaders = ref<any>({ items: [], total: 0, page: 1, page_size: 8 })
  const regions = ref<any>({ items: [], total: 0, page: 1, page_size: 6 })
  const distributionBins = ref(20)
  const transactionSort = ref('recent')
  const transactionOrder = ref('desc')
  const rankingSort = ref('count')
  const rankingOrder = ref('desc')

  const tabIndexMap: Record<string, number> = {
    overview: 0,
    transactions: 1,
    rankings: 2,
    distribution: 3,
  }
  const tabNames = ['overview', 'transactions', 'rankings', 'distribution']
  const activeTab = computed({
    get: () => tabIndexMap[viewerQuery.state.tab] ?? 0,
    set: (index: number) => viewerQuery.patchState({ tab: tabNames[index] || 'overview' }),
  })

  const marketHome = computed<any>(
    () =>
      stats.marketHome || {
        headline: {},
        property_type_mix: [],
        year_coverage: [],
      },
  )

  const propertyTypeOptions = computed(() => [
    { label: t('market.allPropertyTypes'), value: '' },
    ...(marketHome.value.property_type_mix || []).map((item: any) => ({
      label: getPropertyTypeLabel(item.property_type, t),
      value: item.property_type,
    })),
  ])

  const regionOptions = computed(() => {
    const regions = [...new Set(allMunicipalities.value.map((item) => item.region).filter(Boolean))]
    return [{ label: t('municipalities.allRegions'), value: '' }].concat(
      regions.sort().map((region) => ({ label: region as string, value: region as string })),
    )
  })

  const municipalityOptions = computed(() => {
    const items = viewerQuery.state.region
      ? allMunicipalities.value.filter((item) => item.region === viewerQuery.state.region)
      : allMunicipalities.value
    return [{ label: t('map.allMunicipalities'), value: '' }].concat(
      items.map((item) => ({ label: item.municipality, value: item.municipality })),
    )
  })

  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: '' },
    ...((marketHome.value.year_coverage || []) as any[]).map((item) => ({
      label: String(item.year),
      value: String(item.year),
    })),
  ])

  const summaryCards = computed(() => [
    {
      label: t('dashboard.totalRecords'),
      value: formatNumber(marketHome.value.headline?.total_records),
      meta: t('dashboard.marketCoverageYears', {
        from: marketHome.value.headline?.earliest_year || '-',
        to: marketHome.value.headline?.latest_year || '-',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(marketHome.value.headline?.median_price),
      meta: t('dashboard.latestYearLabel', { year: marketHome.value.headline?.latest_year || '-' }),
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(marketHome.value.headline?.avg_price_per_m2),
      meta: t('market.consumerKicker'),
      tone: 'success',
    },
  ])

  const transactionSortOptions = computed(() => [
    { label: t('market.sortRecent'), value: 'recent' },
    { label: t('market.metric_median_price'), value: 'price_eur' },
    { label: t('dashboard.pricePerM2'), value: 'price_per_m2' },
    { label: t('predict.size'), value: 'size_m2' },
    { label: t('map.year'), value: 'year' },
  ])

  const rankingSortOptions = computed(() => [
    { label: t('municipalities.sortTransactions'), value: 'count' },
    { label: t('municipalities.sortPrice'), value: 'median_price_per_m2' },
    { label: t('municipalities.sortName'), value: 'municipality' },
  ])

  const activeFilterLabels = computed(
    () =>
      [
        viewerQuery.state.property_type
          ? getPropertyTypeLabel(viewerQuery.state.property_type, t)
          : '',
        viewerQuery.state.region,
        viewerQuery.state.municipality,
        viewerQuery.state.year,
        viewerQuery.state.search,
      ].filter(Boolean) as string[],
  )
  const activeFilterCountValue = computed(() => viewerQuery.activeFilterCount.value)
  const activeFilterTagSeverity = computed(() =>
    activeFilterCountValue.value > 0 ? 'contrast' : 'secondary',
  )
  const activeFilterTagLabel = computed(() =>
    activeFilterCountValue.value > 0
      ? t('dashboard.activeFilterCount', { count: activeFilterCountValue.value })
      : t('dashboard.noActiveFilters'),
  )

  function filters() {
    return {
      property_type: viewerQuery.state.property_type || undefined,
      region: viewerQuery.state.region || undefined,
      municipality: viewerQuery.state.municipality || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
    }
  }

  function routeQuery(extra: Record<string, string> = {}) {
    return toLocationQuery({ ...filters(), ...extra })
  }

  async function loadReferences() {
    try {
      const { data } = await api.get('/api/regions/municipalities')
      allMunicipalities.value = data || []
    } catch {
      allMunicipalities.value = []
    }
  }

  async function loadTransactions() {
    const { data } = await api.get('/api/stats/transactions', {
      params: {
        ...filters(),
        page: transactions.value.page,
        page_size: transactions.value.page_size,
        sort: transactionSort.value,
        order: transactionOrder.value,
      },
    })
    transactions.value = data
  }

  async function loadRankings() {
    const [largestRes, leadersRes, regionRes] = await Promise.all([
      api.get('/api/stats/municipalities', {
        params: {
          ...filters(),
          page: largestMarkets.value.page,
          page_size: largestMarkets.value.page_size,
          sort: rankingSort.value,
          order: rankingOrder.value,
        },
      }),
      api.get('/api/stats/municipalities', {
        params: {
          ...filters(),
          page: priceLeaders.value.page,
          page_size: priceLeaders.value.page_size,
          sort: 'median_price_per_m2',
          order: 'desc',
        },
      }),
      api.get('/api/stats/regions-explorer', {
        params: { ...filters(), page: 1, page_size: 8, sort: 'count', order: 'desc' },
      }),
    ])
    largestMarkets.value = largestRes.data
    priceLeaders.value = leadersRes.data
    regions.value = regionRes.data
  }

  async function loadMarket() {
    loading.value = true
    pageError.value = ''
    try {
      await Promise.all([
        stats.fetchMarketHome(filters()),
        stats.fetchFeatureImportance(),
        api
          .get('/api/stats/trend', {
            params: {
              property_type: viewerQuery.state.property_type || undefined,
              region: viewerQuery.state.region || undefined,
              municipality: viewerQuery.state.municipality || undefined,
            },
          })
          .then(({ data }) => {
            trendData.value = data || []
          }),
        api
          .get('/api/stats/price-distribution', {
            params: {
              property_type: viewerQuery.state.property_type || undefined,
              region: viewerQuery.state.region || undefined,
              municipality: viewerQuery.state.municipality || undefined,
              year: viewerQuery.state.year || undefined,
              bins: distributionBins.value,
            },
          })
          .then(({ data }) => {
            distributionData.value = data
          }),
        loadTransactions(),
        loadRankings(),
      ])
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
    } finally {
      loading.value = false
    }
  }

  function clearFilters() {
    viewerQuery.patchState({
      property_type: '',
      region: '',
      municipality: '',
      year: '',
      search: '',
    })
  }

  async function addMunicipalityToWatchlist(item: any) {
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: item.slug,
      display_label: item.municipality,
      metadata: { link: `/obcine/${item.slug}`, region: item.region },
    })
  }

  function addMunicipalityToCompare(item: any) {
    workbench.addCompareItem({
      id: `municipality:${item.slug}`,
      entity_type: 'municipality',
      label: item.municipality,
      slug: item.slug,
      region: item.region,
      metadata: { source: 'market' },
    })
  }

  function exportTransactions() {
    exportToCSV(transactions.value.items || [], 'market-transactions.csv')
  }

  function onTransactionsPage(event: any) {
    transactions.value.page = event.page + 1
    transactions.value.page_size = event.rows
    void loadTransactions()
  }

  function onLargestPage(event: any) {
    largestMarkets.value.page = event.page + 1
    largestMarkets.value.page_size = event.rows
    void loadRankings()
  }

  function onLeadersPage(event: any) {
    priceLeaders.value.page = event.page + 1
    priceLeaders.value.page_size = event.rows
    void loadRankings()
  }

  watch(
    () => viewerQuery.state.region,
    (region) => {
      if (!region) return
      const valid = allMunicipalities.value.some(
        (item) => item.region === region && item.municipality === viewerQuery.state.municipality,
      )
      if (!valid) viewerQuery.patchState({ municipality: '' })
    },
  )

  watch(
    () => [
      viewerQuery.state.property_type,
      viewerQuery.state.region,
      viewerQuery.state.municipality,
      viewerQuery.state.year,
      viewerQuery.state.search,
      distributionBins.value,
      transactionSort.value,
      transactionOrder.value,
      rankingSort.value,
      rankingOrder.value,
    ],
    () => {
      transactions.value.page = 1
      largestMarkets.value.page = 1
      priceLeaders.value.page = 1
      void loadMarket()
    },
  )

  onMounted(async () => {
    await loadReferences()
    await loadMarket()
  })
</script>

<template>
  <div class="market-page">
    <section class="hero-shell">
      <PageHeader
        :eyebrow="t('market.consumerKicker')"
        :title="t('market.consumerTitle')"
        :description="t('market.consumerBody')"
      >
        <template #actions>
          <SavedWorkspaceMenu
            page="market"
            :state="{
              page: 'market',
              filters: filters(),
              tab: viewerQuery.state.tab,
              sort: transactionSort,
            }"
          />
          <RouterLink
            :to="{ path: '/zemljevid', query: routeQuery({ view: 'transactions' }) }"
            class="hero-link"
          >
            <Button severity="secondary" outlined icon="pi pi-map" :label="t('nav.map')" />
          </RouterLink>
          <RouterLink
            :to="{ path: '/obcine', query: routeQuery({ tab: 'table' }) }"
            class="hero-link"
          >
            <Button
              severity="secondary"
              outlined
              icon="pi pi-building"
              :label="t('nav.municipalities')"
            />
          </RouterLink>
        </template>
      </PageHeader>

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
    </section>

    <section class="panel filter-panel">
      <div class="filter-grid">
        <label class="field-inline">
          <span>{{ t('market.selectPropertyType') }}</span>
          <Select
            v-model="viewerQuery.state.property_type"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </label>
        <label class="field-inline">
          <span>{{ t('municipalities.filterByRegion') }}</span>
          <Select
            v-model="viewerQuery.state.region"
            :options="regionOptions"
            option-label="label"
            option-value="value"
          />
        </label>
        <label class="field-inline">
          <span>{{ t('dashboard.municipality') }}</span>
          <Select
            v-model="viewerQuery.state.municipality"
            :options="municipalityOptions"
            option-label="label"
            option-value="value"
          />
        </label>
        <label class="field-inline">
          <span>{{ t('map.year') }}</span>
          <Select
            v-model="viewerQuery.state.year"
            :options="yearOptions"
            option-label="label"
            option-value="value"
          />
        </label>
        <label class="field-inline search-field">
          <span>{{ t('common.search') }}</span>
          <InputText v-model="viewerQuery.state.search" :placeholder="t('common.search')" />
        </label>
        <div class="filter-actions">
          <Tag :value="activeFilterTagLabel" :severity="activeFilterTagSeverity" />
          <Button
            severity="secondary"
            outlined
            icon="pi pi-filter-slash"
            :label="t('map.clearFilter')"
            @click="clearFilters"
          />
        </div>
      </div>
    </section>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />
    <p v-else-if="pageError" class="state-card error-text">{{ pageError }}</p>

    <TabView v-else v-model:active-index="activeTab" class="market-tabs">
      <TabPanel value="0" :header="t('common.overview')">
        <section class="tab-content">
          <div class="grid-two">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('market.tabTrends') }}</p>
                  <h2>{{ t('market.trendSubtitle') }}</h2>
                </div>
              </div>
              <TrendLineChart v-if="trendData.length" :data="trendData" />
              <EmptyState v-else :message="t('common.noData')" />
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('dashboard.regionSnapshot') }}</p>
                  <h2>{{ t('dashboard.regionTableTitle') }}</h2>
                </div>
              </div>
              <div v-if="regions.items?.length" class="ranking-list">
                <RouterLink
                  v-for="region in regions.items.slice(0, 5)"
                  :key="region.region"
                  :to="{
                    path: '/regije',
                    query: routeQuery({ tab: 'drilldown', region: region.region }),
                  }"
                  class="ranking-row"
                >
                  <div>
                    <strong>{{ region.region }}</strong>
                    <p class="muted">
                      {{ formatNumber(region.count) }} {{ t('dashboard.transactions') }}
                    </p>
                  </div>
                  <Tag
                    severity="success"
                    :value="`${formatCurrency(region.median_price_per_m2)}/m²`"
                  />
                </RouterLink>
              </div>
              <EmptyState v-else :message="t('common.noData')" />
            </section>
          </div>

          <div class="grid-two">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('dashboard.largestMarkets') }}</p>
                  <h2>{{ t('market.largestMarketsTitle') }}</h2>
                </div>
              </div>
              <div v-if="largestMarkets.items?.length" class="ranking-list">
                <RouterLink
                  v-for="item in largestMarkets.items.slice(0, 5)"
                  :key="item.slug"
                  :to="`/obcine/${item.slug}`"
                  class="ranking-row"
                >
                  <div>
                    <strong>{{ item.municipality }}</strong>
                    <p class="muted">{{ item.region || '-' }}</p>
                  </div>
                  <Tag severity="contrast" :value="formatNumber(item.count)" />
                </RouterLink>
              </div>
              <EmptyState v-else :message="t('common.noData')" />
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('dashboard.priceLeaders') }}</p>
                  <h2>{{ t('market.priceLeadersTitle') }}</h2>
                </div>
              </div>
              <div v-if="priceLeaders.items?.length" class="ranking-list">
                <RouterLink
                  v-for="item in priceLeaders.items.slice(0, 5)"
                  :key="item.slug"
                  :to="`/obcine/${item.slug}`"
                  class="ranking-row"
                >
                  <div>
                    <strong>{{ item.municipality }}</strong>
                    <p class="muted">{{ item.region || '-' }}</p>
                  </div>
                  <Tag
                    severity="success"
                    :value="`${formatCurrency(item.median_price_per_m2)}/m²`"
                  />
                </RouterLink>
              </div>
              <EmptyState v-else :message="t('common.noData')" />
            </section>
          </div>
        </section>
      </TabPanel>

      <TabPanel value="1" :header="t('market.tabTransactions')">
        <section class="tab-content">
          <TableWorkbenchToolbar
            page="market"
            :state="{
              page: 'market',
              filters: filters(),
              tab: 'transactions',
              sort: transactionSort,
            }"
            :search-value="viewerQuery.state.search"
            :active-filters="activeFilterLabels"
            @update:search-value="viewerQuery.state.search = $event"
            @export="exportTransactions"
            @clear="clearFilters"
          >
            <template #actions>
              <Select
                v-model="transactionSort"
                :options="transactionSortOptions"
                option-label="label"
                option-value="value"
              />
              <Button
                severity="secondary"
                outlined
                :icon="
                  transactionOrder === 'desc' ? 'pi pi-sort-amount-down' : 'pi pi-sort-amount-up'
                "
                :label="
                  transactionOrder === 'desc'
                    ? t('market.sortDescending')
                    : t('market.sortAscending')
                "
                @click="transactionOrder = transactionOrder === 'desc' ? 'asc' : 'desc'"
              />
            </template>
          </TableWorkbenchToolbar>

          <div class="panel">
            <DataTable
              :value="transactions.items"
              lazy
              paginator
              :rows="transactions.page_size"
              :first="(transactions.page - 1) * transactions.page_size"
              :total-records="transactions.total"
              size="small"
              striped-rows
              responsive-layout="scroll"
              table-style="min-width: 100%"
              @page="onTransactionsPage"
            >
              <Column field="municipality" :header="t('dashboard.municipality')">
                <template #body="{ data }">
                  <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                    {{ data.municipality }}
                  </RouterLink>
                </template>
              </Column>
              <Column field="region" :header="t('map.region')" />
              <Column field="property_type" :header="t('predict.propertyType')">
                <template #body="{ data }">
                  {{ getPropertyTypeLabel(data.property_type, t) }}
                </template>
              </Column>
              <Column field="size_m2" :header="t('predict.size')">
                <template #body="{ data }">
                  {{ formatNumber(data.size_m2, { maximumFractionDigits: 1 }) }} m²
                </template>
              </Column>
              <Column field="price_eur" :header="t('dashboard.medianPrice')">
                <template #body="{ data }">{{ formatCurrency(data.price_eur) }}</template>
              </Column>
              <Column field="price_per_m2" header="€/m²">
                <template #body="{ data }">{{ formatCurrency(data.price_per_m2) }}</template>
              </Column>
              <Column field="year" :header="t('map.year')">
                <template #body="{ data }">{{ data.year || '-' }}</template>
              </Column>
              <Column :header="t('common.actions')">
                <template #body="{ data }">
                  <div class="row-actions">
                    <Button
                      size="small"
                      severity="secondary"
                      text
                      icon="pi pi-bookmark"
                      @click="addMunicipalityToWatchlist(data)"
                    />
                    <Button
                      size="small"
                      severity="secondary"
                      text
                      icon="pi pi-plus-circle"
                      @click="addMunicipalityToCompare(data)"
                    />
                    <RouterLink
                      :to="{
                        path: '/zemljevid',
                        query: routeQuery({
                          municipality: data.municipality,
                          view: 'transactions',
                        }),
                      }"
                      class="table-link"
                    >
                      <Button size="small" severity="secondary" text icon="pi pi-map" />
                    </RouterLink>
                  </div>
                </template>
              </Column>
            </DataTable>
          </div>
        </section>
      </TabPanel>

      <TabPanel value="2" :header="t('market.tabRankings')">
        <section class="tab-content">
          <div class="toolbar">
            <Select
              v-model="rankingSort"
              :options="rankingSortOptions"
              option-label="label"
              option-value="value"
            />
            <Button
              severity="secondary"
              outlined
              :icon="rankingOrder === 'desc' ? 'pi pi-sort-amount-down' : 'pi pi-sort-amount-up'"
              :label="
                rankingOrder === 'desc' ? t('market.sortDescending') : t('market.sortAscending')
              "
              @click="rankingOrder = rankingOrder === 'desc' ? 'asc' : 'desc'"
            />
          </div>

          <div class="grid-two">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('dashboard.largestMarkets') }}</p>
                  <h2>{{ t('market.largestMarketsTitle') }}</h2>
                </div>
              </div>
              <DataTable
                :value="largestMarkets.items"
                lazy
                paginator
                :rows="largestMarkets.page_size"
                :first="(largestMarkets.page - 1) * largestMarkets.page_size"
                :total-records="largestMarkets.total"
                size="small"
                striped-rows
                responsive-layout="scroll"
                table-style="min-width: 100%"
                @page="onLargestPage"
              >
                <Column field="municipality" :header="t('dashboard.municipality')">
                  <template #body="{ data }">
                    <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                      {{ data.municipality }}
                    </RouterLink>
                  </template>
                </Column>
                <Column field="region" :header="t('map.region')" />
                <Column field="count" :header="t('dashboard.transactions')">
                  <template #body="{ data }">{{ formatNumber(data.count) }}</template>
                </Column>
                <Column field="median_price_per_m2" header="€/m²">
                  <template #body="{ data }">
                    {{ formatCurrency(data.median_price_per_m2) }}
                  </template>
                </Column>
                <Column :header="t('common.actions')">
                  <template #body="{ data }">
                    <div class="row-actions">
                      <Button
                        size="small"
                        severity="secondary"
                        text
                        icon="pi pi-bookmark"
                        @click="addMunicipalityToWatchlist(data)"
                      />
                      <Button
                        size="small"
                        severity="secondary"
                        text
                        icon="pi pi-plus-circle"
                        @click="addMunicipalityToCompare(data)"
                      />
                    </div>
                  </template>
                </Column>
              </DataTable>
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('dashboard.priceLeaders') }}</p>
                  <h2>{{ t('market.priceLeadersTitle') }}</h2>
                </div>
              </div>
              <DataTable
                :value="priceLeaders.items"
                lazy
                paginator
                :rows="priceLeaders.page_size"
                :first="(priceLeaders.page - 1) * priceLeaders.page_size"
                :total-records="priceLeaders.total"
                size="small"
                striped-rows
                responsive-layout="scroll"
                table-style="min-width: 100%"
                @page="onLeadersPage"
              >
                <Column field="municipality" :header="t('dashboard.municipality')">
                  <template #body="{ data }">
                    <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                      {{ data.municipality }}
                    </RouterLink>
                  </template>
                </Column>
                <Column field="region" :header="t('map.region')" />
                <Column field="median_price_per_m2" header="€/m²">
                  <template #body="{ data }">
                    {{ formatCurrency(data.median_price_per_m2) }}
                  </template>
                </Column>
                <Column field="count" :header="t('dashboard.transactions')">
                  <template #body="{ data }">{{ formatNumber(data.count) }}</template>
                </Column>
                <Column :header="t('common.actions')">
                  <template #body="{ data }">
                    <div class="row-actions">
                      <Button
                        size="small"
                        severity="secondary"
                        text
                        icon="pi pi-bookmark"
                        @click="addMunicipalityToWatchlist(data)"
                      />
                      <Button
                        size="small"
                        severity="secondary"
                        text
                        icon="pi pi-plus-circle"
                        @click="addMunicipalityToCompare(data)"
                      />
                    </div>
                  </template>
                </Column>
              </DataTable>
            </section>
          </div>

          <section class="panel">
            <div class="panel-head">
              <div>
                <p class="eyebrow subtle">{{ t('market.featureImportance') }}</p>
                <h2>{{ t('market.featureImportanceDesc') }}</h2>
              </div>
            </div>
            <FeatureImportanceChart
              v-if="stats.featureImportance?.length"
              :features="stats.featureImportance"
              :limit="15"
            />
            <EmptyState v-else :message="t('common.noData')" />
          </section>
        </section>
      </TabPanel>

      <TabPanel value="3" :header="t('market.tabDistribution')">
        <section class="tab-content">
          <div class="toolbar">
            <InputNumber v-model="distributionBins" :min="5" :max="50" :step="5" />
          </div>
          <div class="grid-two">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('market.distributionTitle') }}</p>
                  <h2>{{ t('market.distributionSubtitle') }}</h2>
                </div>
              </div>
              <PriceDistributionChart
                v-if="distributionData?.bins?.length"
                :bins="distributionData.bins"
                :counts="distributionData.counts"
                :bin-labels="distributionData.bin_labels"
              />
              <EmptyState v-else :message="t('common.noData')" />
            </section>

            <section class="panel">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('market.propertyMixTitle') }}</p>
                  <h2>{{ t('market.propertyMixSubtitle') }}</h2>
                </div>
              </div>
              <PropertyTypePieChart
                v-if="marketHome.property_type_mix?.length"
                :items="marketHome.property_type_mix"
              />
              <EmptyState v-else :message="t('common.noData')" />
            </section>
          </div>
        </section>
      </TabPanel>
    </TabView>
  </div>
</template>

<style scoped>
  .market-page,
  .tab-content,
  .hero-summary,
  .filter-grid,
  .grid-two {
    display: grid;
    gap: 1rem;
  }
  .market-page {
    gap: 1.2rem;
  }
  .hero-shell,
  .panel,
  .state-card {
    border: 1px solid var(--border);
    border-radius: 1.6rem;
  }
  .hero-shell,
  .panel {
    background:
      linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft)), var(--surface-soft);
    box-shadow: var(--shadow-sm);
    padding: 1.25rem;
  }
  .hero-shell {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 76%, transparent),
        var(--surface-soft)
      ),
      var(--surface-soft);
  }
  .hero-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 1rem;
  }
  .filter-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    align-items: end;
  }
  .grid-two {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .field-inline {
    display: grid;
    gap: 0.35rem;
  }
  .field-inline span {
    font-size: 0.82rem;
    color: var(--text-muted);
    font-weight: 700;
  }
  .search-field {
    grid-column: span 2;
  }
  .filter-actions,
  .toolbar,
  .panel-head,
  .row-actions {
    display: flex;
    gap: 0.8rem;
    flex-wrap: wrap;
  }
  .filter-actions {
    align-items: end;
    justify-content: flex-end;
  }
  .panel-head {
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 0.85rem;
  }
  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.12rem, 1.8vw, 1.48rem);
    line-height: 1.08;
  }
  .eyebrow.subtle {
    color: var(--text-soft);
  }
  .ranking-list {
    display: grid;
    gap: 0.75rem;
  }
  .ranking-row,
  .hero-link,
  .table-link {
    text-decoration: none;
    color: inherit;
  }
  .ranking-row {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.8rem;
    align-items: center;
    padding: 0.9rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: 1.15rem;
    background: color-mix(in srgb, var(--surface-strong) 88%, var(--overlay-strong) 12%);
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }
  .ranking-row:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }
  .state-card {
    padding: 1.1rem 1.2rem;
  }
  @media (max-width: 1080px) {
    .filter-grid,
    .grid-two {
      grid-template-columns: 1fr;
    }
    .search-field {
      grid-column: span 1;
    }
  }
  @media (max-width: 720px) {
    .hero-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
