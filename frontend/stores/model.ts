interface ModelInfo {
  version: string
  trained_at: string
  rows: number
  mae: number
  rmse: number
  r2: number
  mape: number
  median_ae: number
  duration_sec: number
  model_type: string
  per_type_count: number
  source_csv_path: string
  combined_metrics?: Record<string, unknown>
}

interface TrainingStatus {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'stale'
  stage: string | null
  progress: number
  current_model: string | null
  current_model_index: number | null
  total_models: number | null
  fitted_trees: number | null
  total_trees: number | null
  trees_per_sec: number | null
  elapsed_sec: number | null
  eta_sec: number | null
  duration_sec: number | null
  error: string | null
  created_at: string
  updated_at: string
}

interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  pages: number
}

export const useModelStore = defineStore('model', () => {
  const info = ref<ModelInfo | null>(null)
  const diagnostics = ref<Record<string, unknown> | null>(null)
  const importance = ref<unknown[]>([])
  const training = ref(false)
  const trainingStatus = ref<TrainingStatus | null>(null)
  const jobHistory = ref<TrainingStatus[]>([])
  const modelRuns = ref<unknown[]>([])
  const jobsLoading = ref(false)
  const runsLoading = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const api = useApi()
  const { t } = useI18n()

  async function fetchInfo(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get<ModelInfo>('/api/model/info')
      info.value = data
    } catch (e) {
      const err = e as { response?: { status?: number } }
      if (err.response?.status !== 404) error.value = getApiErrorMessage(e as Error, t)
      info.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchImportance(): Promise<void> {
    try {
      const { data } = await api.get<unknown[]>('/api/model/importance')
      importance.value = data
    } catch {
      importance.value = []
    }
  }

  async function fetchDiagnostics(): Promise<void> {
    try {
      const { data } = await api.get<Record<string, unknown>>('/api/model/diagnostics')
      diagnostics.value = data
    } catch {
      diagnostics.value = null
    }
  }

  async function startTraining(csvPath: string): Promise<TrainingStatus> {
    training.value = true
    error.value = null
    try {
      const { data } = await api.post<TrainingStatus>('/api/train/start', { csv_path: csvPath })
      trainingStatus.value = data
      return data
    } catch (e) {
      const err = e as {
        response?: { status?: number; data?: TrainingStatus & { job_id?: string } }
      }
      const activeJob =
        err.response?.status === 409 && err.response?.data?.job_id
          ? ({
              ...err.response.data,
              status: (err.response.data.status || 'queued') as TrainingStatus['status'],
              stage: err.response.data.stage || null,
              progress: err.response.data.progress || 0,
              error: err.response.data.error || null,
            } as TrainingStatus)
          : null

      if (activeJob) {
        training.value = activeJob.status === 'queued' || activeJob.status === 'running'
        trainingStatus.value = activeJob
        return activeJob
      }

      training.value = false
      error.value = getApiErrorMessage(e as Error, t)
      throw e
    }
  }

  async function fetchActiveTraining(): Promise<TrainingStatus | null> {
    try {
      const { data } = await api.get<TrainingStatus>('/api/train/active')
      trainingStatus.value = data
      training.value = data.status === 'queued' || data.status === 'running'
      return data
    } catch (e) {
      const err = e as { response?: { status?: number } }
      if (err.response?.status === 404) {
        training.value = false
        return null
      }
      error.value = getApiErrorMessage(e as Error, t)
      return null
    }
  }

  async function pollStatus(jobId: string): Promise<TrainingStatus | null> {
    try {
      const { data } = await api.get<TrainingStatus>(`/api/train/status/${jobId}`)
      trainingStatus.value = data
      training.value = data.status === 'queued' || data.status === 'running'
      return data
    } catch (e) {
      training.value = false
      error.value = getApiErrorMessage(e as Error, t)
      return null
    }
  }

  async function fetchJobs(
    params: Record<string, unknown> = {},
  ): Promise<PaginatedResult<TrainingStatus> | null> {
    jobsLoading.value = true
    try {
      const { data } = await api.get<PaginatedResult<TrainingStatus>>('/api/train/jobs', {
        params: { per_page: 8, ...params },
      })
      jobHistory.value = data.items || []
      return data
    } catch (e) {
      jobHistory.value = []
      error.value = getApiErrorMessage(e as Error, t)
      return null
    } finally {
      jobsLoading.value = false
    }
  }

  async function fetchRuns(
    params: Record<string, unknown> = {},
  ): Promise<PaginatedResult<unknown> | null> {
    runsLoading.value = true
    try {
      const { data } = await api.get<PaginatedResult<unknown>>('/api/model/runs', {
        params: { per_page: 8, ...params },
      })
      modelRuns.value = data.items || []
      return data
    } catch (e) {
      modelRuns.value = []
      error.value = getApiErrorMessage(e as Error, t)
      return null
    } finally {
      runsLoading.value = false
    }
  }

  function reset(): void {
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
