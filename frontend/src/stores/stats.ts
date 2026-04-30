import axios from 'axios'
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
  const inflightControllers = new Map<string, AbortController>()

  async function runLatestRequest<T>(
    key: string,
    request: (signal: AbortSignal) => Promise<T>,
    fallback: () => T,
  ) {
    inflightControllers.get(key)?.abort()
    const controller = new AbortController()
    inflightControllers.set(key, controller)

    try {
      return await request(controller.signal)
    } catch (requestError) {
      if (
        axios.isCancel(requestError) ||
        (requestError as { code?: string })?.code === 'ERR_CANCELED'
      ) {
        return fallback()
      }
      throw requestError
    } finally {
      if (inflightControllers.get(key) === controller) {
        inflightControllers.delete(key)
      }
    }
  }

  async function fetchOverview(params = {}) {
    const { data } = await api.get('/api/stats/overview', { params })
    overview.value = data
  }

  async function fetchRegions(params = {}) {
    return runLatestRequest(
      'regions',
      async (signal) => {
        const { data } = await api.get('/api/stats/regions', { params, signal })
        regions.value = data
        return data
      },
      () => regions.value,
    )
  }

  async function fetchPriceDistribution(params = {}) {
    return runLatestRequest(
      'priceDistribution',
      async (signal) => {
        const { data } = await api.get('/api/stats/price-distribution', { params, signal })
        priceDistribution.value = data
        return data
      },
      () => priceDistribution.value,
    )
  }

  async function fetchTrend(params = {}) {
    return runLatestRequest(
      'trend',
      async (signal) => {
        const { data } = await api.get('/api/stats/trend', { params, signal })
        trend.value = data
        return data
      },
      () => trend.value,
    )
  }

  async function fetchMarketHome(params = {}) {
    return runLatestRequest(
      'marketHome',
      async (signal) => {
        const { data } = await api.get('/api/stats/market-home', { params, signal })
        marketHome.value = data
        return data
      },
      () => marketHome.value,
    )
  }

  async function fetchMunicipalityDetail(slug: string, params = {}) {
    return runLatestRequest(
      'municipalityDetail',
      async (signal) => {
        const { data } = await api.get(`/api/stats/municipality/${slug}`, { params, signal })
        municipalityDetail.value = data
        return data
      },
      () => municipalityDetail.value,
    )
  }

  async function fetchComparables(params) {
    return runLatestRequest(
      'comparables',
      async (signal) => {
        const { data } = await api.get('/api/stats/comparables', { params, signal })
        comparables.value = data
        return data
      },
      () => comparables.value,
    )
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
    return runLatestRequest(
      `municipalitiesByRegion:${region || 'all'}`,
      async (signal) => {
        const { data } = await api.get('/api/stats/municipalities-by-region', { params, signal })
        municipalitiesByRegion.value = data
        return data
      },
      () => municipalitiesByRegion.value,
    )
  }

  async function fetchTransactionsExplorer(params = {}) {
    return runLatestRequest(
      'transactionsExplorer',
      async (signal) => {
        const { data } = await api.get('/api/stats/transactions', { params, signal })
        transactionsExplorer.value = data
        return data
      },
      () => transactionsExplorer.value,
    )
  }

  async function fetchMunicipalitiesExplorer(params = {}) {
    return runLatestRequest(
      'municipalitiesExplorer',
      async (signal) => {
        const { data } = await api.get('/api/stats/municipalities', { params, signal })
        municipalitiesExplorer.value = data
        return data
      },
      () => municipalitiesExplorer.value,
    )
  }

  async function fetchRegionsExplorer(params = {}) {
    return runLatestRequest(
      'regionsExplorer',
      async (signal) => {
        const { data } = await api.get('/api/stats/regions-explorer', { params, signal })
        regionsExplorer.value = data
        return data
      },
      () => regionsExplorer.value,
    )
  }

  async function fetchMunicipalityTransactions(slug: string, params = {}) {
    return runLatestRequest(
      `municipalityTransactions:${slug}`,
      async (signal) => {
        const { data } = await api.get(`/api/stats/municipality/${slug}/transactions`, {
          params,
          signal,
        })
        municipalityTransactions.value = data
        return data
      },
      () => municipalityTransactions.value,
    )
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
