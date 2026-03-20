import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../composables/useApi'
import { i18n } from '../i18n'
import { getApiErrorMessage } from '../utils/apiError'

export interface UploadProgressContext {
  file: File
  fileProgress: number
  overallProgress: number
  status: 'uploading' | 'processing'
}

interface UploadFilesOptions {
  onFileProgress?: (context: UploadProgressContext) => void
}

interface UploadFileResult {
  file: File
  uploaded: any[]
  skipped: string[]
  message: string
  errorMessage?: string
}

interface UploadBatchResult {
  uploaded: any[]
  skipped: string[]
  message: string
  fileResults: UploadFileResult[]
}

export const useDataStore = defineStore('data', () => {
  const datasets = ref([])
  const trainingDataset = ref(null)
  const qualitySummary = ref(null)
  const uploadCapacity = ref(null)
  const loading = ref(false)
  const uploading = ref(false)
  const uploadProgress = ref(0)

  async function fetchDatasets() {
    loading.value = true
    try {
      const perPage = 200
      let page = 1
      let totalPages = 1
      const allItems = []

      do {
        const { data } = await api.get('/api/data/datasets', {
          params: { page, per_page: perPage },
        })
        const items = Array.isArray(data) ? data : data.items || []
        allItems.push(...items)
        totalPages = Array.isArray(data) ? 1 : data.pages || 1
        page += 1
      } while (page <= totalPages)

      datasets.value = allItems
    } finally {
      loading.value = false
    }
  }

  async function uploadFiles(files, options: UploadFilesOptions = {}): Promise<UploadBatchResult> {
    uploading.value = true
    uploadProgress.value = 0
    try {
      const totalBytes = files.reduce((sum, file) => sum + (file.size || 0), 0)
      let completedBytes = 0
      const aggregated: UploadBatchResult = {
        uploaded: [],
        skipped: [],
        message: '',
        fileResults: [],
      }

      for (const file of files) {
        const formData = new FormData()
        formData.append('files', file)

        let processingSignaled = false
        try {
          const { data } = await api.post('/api/data/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 0,
            maxBodyLength: Infinity,
            maxContentLength: Infinity,
            onUploadProgress: (event) => {
              const loaded = event.loaded || 0
              const total = event.total || file.size || 0
              const fileProgress = total ? Math.min(100, Math.round((loaded * 100) / total)) : 0
              const overallLoaded = completedBytes + Math.min(loaded, file.size || loaded)
              const overallProgress = totalBytes
                ? Math.min(100, Math.round((overallLoaded * 100) / totalBytes))
                : fileProgress

              uploadProgress.value = overallProgress

              if (fileProgress >= 100) {
                if (!processingSignaled) {
                  processingSignaled = true
                  options.onFileProgress?.({
                    file,
                    fileProgress: 100,
                    overallProgress,
                    status: 'processing',
                  })
                }
                return
              }

              options.onFileProgress?.({
                file,
                fileProgress,
                overallProgress,
                status: 'uploading',
              })
            },
          })

          aggregated.uploaded.push(...(data.uploaded || []))
          aggregated.skipped.push(...(data.skipped || []))
          aggregated.message = data.message
          aggregated.fileResults.push({
            file,
            uploaded: data.uploaded || [],
            skipped: data.skipped || [],
            message: data.message || '',
          })
        } catch (error) {
          aggregated.fileResults.push({
            file,
            uploaded: [],
            skipped: [],
            message: '',
            errorMessage: getApiErrorMessage(error, i18n.global.t),
          })
        }

        completedBytes += file.size || 0
        uploadProgress.value = totalBytes
          ? Math.min(100, Math.round((completedBytes * 100) / totalBytes))
          : 100
      }

      await fetchDatasets()
      await fetchUploadCapacity()
      uploadProgress.value = 100
      return aggregated
    } finally {
      uploading.value = false
      uploadProgress.value = 0
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

  async function fetchQualitySummary() {
    const { data } = await api.get('/api/data/quality-summary')
    qualitySummary.value = data
    return data
  }

  async function fetchUploadCapacity() {
    const { data } = await api.get('/api/data/upload-capacity')
    uploadCapacity.value = data
    return data
  }

  return {
    datasets,
    trainingDataset,
    qualitySummary,
    uploadCapacity,
    loading,
    uploading,
    uploadProgress,
    fetchDatasets,
    uploadFiles,
    deleteDataset,
    deleteAllDatasets,
    fetchPreview,
    fetchTrainingDataset,
    fetchQualitySummary,
    fetchUploadCapacity,
  }
})
