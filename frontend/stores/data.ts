interface DatasetFile {
  id: number
  original_name: string
  row_count: number | null
  source_type: string
  uploaded_at: string
}

interface QualitySummary {
  covered_municipalities: number
  total_reference: number
  coverage_ratio: number
  unresolved_rows: number
  unresolved_municipalities: string[]
  alias_collisions: Array<{
    canonical: string
    variants: string[]
  }>
}

interface TrainingDataset {
  path: string
  rows: number
  modified_at: string
}

export const useDataStore = defineStore('data', () => {
  const datasets = ref<DatasetFile[]>([])
  const trainingDataset = ref<TrainingDataset | null>(null)
  const qualitySummary = ref<QualitySummary | null>(null)
  const loading = ref(false)
  const uploading = ref(false)

  const api = useApi()

  async function fetchDatasets(): Promise<void> {
    loading.value = true
    try {
      const perPage = 200
      let page = 1
      let totalPages = 1
      const allItems: DatasetFile[] = []

      do {
        const { data } = await api.get<DatasetFile[] | { items: DatasetFile[]; pages: number }>(
          '/api/data/datasets',
          {
            params: { page, per_page: perPage },
          },
        )
        const items = Array.isArray(data) ? data : (data as { items: DatasetFile[] }).items || []
        allItems.push(...items)
        totalPages = Array.isArray(data) ? 1 : (data as { pages: number }).pages || 1
        page += 1
      } while (page <= totalPages)

      datasets.value = allItems
    } finally {
      loading.value = false
    }
  }

  async function uploadFiles(files: File[]): Promise<unknown> {
    uploading.value = true
    try {
      const formData = new FormData()
      for (const file of files) {
        formData.append('files', file)
      }
      const { data } = await api.post('/api/data/upload', formData)
      await fetchDatasets()
      return data
    } finally {
      uploading.value = false
    }
  }

  async function deleteDataset(id: number): Promise<void> {
    await api.delete(`/api/data/datasets/${id}`)
    datasets.value = datasets.value.filter((d) => d.id !== id)
  }

  async function deleteAllDatasets(): Promise<void> {
    const ids = datasets.value.map((d) => d.id)
    if (!ids.length) return
    await api.post('/api/data/datasets/delete-bulk', { dataset_ids: ids })
    datasets.value = []
  }

  async function fetchPreview(id: number, limit = 20): Promise<unknown> {
    const { data } = await api.get(`/api/data/preview/${id}`, { params: { limit } })
    return data
  }

  async function fetchTrainingDataset(): Promise<TrainingDataset> {
    const { data } = await api.get<TrainingDataset>('/api/data/training-dataset')
    trainingDataset.value = data
    return data
  }

  async function fetchQualitySummary(): Promise<QualitySummary> {
    const { data } = await api.get<QualitySummary>('/api/data/quality-summary')
    qualitySummary.value = data
    return data
  }

  return {
    datasets,
    trainingDataset,
    qualitySummary,
    loading,
    uploading,
    fetchDatasets,
    uploadFiles,
    deleteDataset,
    deleteAllDatasets,
    fetchPreview,
    fetchTrainingDataset,
    fetchQualitySummary,
  }
})
