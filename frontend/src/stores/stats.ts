import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../composables/useApi'
import { i18n } from '../i18n'
import type {
  ExplorerResponse,
  MunicipalityExplorerItem,
  RegionExplorerItem,
  TransactionRecord,
} from '../types/api'
import { getApiErrorMessage } from '../utils/apiError'

export const useStatsStore = defineStore('stats', () => {
  const overview = ref(null)
  const regions = ref([])
  const priceDistribution = ref(null)
  const trend = ref([])
  const marketHome = ref(null)
  const municipalityDetail = ref(null)
  const comparables = ref(null)
  const featureImportance = ref([])
  const municipalitiesByRegion = ref([])
  const transactionsExplorer = ref<ExplorerResponse<TransactionRecord> | null>(null)
  const municipalitiesExplorer = ref<ExplorerResponse<MunicipalityExplorerItem> | null>(null)
  const regionsExplorer = ref<ExplorerResponse<RegionExplorerItem> | null>(null)
  const municipalityTransactions = ref<ExplorerResponse<TransactionRecord> | null>(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchOverview(params = {}) {
    const { data } = await api.get('/api/stats/overview', { params })
    overview.value = data
  }

  async function fetchRegions(params = {}) {
    const { data } = await api.get('/api/stats/regions', { params })
    regions.value = data
    return data
  }

  async function fetchPriceDistribution(params = {}) {
    const { data } = await api.get('/api/stats/price-distribution', { params })
    priceDistribution.value = data
    return data
  }

  async function fetchTrend(params = {}) {
    const { data } = await api.get('/api/stats/trend', { params })
    trend.value = data
    return data
  }

  async function fetchMarketHome(params = {}) {
    const { data } = await api.get('/api/stats/market-home', { params })
    marketHome.value = data
    return data
  }

  async function fetchMunicipalityDetail(slug) {
    const { data } = await api.get(`/api/stats/municipality/${slug}`)
    municipalityDetail.value = data
    return data
  }

  async function fetchComparables(params) {
    const { data } = await api.get('/api/stats/comparables', { params })
    comparables.value = data
    return data
  }

  function resetMunicipalityDetail() {
    municipalityDetail.value = null
  }

  function resetComparables() {
    comparables.value = null
  }

  async function fetchFeatureImportance() {
    const { data } = await api.get('/api/model/importance')
    featureImportance.value = data
    return data
  }

  async function fetchMunicipalitiesByRegion(region?: string) {
    const params: Record<string, string> = {}
    if (region) params.region = region
    const { data } = await api.get('/api/stats/municipalities-by-region', { params })
    municipalitiesByRegion.value = data
    return data
  }

  async function fetchTransactionsExplorer(params = {}) {
    const { data } = await api.get('/api/stats/transactions', { params })
    transactionsExplorer.value = data
    return data
  }

  async function fetchMunicipalitiesExplorer(params = {}) {
    const { data } = await api.get('/api/stats/municipalities', { params })
    municipalitiesExplorer.value = data
    return data
  }

  async function fetchRegionsExplorer(params = {}) {
    const { data } = await api.get('/api/stats/regions-explorer', { params })
    regionsExplorer.value = data
    return data
  }

  async function fetchMunicipalityTransactions(slug: string, params = {}) {
    const { data } = await api.get(`/api/stats/municipality/${slug}/transactions`, { params })
    municipalityTransactions.value = data
    return data
  }

  function resetExplorerData() {
    transactionsExplorer.value = null
    municipalitiesExplorer.value = null
    regionsExplorer.value = null
    municipalityTransactions.value = null
  }

  async function fetchAll() {
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
      error.value = getApiErrorMessage(e, i18n.global.t)
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
    featureImportance,
    municipalitiesByRegion,
    transactionsExplorer,
    municipalitiesExplorer,
    regionsExplorer,
    municipalityTransactions,
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
    fetchFeatureImportance,
    fetchMunicipalitiesByRegion,
    fetchTransactionsExplorer,
    fetchMunicipalitiesExplorer,
    fetchRegionsExplorer,
    fetchMunicipalityTransactions,
    resetMunicipalityDetail,
    resetComparables,
    resetExplorerData,
  }
})
