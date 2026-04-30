<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { useDebounceFn } from '@vueuse/core'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import InputNumber from 'primevue/inputnumber'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tabs from 'primevue/tabs'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import FilterBar from '../components/FilterBar.vue'
  import FilterField from '../components/FilterField.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import FeatureImportanceChart from '../components/charts/FeatureImportanceChart.vue'
  import PriceDistributionChart from '../components/charts/PriceDistributionChart.vue'
  import PropertyTypePieChart from '../components/charts/PropertyTypePieChart.vue'
  import TrendLineChart from '../components/charts/TrendLineChart.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import TableWorkbenchToolbar from '../components/workbench/TableWorkbenchToolbar.vue'
  import MarketSectionCard from '../features/market/MarketSectionCard.vue'
  import MarketStateFrame from '../features/market/MarketStateFrame.vue'
  import { toLocationQuery } from '../constants/workbench'
  import { useExport } from '../composables/useExport'
  import { useFilterOptions } from '../composables/useFilterOptions'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import api from '../composables/useApi'
  import { useReferenceDataStore } from '../stores/referenceData'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import type {
    MunicipalityExplorerItem,
    PriceDistribution,
    PropertyTypeMix,
    RegionExplorerItem,
    TableViewState,
    TransactionRecord,
    TrendPoint,
  } from '../types/api'
  import { getApiErrorMessage } from '../utils/apiError'
  import { useFormat } from '../composables/useFormat'
  import { formatCurrency, formatNumber } from '../utils/format'

  interface MarketHomeHeadline {
    total_records?: number
    earliest_year?: string | number
    latest_year?: string | number
    median_price?: number
    avg_price_per_m2?: number
  }

  interface MarketAnalysisData {
    headline?: MarketHomeHeadline
    market_coverage?: { present?: number; official_total?: number }
    property_type_mix?: PropertyTypeMix[]
    year_coverage?: unknown[]
  }

  interface MarketTablePage<T> {
    items: T[]
    total: number
    page: number
    page_size: number
  }

  interface FeatureImportanceItem {
    feature: string
    label: string
    importance: number
  }

  interface MarketPageEvent {
    page: number
    rows: number
  }

  const MARKET_TRANSACTION_SORTS = ['recent', 'price_eur', 'price_per_m2', 'size_m2', 'year']
  const MARKET_RANKING_SORTS = ['count', 'median_price_per_m2', 'municipality']

  const { t } = useI18n()
  const { formatType } = useFormat()
  const stats = useStatsStore()
  const referenceData = useReferenceDataStore()
  const workbench = useWorkbenchStore()
  const { exportToCSV } = useExport()
  const viewerQuery = useViewerQueryState({
    tab: 'overview',
    property_type: '',
    region: '',
    municipality: '',
    year: '',
    search: '',
    transaction_sort: 'recent',
    transaction_order: 'desc',
    ranking_sort: 'count',
    ranking_order: 'desc',
    distribution_bins: '20',
  })

  const initialized = ref(false)
  const bootstrapLoading = ref(true)
  const bootstrapError = ref('')
  const marketLoading = ref(false)
  const marketError = ref('')
  const trendLoading = ref(false)
  const trendError = ref('')
  const distributionLoading = ref(false)
  const distributionError = ref('')
  const transactionsLoading = ref(false)
  const transactionsError = ref('')
  const regionsLoading = ref(false)
  const regionsError = ref('')
  const largestMarketsLoading = ref(false)
  const largestMarketsError = ref('')
  const priceLeadersLoading = ref(false)
  const priceLeadersError = ref('')
  const featureImportanceLoading = ref(false)
  const featureImportanceError = ref('')

  let marketRequestVersion = 0
  let trendRequestVersion = 0
  let distributionRequestVersion = 0
  let transactionsRequestVersion = 0
  let regionsRequestVersion = 0
  let largestMarketsRequestVersion = 0
  let priceLeadersRequestVersion = 0
  let featureImportanceRequestVersion = 0

  const transactions = ref<MarketTablePage<TransactionRecord>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 12,
  })
  const largestMarkets = ref<MarketTablePage<MunicipalityExplorerItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 8,
  })
  const priceLeaders = ref<MarketTablePage<MunicipalityExplorerItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 8,
  })
  const regions = ref<MarketTablePage<RegionExplorerItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 6,
  })
  const marketHomeData = ref<MarketAnalysisData>(emptyMarketHome())
  const trendRows = ref<TrendPoint[]>([])
  const distributionSnapshot = ref<PriceDistribution | null>(null)
  const featureImportanceRows = ref<FeatureImportanceItem[]>([])
  const marketSectionCache = new Map<string, unknown>()
  const MARKET_SECTION_CACHE_LIMIT = 64

  function emptyMarketHome(): MarketAnalysisData {
    return {
      headline: {},
      property_type_mix: [],
      year_coverage: [],
    }
  }

  function emptyMarketTablePage<T>(page: number, pageSize: number): MarketTablePage<T> {
    return {
      items: [],
      total: 0,
      page,
      page_size: pageSize,
    }
  }

  function rememberMarketSection(cacheKey: string, payload: unknown) {
    marketSectionCache.delete(cacheKey)
    marketSectionCache.set(cacheKey, payload)

    while (marketSectionCache.size > MARKET_SECTION_CACHE_LIMIT) {
      const oldestKey = marketSectionCache.keys().next().value
      if (!oldestKey) break
      marketSectionCache.delete(oldestKey)
    }
  }

  function marketSectionCacheKey(
    section: string,
    extra: Record<string, string | number | undefined> = {},
  ) {
    return JSON.stringify({
      section,
      property_type: viewerQuery.state.property_type || '',
      region: viewerQuery.state.region || '',
      municipality: viewerQuery.state.municipality || '',
      year: viewerQuery.state.year || '',
      search: viewerQuery.state.search || '',
      ...extra,
    })
  }

  const marketHome = computed<MarketAnalysisData>(() =>
    marketError.value ? emptyMarketHome() : marketHomeData.value,
  )
  const trendData = computed<TrendPoint[]>(() => (trendError.value ? [] : trendRows.value))
  const distributionData = computed<PriceDistribution | null>(() =>
    distributionError.value ? null : distributionSnapshot.value,
  )
  const marketFeatureImportance = computed<FeatureImportanceItem[]>(() =>
    featureImportanceError.value ? [] : featureImportanceRows.value,
  )

  const selectedRegionRef = computed(() => viewerQuery.state.region || '')
  const { propertyTypeOptions, regionOptions, municipalityOptions, yearOptions } = useFilterOptions(
    {
      region: selectedRegionRef,
    },
  )

  const activeTab = computed({
    get: () =>
      ['overview', 'transactions', 'rankings', 'distribution'].includes(viewerQuery.state.tab)
        ? viewerQuery.state.tab
        : 'overview',
    set: (tab: string) => viewerQuery.patchState({ tab: tab || 'overview' }),
  })

  const transactionSort = computed({
    get: () =>
      MARKET_TRANSACTION_SORTS.includes(viewerQuery.state.transaction_sort)
        ? viewerQuery.state.transaction_sort
        : 'recent',
    set: (value: string) => {
      void viewerQuery.patchState({ transaction_sort: value })
    },
  })

  const transactionOrder = computed({
    get: () => (viewerQuery.state.transaction_order === 'asc' ? 'asc' : 'desc'),
    set: (value: string) => {
      void viewerQuery.patchState({ transaction_order: value })
    },
  })

  const rankingSort = computed({
    get: () =>
      MARKET_RANKING_SORTS.includes(viewerQuery.state.ranking_sort)
        ? viewerQuery.state.ranking_sort
        : 'count',
    set: (value: string) => {
      void viewerQuery.patchState({ ranking_sort: value })
    },
  })

  const rankingOrder = computed({
    get: () => (viewerQuery.state.ranking_order === 'asc' ? 'asc' : 'desc'),
    set: (value: string) => {
      void viewerQuery.patchState({ ranking_order: value })
    },
  })

  const distributionBins = computed({
    get: () => {
      const parsed = Number(viewerQuery.state.distribution_bins)
      if (!Number.isFinite(parsed)) return 20
      return Math.min(50, Math.max(5, Math.round(parsed / 5) * 5))
    },
    set: (value: number | null) => {
      const numeric = Number(value ?? 20)
      const normalized = Number.isFinite(numeric)
        ? Math.min(50, Math.max(5, Math.round(numeric / 5) * 5))
        : 20
      void viewerQuery.patchState({ distribution_bins: String(normalized) })
    },
  })

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
        viewerQuery.state.property_type ? formatType(viewerQuery.state.property_type) : '',
        viewerQuery.state.region,
        viewerQuery.state.municipality,
        viewerQuery.state.year,
        viewerQuery.state.search,
      ].filter(Boolean) as string[],
  )
  const activeFilterCountValue = computed(
    () =>
      [
        viewerQuery.state.property_type,
        viewerQuery.state.region,
        viewerQuery.state.municipality,
        viewerQuery.state.year,
        viewerQuery.state.search,
      ].filter(Boolean).length,
  )
  const activeFilterTagSeverity = computed(() =>
    activeFilterCountValue.value > 0 ? 'contrast' : 'secondary',
  )
  const activeFilterTagLabel = computed(() =>
    activeFilterCountValue.value > 0
      ? t('dashboard.activeFilterCount', { count: activeFilterCountValue.value })
      : t('dashboard.noActiveFilters'),
  )
  const filtersRefreshing = computed(() =>
    [
      marketLoading.value,
      trendLoading.value,
      distributionLoading.value,
      transactionsLoading.value,
      regionsLoading.value,
      largestMarketsLoading.value,
      priceLeadersLoading.value,
      featureImportanceLoading.value,
    ].some(Boolean),
  )

  const workspaceState = computed<TableViewState>(() => ({
    page: 'market',
    filters: {
      property_type: viewerQuery.state.property_type || '',
      region: viewerQuery.state.region || '',
      municipality: viewerQuery.state.municipality || '',
      year: viewerQuery.state.year || '',
      search: viewerQuery.state.search || '',
      transaction_sort: transactionSort.value,
      transaction_order: transactionOrder.value,
      ranking_sort: rankingSort.value,
      ranking_order: rankingOrder.value,
      distribution_bins: String(distributionBins.value),
    },
    tab: viewerQuery.state.tab,
    sort: transactionSort.value,
  }))

  function filters() {
    return {
      property_type: viewerQuery.state.property_type || undefined,
      region: viewerQuery.state.region || undefined,
      municipality: viewerQuery.state.municipality || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
    }
  }

  function marketHomeFilters() {
    return {
      property_type: viewerQuery.state.property_type || undefined,
      region: viewerQuery.state.region || undefined,
      municipality: viewerQuery.state.municipality || undefined,
      year: viewerQuery.state.year || undefined,
    }
  }

  function trendFilters() {
    return {
      property_type: viewerQuery.state.property_type || undefined,
      region: viewerQuery.state.region || undefined,
      municipality: viewerQuery.state.municipality || undefined,
    }
  }

  function queryState() {
    return {
      ...filters(),
      tab: viewerQuery.state.tab || 'overview',
      transaction_sort: transactionSort.value,
      transaction_order: transactionOrder.value,
      ranking_sort: rankingSort.value,
      ranking_order: rankingOrder.value,
      distribution_bins: String(distributionBins.value),
    }
  }

  function routeQuery(extra: Record<string, string> = {}) {
    return toLocationQuery({ ...queryState(), ...extra })
  }

  function normalizeQueryState() {
    const patch: Record<string, string> = {}

    if (
      viewerQuery.state.property_type &&
      !referenceData.propertyTypes.includes(viewerQuery.state.property_type)
    ) {
      patch.property_type = ''
    }

    if (viewerQuery.state.region && !referenceData.regions.includes(viewerQuery.state.region)) {
      patch.region = ''
    }

    if (
      viewerQuery.state.municipality &&
      !referenceData.municipalities.some(
        (item) =>
          item.municipality === viewerQuery.state.municipality &&
          (!viewerQuery.state.region || item.region === viewerQuery.state.region),
      )
    ) {
      patch.municipality = ''
    }

    if (viewerQuery.state.year && !referenceData.years.includes(viewerQuery.state.year)) {
      patch.year = ''
    }

    if (!MARKET_TRANSACTION_SORTS.includes(viewerQuery.state.transaction_sort)) {
      patch.transaction_sort = 'recent'
    }

    if (!['asc', 'desc'].includes(viewerQuery.state.transaction_order)) {
      patch.transaction_order = 'desc'
    }

    if (!MARKET_RANKING_SORTS.includes(viewerQuery.state.ranking_sort)) {
      patch.ranking_sort = 'count'
    }

    if (!['asc', 'desc'].includes(viewerQuery.state.ranking_order)) {
      patch.ranking_order = 'desc'
    }

    const bins = Number(viewerQuery.state.distribution_bins)
    const normalizedBins = Number.isFinite(bins)
      ? Math.min(50, Math.max(5, Math.round(bins / 5) * 5))
      : 20
    if (String(normalizedBins) !== viewerQuery.state.distribution_bins) {
      patch.distribution_bins = String(normalizedBins)
    }

    if (Object.keys(patch).length) {
      void viewerQuery.patchState(patch)
      return true
    }

    return false
  }

  function resetTablePages() {
    transactions.value.page = 1
    largestMarkets.value.page = 1
    priceLeaders.value.page = 1
    regions.value.page = 1
  }

  async function loadMarketHome() {
    const requestVersion = ++marketRequestVersion
    const cacheKey = marketSectionCacheKey('marketHome', {
      search: undefined,
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      marketError.value = ''
      marketHomeData.value = (cached as MarketAnalysisData | null) || emptyMarketHome()
      marketLoading.value = false
      return
    }

    marketLoading.value = true
    marketError.value = ''
    try {
      const payload = await stats.fetchMarketHome(marketHomeFilters())
      if (requestVersion !== marketRequestVersion) return
      marketHomeData.value = (payload as MarketAnalysisData | null) || emptyMarketHome()
      rememberMarketSection(cacheKey, marketHomeData.value)
    } catch (error) {
      if (requestVersion !== marketRequestVersion) return
      marketError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === marketRequestVersion) {
        marketLoading.value = false
      }
    }
  }

  async function loadTrend() {
    const requestVersion = ++trendRequestVersion
    const cacheKey = marketSectionCacheKey('trend', {
      year: undefined,
      search: undefined,
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      trendError.value = ''
      trendRows.value = Array.isArray(cached) ? (cached as TrendPoint[]) : []
      trendLoading.value = false
      return
    }

    trendLoading.value = true
    trendError.value = ''
    try {
      const payload = await stats.fetchTrend(trendFilters())
      if (requestVersion !== trendRequestVersion) return
      trendRows.value = Array.isArray(payload) ? (payload as TrendPoint[]) : []
      rememberMarketSection(cacheKey, trendRows.value)
    } catch (error) {
      if (requestVersion !== trendRequestVersion) return
      trendError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === trendRequestVersion) {
        trendLoading.value = false
      }
    }
  }

  async function loadDistribution() {
    const requestVersion = ++distributionRequestVersion
    const cacheKey = marketSectionCacheKey('distribution', {
      bins: distributionBins.value,
      search: undefined,
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      distributionError.value = ''
      distributionSnapshot.value = (cached as PriceDistribution | null) || null
      distributionLoading.value = false
      return
    }

    distributionLoading.value = true
    distributionError.value = ''
    try {
      const payload = await stats.fetchPriceDistribution({
        property_type: viewerQuery.state.property_type || undefined,
        region: viewerQuery.state.region || undefined,
        municipality: viewerQuery.state.municipality || undefined,
        year: viewerQuery.state.year || undefined,
        bins: distributionBins.value,
      })
      if (requestVersion !== distributionRequestVersion) return
      distributionSnapshot.value = (payload as PriceDistribution | null) || null
      rememberMarketSection(cacheKey, distributionSnapshot.value)
    } catch (error) {
      if (requestVersion !== distributionRequestVersion) return
      distributionError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === distributionRequestVersion) {
        distributionLoading.value = false
      }
    }
  }

  async function loadFeatureImportance() {
    const requestVersion = ++featureImportanceRequestVersion
    const cacheKey = marketSectionCacheKey('featureImportance', {
      property_type: undefined,
      region: undefined,
      municipality: undefined,
      year: undefined,
      search: undefined,
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      featureImportanceError.value = ''
      featureImportanceRows.value = Array.isArray(cached) ? (cached as FeatureImportanceItem[]) : []
      featureImportanceLoading.value = false
      return
    }

    featureImportanceLoading.value = true
    featureImportanceError.value = ''
    try {
      const payload = await stats.fetchFeatureImportance()
      if (requestVersion !== featureImportanceRequestVersion) return
      featureImportanceRows.value = Array.isArray(payload)
        ? (payload as FeatureImportanceItem[])
        : []
      rememberMarketSection(cacheKey, featureImportanceRows.value)
    } catch (error) {
      if (requestVersion !== featureImportanceRequestVersion) return
      featureImportanceError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === featureImportanceRequestVersion) {
        featureImportanceLoading.value = false
      }
    }
  }

  async function loadTransactions() {
    const requestVersion = ++transactionsRequestVersion
    const cacheKey = marketSectionCacheKey('transactions', {
      page: transactions.value.page,
      page_size: transactions.value.page_size,
      sort: transactionSort.value,
      order: transactionOrder.value,
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      transactionsError.value = ''
      transactions.value =
        (cached as MarketTablePage<TransactionRecord> | null) ||
        emptyMarketTablePage<TransactionRecord>(
          transactions.value.page,
          transactions.value.page_size,
        )
      transactionsLoading.value = false
      return
    }

    transactionsLoading.value = true
    transactionsError.value = ''
    try {
      const { data } = await api.get('/api/stats/transactions', {
        params: {
          ...filters(),
          page: transactions.value.page,
          page_size: transactions.value.page_size,
          sort: transactionSort.value,
          order: transactionOrder.value,
        },
      })
      if (requestVersion !== transactionsRequestVersion) return
      transactions.value = data || transactions.value
      rememberMarketSection(cacheKey, transactions.value)
    } catch (error) {
      if (requestVersion !== transactionsRequestVersion) return
      transactions.value = emptyMarketTablePage<TransactionRecord>(
        transactions.value.page,
        transactions.value.page_size,
      )
      transactionsError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === transactionsRequestVersion) {
        transactionsLoading.value = false
      }
    }
  }

  async function loadRegions() {
    const requestVersion = ++regionsRequestVersion
    const cacheKey = marketSectionCacheKey('regions', {
      page: regions.value.page,
      page_size: regions.value.page_size,
      sort: 'count',
      order: 'desc',
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      regionsError.value = ''
      regions.value =
        (cached as MarketTablePage<RegionExplorerItem> | null) ||
        emptyMarketTablePage<RegionExplorerItem>(regions.value.page, regions.value.page_size)
      regionsLoading.value = false
      return
    }

    regionsLoading.value = true
    regionsError.value = ''
    try {
      const { data } = await api.get('/api/stats/regions-explorer', {
        params: {
          ...filters(),
          page: regions.value.page,
          page_size: regions.value.page_size,
          sort: 'count',
          order: 'desc',
        },
      })
      if (requestVersion !== regionsRequestVersion) return
      regions.value = data || regions.value
      rememberMarketSection(cacheKey, regions.value)
    } catch (error) {
      if (requestVersion !== regionsRequestVersion) return
      regions.value = emptyMarketTablePage<RegionExplorerItem>(
        regions.value.page,
        regions.value.page_size,
      )
      regionsError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === regionsRequestVersion) {
        regionsLoading.value = false
      }
    }
  }

  async function loadLargestMarkets() {
    const requestVersion = ++largestMarketsRequestVersion
    const cacheKey = marketSectionCacheKey('largestMarkets', {
      page: largestMarkets.value.page,
      page_size: largestMarkets.value.page_size,
      sort: rankingSort.value,
      order: rankingOrder.value,
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      largestMarketsError.value = ''
      largestMarkets.value =
        (cached as MarketTablePage<MunicipalityExplorerItem> | null) ||
        emptyMarketTablePage<MunicipalityExplorerItem>(
          largestMarkets.value.page,
          largestMarkets.value.page_size,
        )
      largestMarketsLoading.value = false
      return
    }

    largestMarketsLoading.value = true
    largestMarketsError.value = ''
    try {
      const { data } = await api.get('/api/stats/municipalities', {
        params: {
          ...filters(),
          page: largestMarkets.value.page,
          page_size: largestMarkets.value.page_size,
          sort: rankingSort.value,
          order: rankingOrder.value,
        },
      })
      if (requestVersion !== largestMarketsRequestVersion) return
      largestMarkets.value = data || largestMarkets.value
      rememberMarketSection(cacheKey, largestMarkets.value)
    } catch (error) {
      if (requestVersion !== largestMarketsRequestVersion) return
      largestMarkets.value = emptyMarketTablePage<MunicipalityExplorerItem>(
        largestMarkets.value.page,
        largestMarkets.value.page_size,
      )
      largestMarketsError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === largestMarketsRequestVersion) {
        largestMarketsLoading.value = false
      }
    }
  }

  async function loadPriceLeaders() {
    const requestVersion = ++priceLeadersRequestVersion
    const cacheKey = marketSectionCacheKey('priceLeaders', {
      page: priceLeaders.value.page,
      page_size: priceLeaders.value.page_size,
      sort: 'median_price_per_m2',
      order: 'desc',
    })
    const cached = marketSectionCache.get(cacheKey)

    if (cached) {
      priceLeadersError.value = ''
      priceLeaders.value =
        (cached as MarketTablePage<MunicipalityExplorerItem> | null) ||
        emptyMarketTablePage<MunicipalityExplorerItem>(
          priceLeaders.value.page,
          priceLeaders.value.page_size,
        )
      priceLeadersLoading.value = false
      return
    }

    priceLeadersLoading.value = true
    priceLeadersError.value = ''
    try {
      const { data } = await api.get('/api/stats/municipalities', {
        params: {
          ...filters(),
          page: priceLeaders.value.page,
          page_size: priceLeaders.value.page_size,
          sort: 'median_price_per_m2',
          order: 'desc',
        },
      })
      if (requestVersion !== priceLeadersRequestVersion) return
      priceLeaders.value = data || priceLeaders.value
      rememberMarketSection(cacheKey, priceLeaders.value)
    } catch (error) {
      if (requestVersion !== priceLeadersRequestVersion) return
      priceLeaders.value = emptyMarketTablePage<MunicipalityExplorerItem>(
        priceLeaders.value.page,
        priceLeaders.value.page_size,
      )
      priceLeadersError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === priceLeadersRequestVersion) {
        priceLeadersLoading.value = false
      }
    }
  }

  function activeTabLoaders(includeStaticOverview = false): Promise<void>[] {
    if (activeTab.value === 'transactions') {
      return [loadTransactions()]
    }

    if (activeTab.value === 'rankings') {
      return [loadLargestMarkets(), loadPriceLeaders()]
    }

    if (activeTab.value === 'distribution') {
      return [loadDistribution()]
    }

    return [
      loadTrend(),
      loadRegions(),
      loadLargestMarkets(),
      loadPriceLeaders(),
      ...(includeStaticOverview &&
      !marketFeatureImportance.value.length &&
      !featureImportanceLoading.value
        ? [loadFeatureImportance()]
        : []),
    ]
  }

  function refreshVisibleData(includeStaticOverview = false) {
    void Promise.allSettled([loadMarketHome(), ...activeTabLoaders(includeStaticOverview)])
  }

  const debouncedRefreshVisibleData = useDebounceFn(() => {
    refreshVisibleData()
  }, 180)

  function clearFilters() {
    viewerQuery.patchState({
      property_type: '',
      region: '',
      municipality: '',
      year: '',
      search: '',
    })
  }

  async function addMunicipalityToWatchlist(item: MunicipalityExplorerItem) {
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: item.slug,
      display_label: item.municipality,
      metadata: { link: `/obcine/${item.slug}`, region: item.region },
    })
  }

  function addMunicipalityToCompare(item: MunicipalityExplorerItem) {
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

  function onTransactionsPage(event: MarketPageEvent) {
    transactions.value.page = event.page + 1
    transactions.value.page_size = event.rows
    void loadTransactions()
  }

  function onLargestPage(event: MarketPageEvent) {
    largestMarkets.value.page = event.page + 1
    largestMarkets.value.page_size = event.rows
    void loadLargestMarkets()
  }

  function onLeadersPage(event: MarketPageEvent) {
    priceLeaders.value.page = event.page + 1
    priceLeaders.value.page_size = event.rows
    void loadPriceLeaders()
  }

  async function initializePage() {
    bootstrapLoading.value = true
    bootstrapError.value = ''
    try {
      await referenceData.ensureLoaded()
      normalizeQueryState()
      initialized.value = true
    } catch (error) {
      bootstrapError.value = getApiErrorMessage(error, t)
    } finally {
      bootstrapLoading.value = false
    }

    if (!bootstrapError.value) {
      refreshVisibleData(true)
    }
  }

  watch(
    () => [
      viewerQuery.state.property_type,
      viewerQuery.state.region,
      viewerQuery.state.municipality,
      viewerQuery.state.year,
      viewerQuery.state.search,
    ],
    () => {
      if (!initialized.value) return
      if (normalizeQueryState()) return
      resetTablePages()
      debouncedRefreshVisibleData()
    },
  )

  watch(
    () => activeTab.value,
    () => {
      if (!initialized.value) return
      void Promise.allSettled(activeTabLoaders(true))
    },
  )

  watch(
    () => [transactionSort.value, transactionOrder.value],
    () => {
      if (!initialized.value) return
      transactions.value.page = 1
      void loadTransactions()
    },
  )

  watch(
    () => [rankingSort.value, rankingOrder.value],
    () => {
      if (!initialized.value) return
      largestMarkets.value.page = 1
      void loadLargestMarkets()
    },
  )

  watch(
    () => distributionBins.value,
    () => {
      if (!initialized.value) return
      if (activeTab.value !== 'distribution') return
      void loadDistribution()
    },
  )

  onMounted(() => {
    void initializePage()
  })
</script>

<template>
  <div class="market-page">
    <section class="market-hero">
      <div class="market-hero__copy">
        <PageHeader
          :eyebrow="t('market.consumerKicker')"
          :title="t('market.consumerTitle')"
          :description="t('market.consumerBody')"
        >
          <template #actions>
            <SavedWorkspaceMenu page="market" :state="workspaceState" />
          </template>
        </PageHeader>

        <div class="market-hero__actions">
          <Button
            :as="RouterLink"
            :to="{ path: '/zemljevid', query: routeQuery({ view: 'transactions' }) }"
            class="hero-link hero-link--primary"
            severity="contrast"
            icon="pi pi-map"
            :label="t('nav.map')"
          />
          <Button
            :as="RouterLink"
            :to="{ path: '/obcine', query: routeQuery({ tab: 'table' }) }"
            class="hero-link"
            severity="secondary"
            outlined
            icon="pi pi-building"
            :label="t('nav.municipalities')"
          />
        </div>

        <div class="market-hero__status">
          <Tag :severity="activeFilterTagSeverity" :value="activeFilterTagLabel" />
          <span v-if="filtersRefreshing" class="market-loading-chip">
            <i class="pi pi-spin pi-spinner" aria-hidden="true"></i>
            {{ t('common.loading') }}
          </span>
          <span>{{ t('dashboard.marketLens') }}</span>
        </div>
      </div>

      <div class="market-hero__metrics">
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

    <SectionPanel
      class="market-filters"
      :eyebrow="t('dashboard.activeFilters')"
      :title="t('dashboard.marketLens')"
      compact
    >
      <template #actions>
        <div class="market-filters__actions">
          <Tag :severity="activeFilterTagSeverity" :value="activeFilterTagLabel" />
          <span v-if="filtersRefreshing" class="market-loading-chip">
            <i class="pi pi-spin pi-spinner" aria-hidden="true"></i>
            {{ t('common.loading') }}
          </span>
          <Button
            severity="secondary"
            outlined
            icon="pi pi-filter-slash"
            :label="t('map.clearFilter')"
            @click="clearFilters"
          />
        </div>
      </template>

      <FilterBar :columns="4">
        <FilterField :label="t('market.selectPropertyType')">
          <Select
            v-model="viewerQuery.state.property_type"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>
        <FilterField :label="t('municipalities.filterByRegion')">
          <Select
            v-model="viewerQuery.state.region"
            :options="regionOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>
        <FilterField :label="t('dashboard.municipality')">
          <Select
            v-model="viewerQuery.state.municipality"
            :options="municipalityOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>
        <FilterField :label="t('map.year')">
          <Select
            v-model="viewerQuery.state.year"
            :options="yearOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>
        <FilterField class="market-filters__search" :label="t('common.search')" :span="2">
          <InputText v-model="viewerQuery.state.search" :placeholder="t('common.search')" />
        </FilterField>
      </FilterBar>
    </SectionPanel>

    <LoadingSpinner v-if="bootstrapLoading" :label="t('common.loading')" />
    <div v-else-if="bootstrapError" class="state-card state-card-stack" role="alert">
      <EmptyState :message="bootstrapError" icon="pi pi-exclamation-triangle" />
      <div class="state-card-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="initializePage"
        />
      </div>
    </div>

    <Tabs v-else v-model:value="activeTab" class="market-tabs">
      <TabList>
        <Tab value="overview">{{ t('common.overview') }}</Tab>
        <Tab value="transactions">{{ t('market.tabTransactions') }}</Tab>
        <Tab value="rankings">{{ t('market.tabRankings') }}</Tab>
        <Tab value="distribution">{{ t('market.tabDistribution') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="overview">
          <section class="market-tab-content">
            <div class="market-grid market-grid--overview">
              <MarketSectionCard
                featured
                :eyebrow="t('market.tabTrends')"
                :title="t('market.trendSubtitle')"
                :description="t('market.consumerBody')"
              >
                <MarketStateFrame
                  :loading="trendLoading"
                  :error="trendError"
                  :has-data="trendData.length > 0"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadTrend"
                    />
                  </template>
                  <TrendLineChart :data="trendData" />
                </MarketStateFrame>
              </MarketSectionCard>

              <MarketSectionCard
                :eyebrow="t('dashboard.regionSnapshot')"
                :title="t('dashboard.regionTableTitle')"
                :description="t('dashboard.marketCoverageLabel')"
                compact
              >
                <MarketStateFrame
                  :loading="regionsLoading"
                  :error="regionsError"
                  :has-data="(regions.items || []).length > 0"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadRegions"
                    />
                  </template>
                  <div class="market-rank-list">
                    <RouterLink
                      v-for="(region, index) in regions.items.slice(0, 5)"
                      :key="region.region"
                      :to="{
                        path: '/regije',
                        query: routeQuery({ tab: 'drilldown', region: region.region }),
                      }"
                      class="market-rank-row"
                    >
                      <span class="market-rank-index">#{{ index + 1 }}</span>
                      <div class="market-rank-copy">
                        <strong>{{ region.region }}</strong>
                        <p class="muted">
                          {{ formatNumber(region.count) }} {{ t('dashboard.transactions') }}
                        </p>
                      </div>
                      <Tag
                        severity="success"
                        :value="`${formatCurrency(region.median_price_per_m2)} / m²`"
                      />
                    </RouterLink>
                  </div>
                </MarketStateFrame>
              </MarketSectionCard>
            </div>

            <div class="market-grid market-grid--secondary">
              <MarketSectionCard
                :eyebrow="t('dashboard.largestMarkets')"
                :title="t('market.largestMarketsTitle')"
                compact
              >
                <MarketStateFrame
                  :loading="largestMarketsLoading"
                  :error="largestMarketsError"
                  :has-data="(largestMarkets.items || []).length > 0"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadLargestMarkets"
                    />
                  </template>
                  <div class="market-rank-list">
                    <RouterLink
                      v-for="(item, index) in largestMarkets.items.slice(0, 5)"
                      :key="item.slug"
                      :to="`/obcine/${item.slug}`"
                      class="market-rank-row"
                    >
                      <span class="market-rank-index">#{{ index + 1 }}</span>
                      <div class="market-rank-copy">
                        <strong>{{ item.municipality }}</strong>
                        <p class="muted">{{ item.region || '-' }}</p>
                      </div>
                      <Tag severity="contrast" :value="formatNumber(item.count)" />
                    </RouterLink>
                  </div>
                </MarketStateFrame>
              </MarketSectionCard>

              <MarketSectionCard
                featured
                :eyebrow="t('dashboard.priceLeaders')"
                :title="t('market.priceLeadersTitle')"
                compact
              >
                <MarketStateFrame
                  :loading="priceLeadersLoading"
                  :error="priceLeadersError"
                  :has-data="(priceLeaders.items || []).length > 0"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadPriceLeaders"
                    />
                  </template>
                  <div class="market-rank-list">
                    <RouterLink
                      v-for="(item, index) in priceLeaders.items.slice(0, 5)"
                      :key="item.slug"
                      :to="`/obcine/${item.slug}`"
                      class="market-rank-row"
                    >
                      <span class="market-rank-index">#{{ index + 1 }}</span>
                      <div class="market-rank-copy">
                        <strong>{{ item.municipality }}</strong>
                        <p class="muted">{{ item.region || '-' }}</p>
                      </div>
                      <Tag
                        severity="success"
                        :value="`${formatCurrency(item.median_price_per_m2)} / m²`"
                      />
                    </RouterLink>
                  </div>
                </MarketStateFrame>
              </MarketSectionCard>
            </div>

            <MarketSectionCard
              featured
              :eyebrow="t('market.featureImportance')"
              :title="t('market.featureImportanceDesc')"
              :description="t('market.consumerKicker')"
            >
              <MarketStateFrame
                :loading="featureImportanceLoading"
                :error="featureImportanceError"
                :has-data="marketFeatureImportance.length > 0"
              >
                <template #actions>
                  <Button
                    size="small"
                    severity="secondary"
                    outlined
                    icon="pi pi-refresh"
                    :label="t('common.retry')"
                    @click="loadFeatureImportance"
                  />
                </template>
                <FeatureImportanceChart :features="marketFeatureImportance" :limit="15" />
              </MarketStateFrame>
            </MarketSectionCard>
          </section>
        </TabPanel>

        <TabPanel value="transactions">
          <section class="market-tab-content">
            <TableWorkbenchToolbar
              page="market"
              :state="workspaceState"
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

            <MarketSectionCard
              featured
              :eyebrow="t('market.tabTransactions')"
              :title="t('dashboard.latestTransactions')"
              :description="t('market.consumerBody')"
            >
              <MarketStateFrame
                :loading="transactionsLoading"
                :error="transactionsError"
                :has-data="(transactions.items || []).length > 0"
              >
                <template #actions>
                  <Button
                    size="small"
                    severity="secondary"
                    outlined
                    icon="pi pi-refresh"
                    :label="t('common.retry')"
                    @click="loadTransactions"
                  />
                </template>
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
                    <template #body="{ data }">{{ formatType(data.property_type) }}</template>
                  </Column>
                  <Column field="size_m2" :header="t('predict.size')">
                    <template #body="{ data }">
                      {{ formatNumber(data.size_m2, { maximumFractionDigits: 1 }) }} m²
                    </template>
                  </Column>
                  <Column field="price_eur" :header="t('dashboard.medianPrice')">
                    <template #body="{ data }">{{ formatCurrency(data.price_eur) }}</template>
                  </Column>
                  <Column field="price_per_m2" :header="t('dashboard.pricePerM2')">
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
                          :aria-label="t('workbench.watch')"
                          @click="addMunicipalityToWatchlist(data)"
                        />
                        <Button
                          size="small"
                          severity="secondary"
                          text
                          icon="pi pi-plus-circle"
                          :aria-label="t('workbench.compare')"
                          @click="addMunicipalityToCompare(data)"
                        />
                        <Button
                          :as="RouterLink"
                          :to="{
                            path: '/zemljevid',
                            query: routeQuery({
                              municipality: data.municipality,
                              view: 'transactions',
                            }),
                          }"
                          size="small"
                          severity="secondary"
                          text
                          icon="pi pi-map"
                          :aria-label="t('nav.map')"
                          class="table-link"
                        />
                      </div>
                    </template>
                  </Column>
                </DataTable>
              </MarketStateFrame>
            </MarketSectionCard>
          </section>
        </TabPanel>

        <TabPanel value="rankings">
          <section class="market-tab-content">
            <div class="market-toolbar market-toolbar--compact">
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

            <div class="market-grid market-grid--overview">
              <MarketSectionCard
                :eyebrow="t('dashboard.largestMarkets')"
                :title="t('market.largestMarketsTitle')"
                compact
              >
                <MarketStateFrame
                  :loading="largestMarketsLoading"
                  :error="largestMarketsError"
                  :has-data="(largestMarkets.items || []).length > 0"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadLargestMarkets"
                    />
                  </template>
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
                    <Column field="median_price_per_m2" :header="t('dashboard.pricePerM2')">
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
                            :aria-label="t('workbench.watch')"
                            @click="addMunicipalityToWatchlist(data)"
                          />
                          <Button
                            size="small"
                            severity="secondary"
                            text
                            icon="pi pi-plus-circle"
                            :aria-label="t('workbench.compare')"
                            @click="addMunicipalityToCompare(data)"
                          />
                        </div>
                      </template>
                    </Column>
                  </DataTable>
                </MarketStateFrame>
              </MarketSectionCard>

              <MarketSectionCard
                featured
                :eyebrow="t('dashboard.priceLeaders')"
                :title="t('market.priceLeadersTitle')"
                compact
              >
                <MarketStateFrame
                  :loading="priceLeadersLoading"
                  :error="priceLeadersError"
                  :has-data="(priceLeaders.items || []).length > 0"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadPriceLeaders"
                    />
                  </template>
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
                    <Column field="median_price_per_m2" :header="t('dashboard.pricePerM2')">
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
                            :aria-label="t('workbench.watch')"
                            @click="addMunicipalityToWatchlist(data)"
                          />
                          <Button
                            size="small"
                            severity="secondary"
                            text
                            icon="pi pi-plus-circle"
                            :aria-label="t('workbench.compare')"
                            @click="addMunicipalityToCompare(data)"
                          />
                        </div>
                      </template>
                    </Column>
                  </DataTable>
                </MarketStateFrame>
              </MarketSectionCard>
            </div>
          </section>
        </TabPanel>

        <TabPanel value="distribution">
          <section class="market-tab-content">
            <div class="market-toolbar market-toolbar--compact">
              <InputNumber v-model="distributionBins" :min="5" :max="50" :step="5" />
            </div>

            <div class="market-grid market-grid--overview">
              <MarketSectionCard
                featured
                :eyebrow="t('market.distributionTitle')"
                :title="t('market.distributionSubtitle')"
              >
                <MarketStateFrame
                  :loading="distributionLoading"
                  :error="distributionError"
                  :has-data="Boolean(distributionData?.bins?.length)"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadDistribution"
                    />
                  </template>
                  <PriceDistributionChart
                    v-if="distributionData"
                    :bins="distributionData.bins"
                    :counts="distributionData.counts"
                    :bin-labels="distributionData.bin_labels"
                  />
                </MarketStateFrame>
              </MarketSectionCard>

              <MarketSectionCard
                :eyebrow="t('market.propertyMixTitle')"
                :title="t('market.propertyMixSubtitle')"
                compact
              >
                <MarketStateFrame
                  :loading="marketLoading"
                  :error="marketError"
                  :has-data="(marketHome.property_type_mix || []).length > 0"
                >
                  <template #actions>
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadMarketHome"
                    />
                  </template>
                  <PropertyTypePieChart :items="marketHome.property_type_mix || []" />
                </MarketStateFrame>
              </MarketSectionCard>
            </div>
          </section>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
  .market-page,
  .market-tab-content,
  .market-grid,
  .market-rank-list {
    display: grid;
    gap: 1rem;
  }

  .market-page {
    gap: var(--space-section);
    animation: market-in 420ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .market-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr);
    gap: 1rem;
    padding: clamp(1.1rem, 2vw, 1.55rem);
    border: 1px solid color-mix(in srgb, var(--border) 58%, var(--primary) 42%);
    border-radius: calc(var(--radius-lg) + 0.45rem);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 16%, transparent),
        transparent 28%
      ),
      radial-gradient(
        circle at bottom left,
        color-mix(in srgb, var(--primary) 10%, transparent),
        transparent 26%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-hero) 88%, var(--primary) 12%),
        var(--surface-panel)
      );
    box-shadow: 0 18px 42px color-mix(in srgb, var(--shadow-color) 10%, transparent);
    transition:
      border-color 180ms ease,
      box-shadow 180ms ease,
      transform 180ms ease;
  }

  .market-hero:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--border) 54%, var(--primary) 46%);
    box-shadow: 0 26px 52px color-mix(in srgb, var(--shadow-color) 14%, transparent);
  }

  .market-hero__copy {
    display: grid;
    gap: 1rem;
    align-content: start;
  }

  .market-hero__actions,
  .market-hero__status,
  .market-filters__actions,
  .market-toolbar,
  .row-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .market-hero__status {
    padding: 0.85rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 64%, var(--primary) 36%);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--surface-card) 90%, var(--primary) 10%);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .market-hero__status span {
    color: var(--text-muted);
    font-size: 0.86rem;
    font-weight: 700;
  }

  .market-loading-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--primary) 30%);
    background: color-mix(in srgb, var(--surface-card) 88%, var(--primary-overlay) 12%);
    color: var(--text-muted);
    font-size: 0.78rem;
    font-weight: 700;
    white-space: nowrap;
  }

  .market-hero__metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 0.85rem;
    align-self: stretch;
  }

  .market-filters__actions {
    justify-content: flex-end;
  }

  .market-filters__search {
    grid-column: span 2;
  }

  .market-tabs {
    display: grid;
    gap: var(--space-grid);
  }

  .market-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 14%);
    border-radius: var(--radius-lg);
    background: color-mix(in srgb, var(--surface-strong) 92%, var(--primary-overlay) 8%);
    box-shadow: 0 10px 22px color-mix(in srgb, var(--shadow-color) 8%, transparent);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .market-tabs :deep(.p-tabpanels) {
    padding-top: 0.15rem;
  }

  .market-grid--overview,
  .market-grid--secondary {
    grid-template-columns: 1fr;
  }

  .market-rank-row,
  .table-link {
    text-decoration: none;
    color: inherit;
  }

  .market-rank-row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.8rem;
    padding: 0.85rem 0.95rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: var(--radius-sm);
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--surface-strong) 96%, var(--primary-overlay) 4%),
      color-mix(in srgb, var(--surface-subtle) 92%, var(--overlay-strong) 8%)
    );
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease,
      background 0.16s ease;
  }

  .market-rank-row:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 14%, transparent);
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--surface-strong) 92%, var(--primary-overlay) 8%),
      color-mix(in srgb, var(--surface-subtle) 84%, var(--primary-overlay) 16%)
    );
  }

  .market-rank-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: var(--radius-xs);
    background: color-mix(in srgb, var(--primary) 12%, transparent);
    color: var(--primary);
    font-weight: 800;
  }

  .market-rank-copy strong {
    display: block;
    font-size: 0.95rem;
  }

  .market-rank-copy p {
    margin: 0.2rem 0 0;
  }

  .hero-link--primary {
    box-shadow: 0 18px 30px color-mix(in srgb, var(--primary) 20%, transparent);
  }

  .table-link {
    font-weight: 700;
  }

  @keyframes market-in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 1180px) {
    .market-hero,
    .market-grid--overview,
    .market-grid--secondary {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 1080px) {
    .market-filters__search {
      grid-column: span 1;
    }
  }

  @media (max-width: 720px) {
    .market-hero {
      padding: 0.9rem;
    }

    .market-hero__metrics {
      grid-template-columns: 1fr;
    }

    .market-filters__actions,
    .market-toolbar {
      justify-content: flex-start;
      width: 100%;
    }

    .market-hero__actions :deep(.p-button),
    .market-filters__actions :deep(.p-button),
    .market-toolbar :deep(.p-button),
    .market-toolbar :deep(.p-select),
    .market-toolbar :deep(.p-inputnumber) {
      width: 100%;
    }

    .market-rank-row {
      grid-template-columns: auto minmax(0, 1fr);
    }

    .market-rank-row :deep(.p-tag) {
      grid-column: 1 / -1;
      justify-self: start;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .market-page {
      animation: none;
    }

    .market-hero,
    .market-rank-row {
      transition: none;
    }

    .market-hero:hover,
    .market-rank-row:hover {
      transform: none;
    }
  }
</style>
