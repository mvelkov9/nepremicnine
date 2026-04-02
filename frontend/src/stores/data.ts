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

interface UploadedItem {
  id: number
  original_name: string
  relative_path: string
  row_count: number
}

interface UploadFileResult {
  file: File
  uploaded: UploadedItem[]
  skipped: string[]
  message: string
  errorMessage?: string
}

interface UploadBatchResult {
  uploaded: UploadedItem[]
  skipped: string[]
  message: string
  fileResults: UploadFileResult[]
}

interface FetchDatasetsOptions {
  page?: number
  perPage?: number
}

export const useDataStore = defineStore('data', () => {
  const datasets = ref([])
  const datasetsPage = ref(1)
  const datasetsPerPage = ref(10)
  const datasetsTotal = ref(0)
  const datasetsPages = ref(0)
  const trainingDataset = ref(null)
  const qualitySummary = ref(null)
  const uploadCapacity = ref(null)
  const loading = ref(false)
  const uploading = ref(false)
  const uploadProgress = ref(0)
  let fetchDatasetsInFlight: Promise<void> | null = null
  let fetchTrainingDatasetInFlight: Promise<unknown> | null = null
  let fetchQualitySummaryInFlight: Promise<unknown> | null = null
  let allDatasetsCached = false

  async function fetchDatasets(
    withSync = false,
    fetchAllPages = false,
    options: FetchDatasetsOptions = {},
  ) {
    // If we already have all pages loaded and no sync is needed, skip re-fetching
    if (fetchAllPages && !withSync && allDatasetsCached && datasets.value.length > 0) return

    if (fetchDatasetsInFlight) return fetchDatasetsInFlight

    fetchDatasetsInFlight = (async () => {
      loading.value = true
      try {
        const requestedPage = Math.max(1, Number(options.page || 1))
        const requestedPerPage = Math.max(
          1,
          Math.min(200, Number(options.perPage || (fetchAllPages ? 200 : 10))),
        )

        if (fetchAllPages) {
          let page = 1
          let totalPages = 1
          let total = 0
          const allItems = []

          do {
            const { data } = await api.get('/api/data/datasets', {
              params: { page, per_page: requestedPerPage, sync: withSync && page === 1 },
            })
            const items = Array.isArray(data) ? data : data.items || []
            allItems.push(...items)
            totalPages = Array.isArray(data) ? 1 : Number(data.pages || 1)
            total = Array.isArray(data) ? allItems.length : Number(data.total || allItems.length)
            page += 1
          } while (page <= totalPages)

          datasets.value = allItems
          datasetsPage.value = requestedPage
          datasetsPerPage.value = requestedPerPage
          datasetsTotal.value = total
          datasetsPages.value = totalPages
          allDatasetsCached = true
          return
        }

        const { data } = await api.get('/api/data/datasets', {
          params: { page: requestedPage, per_page: requestedPerPage, sync: withSync },
        })
        const items = Array.isArray(data) ? data : data.items || []
        const total = Array.isArray(data) ? items.length : Number(data.total || items.length)
        const pages = Array.isArray(data) ? 1 : Number(data.pages || 1)

        datasets.value = items
        datasetsPage.value = requestedPage
        datasetsPerPage.value = requestedPerPage
        datasetsTotal.value = total
        datasetsPages.value = pages
      } finally {
        loading.value = false
        fetchDatasetsInFlight = null
      }
    })()

    return fetchDatasetsInFlight
  }

  async function uploadFiles(
    files: File[],
    options: UploadFilesOptions = {},
  ): Promise<UploadBatchResult> {
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

      allDatasetsCached = false
      await fetchDatasets()
      await fetchUploadCapacity()
      uploadProgress.value = 100
      return aggregated
    } finally {
      uploading.value = false
      uploadProgress.value = 0
    }
  }

  async function deleteDataset(id: number) {
    allDatasetsCached = false
    await api.delete(`/api/data/datasets/${id}`)
    datasets.value = datasets.value.filter((d) => d.id !== id)
    datasetsTotal.value = Math.max(0, Number(datasetsTotal.value || 0) - 1)
    datasetsPages.value = datasetsPerPage.value
      ? Math.ceil(datasetsTotal.value / datasetsPerPage.value)
      : 0
  }

  async function deleteAllDatasets() {
    allDatasetsCached = false
    const ids = datasets.value.map((d) => d.id)
    if (!ids.length) return
    await api.post('/api/data/datasets/delete-bulk', { dataset_ids: ids })
    datasets.value = []
    datasetsPage.value = 1
    datasetsTotal.value = 0
    datasetsPages.value = 0
  }

  async function fetchPreview(id: number, limit = 20) {
    const { data } = await api.get(`/api/data/preview/${id}`, { params: { limit } })
    return data
  }

  async function fetchTrainingDataset() {
    if (fetchTrainingDatasetInFlight) return fetchTrainingDatasetInFlight
    fetchTrainingDatasetInFlight = (async () => {
      const { data } = await api.get('/api/data/training-dataset')
      trainingDataset.value = data
      return data
    })()
    try {
      return await fetchTrainingDatasetInFlight
    } finally {
      fetchTrainingDatasetInFlight = null
    }
  }

  async function fetchQualitySummary() {
    if (fetchQualitySummaryInFlight) return fetchQualitySummaryInFlight
    fetchQualitySummaryInFlight = (async () => {
      const { data } = await api.get('/api/data/quality-summary')
      qualitySummary.value = data
      return data
    })()
    try {
      return await fetchQualitySummaryInFlight
    } finally {
      fetchQualitySummaryInFlight = null
    }
  }

  async function fetchUploadCapacity() {
    const { data } = await api.get('/api/data/upload-capacity')
    uploadCapacity.value = data
    return data
  }

  async function rescanDatasets() {
    allDatasetsCached = false
    const { data } = await api.post('/api/data/datasets/rescan', null, { timeout: 0 })
    await fetchDatasets(false, false)
    return data
  }

  return {
    datasets,
    datasetsPage,
    datasetsPerPage,
    datasetsTotal,
    datasetsPages,
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
    rescanDatasets,
  }
})
