import { ref } from 'vue'
import { defineStore } from 'pinia'
import api from '../composables/useApi'

export const useModelStore = defineStore('model', () => {
  const info = ref(null)
  const importance = ref([])
  const training = ref(false)
  const trainingStatus = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchInfo() {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/api/model/info')
      info.value = data
    } catch (e) {
      if (e.response?.status !== 404) error.value = e.message
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

  async function startTraining(csvPath) {
    training.value = true
    error.value = null
    try {
      const { data } = await api.post('/api/train/start', { csv_path: csvPath })
      trainingStatus.value = data
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
      throw e
    }
  }

  async function pollStatus(jobId) {
    try {
      const { data } = await api.get(`/api/train/status/${jobId}`)
      trainingStatus.value = data
      if (data.status === 'completed' || data.status === 'failed') {
        training.value = false
      }
      return data
    } catch (e) {
      error.value = e.message
      return null
    }
  }

  function reset() {
    training.value = false
    trainingStatus.value = null
    error.value = null
  }

  return {
    info, importance, training, trainingStatus, loading, error,
    fetchInfo, fetchImportance, startTraining, pollStatus, reset,
  }
})
