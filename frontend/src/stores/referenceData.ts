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
  const error = ref<string | null>(null)
  const lastLoadedAt = ref<string | null>(null)
  let pendingLoad: Promise<void> | null = null

  const regions = computed(() =>
    [...new Set(municipalities.value.map((item) => item.region).filter(Boolean))].sort(),
  )

  async function ensureLoaded(force = false) {
    if (loaded.value && !force) return
    if (pendingLoad && !force) return pendingLoad

    pendingLoad = (async () => {
      const wasLoaded = loaded.value
      loading.value = true
      error.value = null
      try {
        const [municipalityRes, marketRes, trendRes] = await Promise.allSettled([
          api.get('/api/regions/municipalities'),
          api.get('/api/stats/market-home'),
          api.get('/api/stats/trend'),
        ])

        if (municipalityRes.status === 'fulfilled') {
          municipalities.value = municipalityRes.value.data || []
        }

        if (marketRes.status === 'fulfilled') {
          propertyTypes.value = (marketRes.value.data?.property_type_mix || [])
            .map((item: { property_type: string }) => String(item.property_type || '').trim())
            .filter((value) => SUPPORTED_PROPERTY_TYPES.has(value))
        }

        if (trendRes.status === 'fulfilled') {
          years.value = (trendRes.value.data || []).map((item: { year: string | number }) =>
            String(item.year),
          )
        }

        const allSucceeded = [municipalityRes, marketRes, trendRes].every(
          (result) => result.status === 'fulfilled',
        )

        loaded.value = allSucceeded || wasLoaded

        if (allSucceeded) {
          lastLoadedAt.value = new Date().toISOString()
          return
        }

        const failedSections = [
          municipalityRes.status === 'rejected' ? 'municipalities' : null,
          marketRes.status === 'rejected' ? 'market' : null,
          trendRes.status === 'rejected' ? 'trend' : null,
        ].filter((value): value is string => Boolean(value))

        if (failedSections.length) {
          error.value = `Reference data unavailable: ${failedSections.join(', ')}`
        }
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
    error,
    lastLoadedAt,
    ensureLoaded,
  }
})
