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
  search?: string
  sort?: string
  order?: 'asc' | 'desc'
}

interface DatasetPageCacheEntry {
  items: unknown[]
  page: number
  perPage: number
  total: number
  pages: number
}

export const useDataStore = defineStore('data', () => {
  const SHARED_DATA_CACHE_TTL_MS = 15_000
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
  let fetchDatasetsVersion = 0
  let fetchDatasetsInFlight: Promise<void> | null = null
  let fetchDatasetsRequestKey = ''
  let fetchTrainingDatasetInFlight: Promise<unknown> | null = null
  let fetchQualitySummaryInFlight: Promise<unknown> | null = null
  let fetchUploadCapacityInFlight: Promise<unknown> | null = null
  let allDatasetsCached = false
  const datasetPageCache = new Map<string, DatasetPageCacheEntry>()
  let trainingDatasetFetchedAt = 0
  let qualitySummaryFetchedAt = 0
  let uploadCapacityFetchedAt = 0

  function clearDatasetPageCache() {
    datasetPageCache.clear()
  }

  function isSharedDataCacheFresh(timestamp: number) {
    return timestamp > 0 && Date.now() - timestamp < SHARED_DATA_CACHE_TTL_MS
  }

  function invalidateSharedDatasetMetadata() {
    trainingDatasetFetchedAt = 0
    qualitySummaryFetchedAt = 0
    uploadCapacityFetchedAt = 0
  }

  async function fetchDatasets(
    withSync = false,
    fetchAllPages = false,
    options: FetchDatasetsOptions = {},
  ) {
    // If we already have all pages loaded and no sync is needed, skip re-fetching
    if (fetchAllPages && !withSync && allDatasetsCached && datasets.value.length > 0) return

    const requestKey = JSON.stringify({
      withSync,
      fetchAllPages,
      page: Number(options.page || 1),
      perPage: Number(options.perPage || (fetchAllPages ? 200 : 10)),
      search: String(options.search || '').trim(),
      sort: String(options.sort || 'uploaded_at'),
      order: options.order === 'asc' ? 'asc' : 'desc',
    })

    if (!withSync) {
      const cached = datasetPageCache.get(requestKey)
      if (cached) {
        datasets.value = [...cached.items]
        datasetsPage.value = cached.page
        datasetsPerPage.value = cached.perPage
        datasetsTotal.value = cached.total
        datasetsPages.value = cached.pages
        if (fetchAllPages) {
          allDatasetsCached = true
        }
        return
      }
    }

    if (fetchDatasetsInFlight && fetchDatasetsRequestKey === requestKey)
      return fetchDatasetsInFlight

    fetchDatasetsRequestKey = requestKey

    fetchDatasetsInFlight = (async () => {
      const requestVersion = ++fetchDatasetsVersion
      loading.value = true
      try {
        const requestedPage = Math.max(1, Number(options.page || 1))
        const requestedPerPage = Math.max(
          1,
          Math.min(200, Number(options.perPage || (fetchAllPages ? 200 : 10))),
        )
        const requestedSearch = String(options.search || '').trim()
        const requestedSort = String(options.sort || 'uploaded_at')
        const requestedOrder = options.order === 'asc' ? 'asc' : 'desc'

        if (fetchAllPages) {
          let page = 1
          let totalPages = 1
          let total = 0
          const allItems = []

          do {
            const { data } = await api.get('/api/data/datasets', {
              params: {
                page,
                per_page: requestedPerPage,
                sync: withSync && page === 1,
                search: requestedSearch || undefined,
                sort: requestedSort,
                order: requestedOrder,
              },
            })
            const items = Array.isArray(data) ? data : data.items || []
            allItems.push(...items)
            totalPages = Array.isArray(data) ? 1 : Number(data.pages || 1)
            total = Array.isArray(data) ? allItems.length : Number(data.total || allItems.length)
            page += 1
          } while (page <= totalPages)

          if (requestVersion === fetchDatasetsVersion) {
            datasets.value = allItems
            datasetsPage.value = requestedPage
            datasetsPerPage.value = requestedPerPage
            datasetsTotal.value = total
            datasetsPages.value = totalPages
            allDatasetsCached = true
            datasetPageCache.set(requestKey, {
              items: [...allItems],
              page: requestedPage,
              perPage: requestedPerPage,
              total,
              pages: totalPages,
            })
          }
          return
        }

        const { data } = await api.get('/api/data/datasets', {
          params: {
            page: requestedPage,
            per_page: requestedPerPage,
            sync: withSync,
            search: requestedSearch || undefined,
            sort: requestedSort,
            order: requestedOrder,
          },
        })
        const items = Array.isArray(data) ? data : data.items || []
        const total = Array.isArray(data) ? items.length : Number(data.total || items.length)
        const pages = Array.isArray(data) ? 1 : Number(data.pages || 1)

        if (requestVersion === fetchDatasetsVersion) {
          datasets.value = items
          datasetsPage.value = requestedPage
          datasetsPerPage.value = requestedPerPage
          datasetsTotal.value = total
          datasetsPages.value = pages
          datasetPageCache.set(requestKey, {
            items: [...items],
            page: requestedPage,
            perPage: requestedPerPage,
            total,
            pages,
          })
        }
      } finally {
        if (requestVersion === fetchDatasetsVersion) {
          loading.value = false
        }
        if (fetchDatasetsInFlight) {
          fetchDatasetsInFlight = null
          fetchDatasetsRequestKey = ''
        }
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
    allDatasetsCached = false
    clearDatasetPageCache()
    invalidateSharedDatasetMetadata()
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

      await Promise.all([
        fetchDatasets(),
        fetchTrainingDataset(),
        fetchQualitySummary(),
        fetchUploadCapacity(),
      ])
      uploadProgress.value = 100
      return aggregated
    } finally {
      uploading.value = false
      uploadProgress.value = 0
    }
  }

  async function deleteDataset(id: number) {
    allDatasetsCached = false
    clearDatasetPageCache()
    invalidateSharedDatasetMetadata()
    await api.delete(`/api/data/datasets/${id}`)
    datasets.value = datasets.value.filter((d) => d.id !== id)
    datasetsTotal.value = Math.max(0, Number(datasetsTotal.value || 0) - 1)
    datasetsPages.value = datasetsPerPage.value
      ? Math.ceil(datasetsTotal.value / datasetsPerPage.value)
      : 0
  }

  async function deleteAllDatasets() {
    allDatasetsCached = false
    clearDatasetPageCache()
    invalidateSharedDatasetMetadata()
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

  async function fetchTrainingDataset(force = false) {
    if (!force && isSharedDataCacheFresh(trainingDatasetFetchedAt)) {
      return trainingDataset.value
    }
    if (fetchTrainingDatasetInFlight) return fetchTrainingDatasetInFlight
    fetchTrainingDatasetInFlight = (async () => {
      try {
        const { data } = await api.get('/api/data/training-dataset')
        trainingDataset.value = data
        trainingDatasetFetchedAt = Date.now()
        return data
      } catch (error) {
        trainingDatasetFetchedAt = 0
        throw error
      }
    })()
    try {
      return await fetchTrainingDatasetInFlight
    } finally {
      fetchTrainingDatasetInFlight = null
    }
  }

  async function fetchQualitySummary(force = false) {
    if (!force && isSharedDataCacheFresh(qualitySummaryFetchedAt)) {
      return qualitySummary.value
    }
    if (fetchQualitySummaryInFlight) return fetchQualitySummaryInFlight
    fetchQualitySummaryInFlight = (async () => {
      try {
        const { data } = await api.get('/api/data/quality-summary')
        qualitySummary.value = data
        qualitySummaryFetchedAt = Date.now()
        return data
      } catch (error) {
        qualitySummaryFetchedAt = 0
        throw error
      }
    })()
    try {
      return await fetchQualitySummaryInFlight
    } finally {
      fetchQualitySummaryInFlight = null
    }
  }

  async function fetchUploadCapacity(force = false) {
    if (!force && isSharedDataCacheFresh(uploadCapacityFetchedAt)) {
      return uploadCapacity.value
    }
    if (fetchUploadCapacityInFlight) return fetchUploadCapacityInFlight

    fetchUploadCapacityInFlight = (async () => {
      try {
        const { data } = await api.get('/api/data/upload-capacity')
        uploadCapacity.value = data
        uploadCapacityFetchedAt = Date.now()
        return data
      } catch (error) {
        uploadCapacityFetchedAt = 0
        throw error
      } finally {
        fetchUploadCapacityInFlight = null
      }
    })()

    return fetchUploadCapacityInFlight
  }

  async function rescanDatasets() {
    allDatasetsCached = false
    clearDatasetPageCache()
    invalidateSharedDatasetMetadata()
    const { data } = await api.post('/api/data/datasets/rescan', null, { timeout: 0 })
    await Promise.all([
      fetchDatasets(false, false),
      fetchTrainingDataset(),
      fetchQualitySummary(),
      fetchUploadCapacity(),
    ])
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
