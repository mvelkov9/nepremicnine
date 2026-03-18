import { computed, ref } from 'vue'
import api from './useApi'
import { normalizeMunicipalityName } from '../utils/municipality'

const municipalities = ref([])
const loading = ref(false)

let loaded = false
let fetchPromise = null

async function fetchMunicipalities(options = {}) {
  if (loaded && !options.force) {
    return municipalities.value
  }

  if (fetchPromise && !options.force) {
    return fetchPromise
  }

  loading.value = true
  fetchPromise = api
    .get('/api/regions/municipalities', {
      skipErrorToast: true,
      ...options.requestConfig,
    })
    .then(({ data }) => {
      municipalities.value = data || []
      loaded = true
      return municipalities.value
    })
    .catch(() => {
      if (!loaded) {
        municipalities.value = []
      }
      return municipalities.value
    })
    .finally(() => {
      loading.value = false
      fetchPromise = null
    })

  return fetchPromise
}

export function useMunicipalityLookup() {
  const municipalitySuggestions = ref([])

  const municipalityIndex = computed(
    () =>
      new Map(
        municipalities.value.map((item) => [normalizeMunicipalityName(item.municipality), item]),
      ),
  )

  function searchMunicipalities(event) {
    const query = normalizeMunicipalityName(event?.query || '')
    municipalitySuggestions.value = query
      ? municipalities.value
          .filter((item) => normalizeMunicipalityName(item.municipality).includes(query))
          .map((item) => item.municipality)
          .slice(0, 12)
      : municipalities.value.map((item) => item.municipality).slice(0, 12)
  }

  function findMunicipalityMeta(name) {
    return municipalityIndex.value.get(normalizeMunicipalityName(name)) || null
  }

  return {
    municipalities,
    municipalitySuggestions,
    municipalityIndex,
    loading,
    fetchMunicipalities,
    searchMunicipalities,
    findMunicipalityMeta,
  }
}