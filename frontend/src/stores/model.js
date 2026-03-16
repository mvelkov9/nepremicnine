import { ref } from 'vue'
import { defineStore } from 'pinia'
import api from '../composables/useApi'
import { i18n } from '../i18n'
import { getApiErrorMessage } from '../utils/apiError'

export const useModelStore = defineStore('model', () => {
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

  async function fetchInfo() {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/api/model/info')
      info.value = data
    } catch (e) {
      if (e.response?.status !== 404) error.value = getApiErrorMessage(e, i18n.global.t)
      info.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchImportance() {
    try {
      const { data } = await api.get('/api/model/importance')
      importance.value = data
    } catch {
      importance.value = []
    }
  }

  async function fetchDiagnostics() {
    try {
      const { data } = await api.get('/api/model/diagnostics')
      diagnostics.value = data
    } catch {
      diagnostics.value = null
    }
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
