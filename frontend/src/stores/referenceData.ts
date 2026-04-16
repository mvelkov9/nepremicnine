import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import api from '../composables/useApi'

interface MunicipalityReference {
  municipality: string
  region?: string
}

const SUPPORTED_PROPERTY_TYPES = new Set([
  'stanovanje',
  'hisa',
  'poslovni_prostor',
  'garaza',
  'turisticni',
  'gostinstvo',
  'industrijski',
  'kmetijsko',
  'parcela',
])

export const useReferenceDataStore = defineStore('referenceData', () => {
  const municipalities = ref<MunicipalityReference[]>([])
  const propertyTypes = ref<string[]>([])
  const years = ref<string[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const lastLoadedAt = ref<string | null>(null)
  let pendingLoad: Promise<void> | null = null

  const regions = computed(() =>
    [...new Set(municipalities.value.map((item) => item.region).filter(Boolean))].sort(),
  )

  async function ensureLoaded(force = false) {
    if (loaded.value && !force) return
    if (pendingLoad && !force) return pendingLoad

    pendingLoad = (async () => {
      loading.value = true
      try {
        const [municipalityRes, marketRes, trendRes] = await Promise.all([
          api.get('/api/regions/municipalities'),
          api.get('/api/stats/market-home'),
          api.get('/api/stats/trend'),
        ])
        municipalities.value = municipalityRes.data || []
        propertyTypes.value = (marketRes.data?.property_type_mix || [])
          .map((item: { property_type: string }) => String(item.property_type || '').trim())
          .filter((value) => SUPPORTED_PROPERTY_TYPES.has(value))
        years.value = (trendRes.data || []).map((item: { year: string | number }) =>
          String(item.year),
        )
        loaded.value = true
        lastLoadedAt.value = new Date().toISOString()
      } finally {
        loading.value = false
        pendingLoad = null
      }
    })()

    return pendingLoad
  }

  return {
    municipalities,
    propertyTypes,
    years,
    regions,
    loaded,
    loading,
    lastLoadedAt,
    ensureLoaded,
  }
})
