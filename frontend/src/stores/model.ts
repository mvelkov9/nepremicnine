import { ref } from 'vue'
import { defineStore } from 'pinia'
import api from '../composables/useApi'
import { i18n } from '../i18n'
import { getApiErrorMessage } from '../utils/apiError'

export const useModelStore = defineStore('model', () => {
  const SHARED_MODEL_CACHE_TTL_MS = 15_000
  const info = ref(null)
  const diagnostics = ref(null)
  const importance = ref([])
  const training = ref(false)
  const trainingStatus = ref(null)
  const jobHistory = ref([])
  const modelRuns = ref([])
  const jobsLoading = ref(false)
  const runsLoading = ref(false)
  const loading = ref(false)
  const error = ref(null)
  let infoFetchedAt = 0
  let diagnosticsFetchedAt = 0
  let importanceFetchedAt = 0
  let fetchInfoInFlight: Promise<unknown> | null = null
  let fetchDiagnosticsInFlight: Promise<unknown> | null = null
  let fetchImportanceInFlight: Promise<unknown> | null = null

  function isSharedModelCacheFresh(timestamp: number) {
    return timestamp > 0 && Date.now() - timestamp < SHARED_MODEL_CACHE_TTL_MS
  }

  function invalidateModelMetadataCache() {
    infoFetchedAt = 0
    diagnosticsFetchedAt = 0
    importanceFetchedAt = 0
  }

  async function fetchInfo(force = false) {
    if (!force && isSharedModelCacheFresh(infoFetchedAt)) {
      return info.value
    }
    if (fetchInfoInFlight) return fetchInfoInFlight

    loading.value = true
    error.value = null
    fetchInfoInFlight = (async () => {
      try {
        const { data } = await api.get('/api/model/info')
        info.value = data
        infoFetchedAt = Date.now()
        return data
      } catch (e) {
        if (e.response?.status !== 404) {
          error.value = getApiErrorMessage(e, i18n.global.t)
          infoFetchedAt = 0
        } else {
          infoFetchedAt = Date.now()
        }
        info.value = null
        return null
      } finally {
        loading.value = false
        fetchInfoInFlight = null
      }
    })()

    return fetchInfoInFlight
  }

  async function fetchImportance(force = false) {
    if (!force && isSharedModelCacheFresh(importanceFetchedAt)) {
      return importance.value
    }
    if (fetchImportanceInFlight) return fetchImportanceInFlight

    fetchImportanceInFlight = (async () => {
      try {
        const { data } = await api.get('/api/model/importance')
        importance.value = data
        importanceFetchedAt = Date.now()
        return data
      } catch {
        importance.value = []
        importanceFetchedAt = 0
        return []
      } finally {
        fetchImportanceInFlight = null
      }
    })()

    return fetchImportanceInFlight
  }

  async function fetchDiagnostics(force = false) {
    if (!force && isSharedModelCacheFresh(diagnosticsFetchedAt)) {
      return diagnostics.value
    }
    if (fetchDiagnosticsInFlight) return fetchDiagnosticsInFlight

    fetchDiagnosticsInFlight = (async () => {
      try {
        const { data } = await api.get('/api/model/diagnostics')
        diagnostics.value = data
        diagnosticsFetchedAt = Date.now()
        return data
      } catch {
        diagnostics.value = null
        diagnosticsFetchedAt = 0
        return null
      } finally {
        fetchDiagnosticsInFlight = null
      }
    })()

    return fetchDiagnosticsInFlight
  }

  async function startTraining(csvPath) {
    training.value = true
    error.value = null
    try {
      const { data } = await api.post('/api/train/start', { csv_path: csvPath })
      trainingStatus.value = data
      return data
    } catch (e) {
      const activeJob =
        e.response?.status === 409 && e.response?.data?.job_id
          ? {
              ...e.response.data,
              status: e.response.data.status || 'queued',
              stage: e.response.data.stage || null,
              progress: e.response.data.progress || 0,
              result: e.response.data.result || null,
              error: e.response.data.error || null,
            }
          : null

      if (activeJob) {
        training.value = activeJob.status === 'queued' || activeJob.status === 'running'
        trainingStatus.value = activeJob
        return activeJob
      }

      training.value = false
      error.value = getApiErrorMessage(e, i18n.global.t)
      throw e
    }
  }

  async function fetchActiveTraining() {
    try {
      const { data } = await api.get('/api/train/active')
      trainingStatus.value = data
      training.value = data.status === 'queued' || data.status === 'running'
      return data
    } catch (e) {
      if (e.response?.status === 404) {
        training.value = false
        return null
      }
      error.value = getApiErrorMessage(e, i18n.global.t)
      return null
    }
  }

  async function pollStatus(jobId) {
    try {
      const { data } = await api.get(`/api/train/status/${jobId}`)
      trainingStatus.value = data
      training.value = data.status === 'queued' || data.status === 'running'
      if (!training.value) {
        invalidateModelMetadataCache()
      }
      return data
    } catch (e) {
      training.value = false
      error.value = getApiErrorMessage(e, i18n.global.t)
      return null
    }
  }

  async function fetchJobs(params = {}) {
    jobsLoading.value = true
    try {
      const { data } = await api.get('/api/train/jobs', {
        params: { per_page: 8, ...params },
      })
      jobHistory.value = data.items || []
      return data
    } catch (e) {
      jobHistory.value = []
      error.value = getApiErrorMessage(e, i18n.global.t)
      return null
    } finally {
      jobsLoading.value = false
    }
  }

  async function fetchRuns(params = {}) {
    runsLoading.value = true
    try {
      const { data } = await api.get('/api/model/runs', {
        params: { per_page: 8, ...params },
      })
      modelRuns.value = data.items || []
      return data
    } catch (e) {
      modelRuns.value = []
      error.value = getApiErrorMessage(e, i18n.global.t)
      return null
    } finally {
      runsLoading.value = false
    }
  }

  function reset() {
    training.value = false
    trainingStatus.value = null
    modelRuns.value = []
    error.value = null
    invalidateModelMetadataCache()
  }

  return {
    info,
    diagnostics,
    importance,
    training,
    trainingStatus,
    jobHistory,
    modelRuns,
    jobsLoading,
    runsLoading,
    loading,
    error,
    fetchInfo,
    fetchImportance,
    fetchDiagnostics,
    startTraining,
    fetchActiveTraining,
    pollStatus,
    fetchJobs,
    fetchRuns,
    reset,
  }
})
