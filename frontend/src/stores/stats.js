import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../composables/useApi'
import { i18n } from '../i18n'
import { getApiErrorMessage } from '../utils/apiError'

export const useStatsStore = defineStore('stats', () => {
  const overview = ref(null)
  const regions = ref([])
  const priceDistribution = ref(null)
  const trend = ref([])
  const marketHome = ref(null)
  const municipalityDetail = ref(null)
  const comparables = ref(null)
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
