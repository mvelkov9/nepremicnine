import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../composables/useApi'

export const useDataStore = defineStore('data', () => {
  const datasets = ref([])
  const loading = ref(false)
  const uploading = ref(false)

  async function fetchDatasets() {
    loading.value = true
    try {
      const { data } = await api.get('/api/data/datasets')
      datasets.value = Array.isArray(data) ? data : []
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

  async function fetchPreview(id, limit = 20) {
    const { data } = await api.get(`/api/data/preview/${id}`, { params: { limit } })
    return data
  }

  return { datasets, loading, uploading, fetchDatasets, uploadFiles, deleteDataset, fetchPreview }
})
