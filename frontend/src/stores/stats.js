import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../composables/useApi'

export const useStatsStore = defineStore('stats', () => {
  const overview = ref(null)
  const regions = ref([])
  const priceDistribution = ref(null)
  const trend = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function fetchOverview(params = {}) {
    const { data } = await api.get('/api/stats/overview', { params })
    overview.value = data
  }

  async function fetchRegions() {
    const { data } = await api.get('/api/stats/regions')
    regions.value = data
  }

  async function fetchPriceDistribution() {
    const { data } = await api.get('/api/stats/price-distribution')
    priceDistribution.value = data
  }

  async function fetchTrend() {
    const { data } = await api.get('/api/stats/trend')
    trend.value = data
  }

  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      await Promise.all([fetchOverview(), fetchRegions(), fetchPriceDistribution(), fetchTrend()])
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
    } finally {
      loading.value = false
    }
  }

  return {
    overview,
    regions,
    priceDistribution,
    trend,
    loading,
    error,
    fetchAll,
    fetchOverview,
    fetchRegions,
    fetchPriceDistribution,
    fetchTrend,
  }
})
