import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../composables/useApi'

export const useDataStore = defineStore('data', () => {
  const datasets = ref([])
  const trainingDataset = ref(null)
  const loading = ref(false)
  const uploading = ref(false)

  async function fetchDatasets() {
    loading.value = true
    try {
      const { data } = await api.get('/api/data/datasets', { params: { per_page: 200 } })
      datasets.value = Array.isArray(data) ? data : data.items || []
    } finally {
      loading.value = false
    }
  }

  async function uploadFiles(files) {
    uploading.value = true
    try {
      const formData = new FormData()
      for (const file of files) {
        formData.append('files', file)
      }
      const { data } = await api.post('/api/data/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000,
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
      })
      await fetchDatasets()
      return data
    } finally {
      uploading.value = false
    }
  }

  async function deleteDataset(id) {
    await api.delete(`/api/data/datasets/${id}`)
    datasets.value = datasets.value.filter((d) => d.id !== id)
  }

  async function deleteAllDatasets() {
    const ids = datasets.value.map((d) => d.id)
    if (!ids.length) return
    await api.post('/api/data/datasets/delete-bulk', { dataset_ids: ids })
    datasets.value = []
  }

  async function fetchPreview(id, limit = 20) {
    const { data } = await api.get(`/api/data/preview/${id}`, { params: { limit } })
    return data
  }

  async function fetchTrainingDataset() {
    const { data } = await api.get('/api/data/training-dataset')
    trainingDataset.value = data
    return data
  }

  return {
    datasets,
    trainingDataset,
    loading,
    uploading,
    fetchDatasets,
    uploadFiles,
    deleteDataset,
    deleteAllDatasets,
    fetchPreview,
    fetchTrainingDataset,
  }
})
