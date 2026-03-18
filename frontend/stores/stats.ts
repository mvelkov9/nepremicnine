interface HeadlineStats {
  total_records: number | null
  median_price: number | null
  avg_price_per_m2: number | null
  earliest_year: number | null
  latest_year: number | null
}

interface MarketItem {
  municipality: string
  slug: string
  region: string
  count: number
  median_price: number
  median_price_per_m2: number
}

interface PropertyTypeMix {
  property_type: string
  count: number
  share: number
}

interface RegionItem {
  region: string
  count: number
  median_price_per_m2: number
  min_price?: number
  max_price?: number
}

interface SaleItem {
  municipality: string
  slug: string
  property_type: string
  size_m2: number
  price_eur: number
  price_per_m2: number
  year: number
}

interface MarketCoverage {
  present: number
  official_total: number
}

interface MarketHome {
  headline: HeadlineStats
  largest_markets: MarketItem[]
  price_leaders: MarketItem[]
  region_snapshot: RegionItem[]
  latest_sales: SaleItem[]
  property_type_mix: PropertyTypeMix[]
  market_coverage?: MarketCoverage
}

export const useStatsStore = defineStore('stats', () => {
  const overview = ref<Record<string, unknown> | null>(null)
  const regions = ref<RegionItem[]>([])
  const priceDistribution = ref<Record<string, unknown> | null>(null)
  const trend = ref<unknown[]>([])
  const marketHome = ref<MarketHome | null>(null)
  const municipalityDetail = ref<Record<string, unknown> | null>(null)
  const comparables = ref<Record<string, unknown> | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const api = useApi()
  const { t } = useI18n()

  async function fetchOverview(params: Record<string, unknown> = {}): Promise<void> {
    const { data } = await api.get<Record<string, unknown>>('/api/stats/overview', { params })
    overview.value = data
  }

  async function fetchRegions(params: Record<string, unknown> = {}): Promise<RegionItem[]> {
    const { data } = await api.get<RegionItem[]>('/api/stats/regions', { params })
    regions.value = data
    return data
  }

  async function fetchPriceDistribution(
    params: Record<string, unknown> = {},
  ): Promise<Record<string, unknown>> {
    const { data } = await api.get<Record<string, unknown>>('/api/stats/price-distribution', {
      params,
    })
    priceDistribution.value = data
    return data
  }

  async function fetchTrend(params: Record<string, unknown> = {}): Promise<unknown[]> {
    const { data } = await api.get<unknown[]>('/api/stats/trend', { params })
    trend.value = data
    return data
  }

  async function fetchMarketHome(params: Record<string, unknown> = {}): Promise<MarketHome> {
    const { data } = await api.get<MarketHome>('/api/stats/market-home', { params })
    marketHome.value = data
    return data
  }

  async function fetchMunicipalityDetail(slug: string): Promise<Record<string, unknown>> {
    const { data } = await api.get<Record<string, unknown>>(`/api/stats/municipality/${slug}`)
    municipalityDetail.value = data
    return data
  }

  async function fetchComparables(
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const { data } = await api.get<Record<string, unknown>>('/api/stats/comparables', { params })
    comparables.value = data
    return data
  }

  function resetMunicipalityDetail(): void {
    municipalityDetail.value = null
  }

  function resetComparables(): void {
    comparables.value = null
  }

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await Promise.all([
        fetchOverview(),
        fetchRegions(),
        fetchPriceDistribution(),
        fetchTrend(),
        fetchMarketHome(),
      ])
    } catch (e) {
      error.value = getApiErrorMessage(e as Error, t)
    } finally {
      loading.value = false
    }
  }

  return {
    overview,
    regions,
    priceDistribution,
    trend,
    marketHome,
    municipalityDetail,
    comparables,
    loading,
    error,
    fetchAll,
    fetchOverview,
    fetchRegions,
    fetchPriceDistribution,
    fetchTrend,
    fetchMarketHome,
    fetchMunicipalityDetail,
    fetchComparables,
    resetMunicipalityDetail,
    resetComparables,
  }
})
