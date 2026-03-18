<script setup lang="ts">
  import { Bar } from 'vue-chartjs'
  import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
  import { useIntervalFn } from '@vueuse/core'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

  definePageMeta({ middleware: ['admin'] })

  // ─── Types ──────────────────────────────────────────────────────────────────
  interface GlobalMetrics {
    mae: number
    rmse: number
    r2: number
    mape: number
    median_ae: number
  }

  interface PerTypeMetric {
    mae: number
    rmse: number
    r2: number
    mape: number
    n_train: number
  }

  interface ModelInfoExt {
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
    global_metrics?: GlobalMetrics
    per_type_metrics?: Record<string, PerTypeMetric>
  }

  interface TrainingStatusExt {
    job_id: string
    status: 'queued' | 'running' | 'completed' | 'failed' | 'stale'
    stage: string | null
    progress: number
    current_model: string | null
    current_model_index: number | null
    total_models: number | null
    current_model_progress?: number | null
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

  interface ModelRun {
    created_at: string
    source_csv_path: string
    rows: number
    mae: number
    rmse: number
    mape: number
    duration_sec: number
    per_type_count: number
  }

  interface SourceOption {
    label: string
    value: string
    dataset?: any
  }

  interface MetricCardItem {
    label: string
    value: string
    meta?: string
  }

  interface StoryCardItem {
    label: string
    value: string
    meta: string
    tone: 'success' | 'warning' | 'default'
  }

  interface PerTypeRow {
    propertyType: string
    mae: number
    rmse: number
    r2: number
    mape: number
    n_train: number
  }

  interface FeatureItem {
    label: string
    importance: number
    share: number
  }

  // ─── Stores & composables ───────────────────────────────────────────────────
  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const modelStore = useModelStore()

  // ─── Local state ────────────────────────────────────────────────────────────
  const selectedCsv = ref('')
  const pollJobId = ref<string | null>(null)
  const themeObserver = ref<MutationObserver | null>(null)

  // ─── Cast helpers (store types are narrower than API response) ───────────────
  const modelInfo = computed(() => modelStore.info as ModelInfoExt | null)
  const activeStatus = computed(() => modelStore.trainingStatus as TrainingStatusExt | null)

  // ─── Core computed ──────────────────────────────────────────────────────────
  const isAdmin = computed(() => auth.user?.role === 'admin')
  const trainingDataset = computed(() => dataStore.trainingDataset as any)
  const recentJobs = computed(() => (modelStore.jobHistory as TrainingStatusExt[]).slice(0, 6))
  const recentRuns = computed(() => (modelStore.modelRuns as ModelRun[]).slice(0, 6))
  const latestRun = computed<ModelRun | null>(() => recentRuns.value[0] ?? null)
  const trainingLocked = computed(() => modelStore.training)

  const uploadOptions = computed<SourceOption[]>(() =>
    (Array.isArray(dataStore.datasets) ? dataStore.datasets : [])
      .filter((dataset: any) => dataset.relative_path !== trainingDataset.value?.relative_path)
      .map((dataset: any) => ({
        label: `${dataset.original_name} (${fmt(dataset.row_count)} ${t('data.rows')})`,
        value: dataset.relative_path,
        dataset,
      })),
  )

  const sourceOptions = computed<SourceOption[]>(() => {
    const options: SourceOption[] = []
    if (trainingDataset.value?.exists) {
      options.push({
        label: `${t('model.preparedDatasetLabel')} (${fmt(trainingDataset.value.rows)} ${t('data.rows')})`,
        value: trainingDataset.value.relative_path,
      })
    }
    return [...options, ...uploadOptions.value]
  })

  const selectedSourceMeta = computed<any>(() => {
    if (!selectedCsv.value) return null
    if (
      trainingDataset.value?.exists &&
      selectedCsv.value === trainingDataset.value.relative_path
    ) {
      return {
        name: t('model.preparedDatasetLabel'),
        rows: trainingDataset.value.rows,
        updated_at: trainingDataset.value.updated_at,
        relative_path: trainingDataset.value.relative_path,
      }
    }
    return uploadOptions.value.find((o) => o.value === selectedCsv.value)?.dataset ?? null
  })

  const selectedSourcePath = computed(
    () =>
      selectedSourceMeta.value?.relative_path ||
      trainingDataset.value?.relative_path ||
      modelInfo.value?.source_csv_path ||
      '',
  )

  const activeModelLabel = computed(() => {
    const key = activeStatus.value?.current_model
    if (!key) return t('common.noData')
    if (key === 'global') return t('model.globalModel')
    if (key === 'done') return t('model.completedStage')
    return formatType(key)
  })

  const trainingStageLabel = computed(() => {
    const stage = activeStatus.value?.stage
    return stage ? t(`model.stages.${stage}`) : t('common.loading')
  })

  // ─── Card data ──────────────────────────────────────────────────────────────
  const metricsCards = computed<MetricCardItem[]>(() => {
    const metrics = modelInfo.value?.global_metrics
    if (!metrics) return []
    return [
      { label: 'MAE', value: fmtCurrency(metrics.mae) },
      { label: 'RMSE', value: fmtCurrency(metrics.rmse) },
      { label: 'R\u00B2', value: formatScore(metrics.r2) },
      { label: 'MAPE', value: fmtPercent(metrics.mape) },
      { label: t('model.medianError'), value: fmtCurrency(metrics.median_ae) },
    ]
  })

  const runCards = computed<MetricCardItem[]>(() => {
    if (!activeStatus.value) return []
    return [
      {
        label: t('model.trainingProgress'),
        value: `${activeStatus.value.progress || 0}%`,
        meta: trainingStageLabel.value,
      },
      {
        label: t('model.currentModel'),
        value: activeModelLabel.value,
        meta:
          activeStatus.value.current_model_index && activeStatus.value.total_models
            ? `${activeStatus.value.current_model_index}/${activeStatus.value.total_models}`
            : '',
      },
      {
        label: t('model.currentModelProgress'),
        value: `${activeStatus.value.current_model_progress || 0}%`,
        meta:
          activeStatus.value.fitted_trees != null && activeStatus.value.total_trees != null
            ? `${fmt(activeStatus.value.fitted_trees)}/${fmt(activeStatus.value.total_trees)}`
            : '',
      },
      {
        label: t('model.elapsed'),
        value: formatDuration(activeStatus.value.elapsed_sec),
        meta:
          activeStatus.value.eta_sec != null
            ? `${t('model.eta')}: ${formatDuration(activeStatus.value.eta_sec)}`
            : '',
      },
    ]
  })

  const heroStoryCards = computed<StoryCardItem[]>(() => [
    {
      label: t('model.currentModel'),
      value: modelInfo.value ? t('model.modelReady') : t('model.modelMissing'),
      meta: modelInfo.value
        ? `${formatDate(modelInfo.value.trained_at)} \u00B7 ${fmt(modelInfo.value.rows)} ${t('data.rows')}`
        : t('model.noModel'),
      tone: modelInfo.value ? 'success' : 'warning',
    },
    {
      label: t('model.currentSource'),
      value: modelInfo.value?.source_csv_path || selectedSourcePath.value || t('common.noData'),
      meta: selectedSourceMeta.value
        ? `${fmt(selectedSourceMeta.value.row_count || selectedSourceMeta.value.rows || 0)} ${t('data.rows')} \u00B7 ${formatDate(selectedSourceMeta.value.uploaded_at || selectedSourceMeta.value.updated_at)}`
        : t('model.selectSourceHint'),
      tone: selectedSourcePath.value ? 'default' : 'warning',
    },
    {
      label: t('model.completedRuns'),
      value: fmt(modelStore.modelRuns.length),
      meta: latestRun.value
        ? `${fmtCurrency(latestRun.value.mae)} MAE \u00B7 ${formatDate(latestRun.value.created_at)}`
        : t('model.noCompletedRuns'),
      tone: latestRun.value ? 'success' : 'default',
    },
  ])

  const launchChecklist = computed<StoryCardItem[]>(() => [
    {
      label: t('model.preparedDataset'),
      value: trainingDataset.value?.exists
        ? t('model.preparedDatasetReady')
        : t('model.preparedDatasetMissing'),
      meta: trainingDataset.value?.exists
        ? trainingDataset.value.relative_path
        : t('model.prepareDataFirst'),
      tone: trainingDataset.value?.exists ? 'success' : 'warning',
    },
    {
      label: t('model.trainingStatus'),
      value: activeStatus.value
        ? jobStatusLabel(activeStatus.value.status)
        : modelInfo.value
          ? t('model.modelReady')
          : t('model.modelMissing'),
      meta: activeStatus.value ? trainingStageLabel.value : t('model.trainingCtaHint'),
      tone: activeStatus.value ? 'warning' : modelInfo.value ? 'success' : 'default',
    },
    {
      label: t('model.completedRuns'),
      value: fmt(recentRuns.value.length),
      meta: latestRun.value
        ? `${fmtCurrency(latestRun.value.rmse)} RMSE \u00B7 ${formatDuration(latestRun.value.duration_sec)}`
        : t('model.noCompletedRuns'),
      tone: latestRun.value ? 'success' : 'default',
    },
  ])

  // ─── Per-type metrics table ─────────────────────────────────────────────────
  const perTypeRows = computed<PerTypeRow[]>(() => {
    const ptm = modelInfo.value?.per_type_metrics
    if (!ptm) return []
    return Object.entries(ptm).map(([propertyType, metrics]) => ({
      propertyType,
      ...metrics,
    }))
  })

  const perTypeColumns = computed(() => [
    { accessorKey: 'propertyType', header: t('model.propertyType'), enableSorting: false },
    { accessorKey: 'mae', header: 'MAE', enableSorting: false },
    { accessorKey: 'rmse', header: 'RMSE', enableSorting: false },
    { accessorKey: 'r2', header: 'R\u00B2', enableSorting: false },
    { accessorKey: 'mape', header: 'MAPE', enableSorting: false },
    { accessorKey: 'n_train', header: 'N', enableSorting: false },
  ])

  // ─── Job history table ──────────────────────────────────────────────────────
  const jobColumns = computed(() => [
    { accessorKey: 'created_at', header: t('predict.date'), enableSorting: false },
    { accessorKey: 'status', header: t('model.trainingStatus'), enableSorting: false },
    { accessorKey: 'stage', header: t('model.trainingStage'), enableSorting: false },
    { accessorKey: 'progress', header: t('model.trainingProgress'), enableSorting: false },
    { accessorKey: 'current_model', header: t('model.currentModel'), enableSorting: false },
    { accessorKey: 'elapsed_sec', header: t('model.elapsed'), enableSorting: false },
  ])

  // ─── Completed runs table ───────────────────────────────────────────────────
  const runColumns = computed(() => [
    { accessorKey: 'created_at', header: t('predict.date'), enableSorting: false },
    { accessorKey: 'source_csv_path', header: t('model.currentSource'), enableSorting: false },
    { accessorKey: 'rows', header: t('data.rows'), enableSorting: false },
    { accessorKey: 'mae', header: 'MAE', enableSorting: false },
    { accessorKey: 'rmse', header: 'RMSE', enableSorting: false },
    { accessorKey: 'mape', header: 'MAPE', enableSorting: false },
    { accessorKey: 'duration_sec', header: t('diag.duration'), enableSorting: false },
    { accessorKey: 'per_type_count', header: t('model.perTypeModels'), enableSorting: false },
  ])

  // ─── Feature importance ─────────────────────────────────────────────────────
  const featureHighlights = computed<FeatureItem[]>(() => {
    const items = (modelStore.importance as any[]).slice(0, 5)
    const maxImportance = items[0]?.importance || 1
    return items.map((item) => ({
      ...item,
      share: maxImportance ? (item.importance / maxImportance) * 100 : 0,
    }))
  })

  const chartPalette = ref({
    primary: '#3b82f6',
    muted: '#94a3b8',
    grid: 'rgba(148, 163, 184, 0.18)',
  })

  const importanceChart = computed(() => {
    const items = (modelStore.importance as any[]).slice(0, 15)
    return {
      labels: items.map((item) => item.label),
      datasets: [
        {
          label: t('model.importance'),
          data: items.map((item) => item.importance),
          backgroundColor: chartPalette.value.primary,
          borderRadius: 12,
          maxBarThickness: 20,
        },
      ],
    }
  })

  const importanceOptions = computed(() => ({
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        beginAtZero: true,
        ticks: { color: chartPalette.value.muted },
        grid: { color: chartPalette.value.grid },
      },
      y: {
        ticks: { color: chartPalette.value.muted },
        grid: { display: false },
      },
    },
  }))

  // ─── Formatting helpers ─────────────────────────────────────────────────────
  function fmt(value: number | null | undefined, decimals = 0): string {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value: number | null | undefined): string {
    return formatCurrency(value)
  }

  function fmtPercent(value: number | null | undefined): string {
    return formatPercent(value, { scale: 0.01, minimumFractionDigits: 1 })
  }

  function formatScore(value: number | null | undefined): string {
    return formatNumber(value, { minimumFractionDigits: 4, maximumFractionDigits: 4 })
  }

  function formatType(value: string | null | undefined): string {
    return getPropertyTypeLabel(value ?? '', t)
  }

  function formatDate(value: string | null | undefined): string {
    if (!value) return t('common.noData')
    return formatDateTime(value)
  }

  function formatDuration(value: number | null | undefined): string {
    if (value == null || Number.isNaN(Number(value))) return '\u2014'
    return `${formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }

  // ─── Status helpers ─────────────────────────────────────────────────────────
  function jobBadgeColor(
    status: string | null | undefined,
  ): 'success' | 'error' | 'warning' | 'neutral' {
    if (status === 'completed') return 'success'
    if (status === 'failed') return 'error'
    if (status === 'running') return 'warning'
    return 'neutral'
  }

  function jobStatusLabel(status: string | null | undefined): string {
    return status ? t(`model.status.${status}`) : '\u2014'
  }

  function stageLabel(stage: string | null | undefined): string {
    return stage ? t(`model.stages.${stage}`) : '\u2014'
  }

  function isTerminalStatus(status: string | null | undefined): boolean {
    return status === 'completed' || status === 'failed'
  }

  // ─── Chart theme sync ───────────────────────────────────────────────────────
  function readCssColor(variable: string, fallback: string): string {
    if (typeof window === 'undefined') return fallback
    const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim()
    return value || fallback
  }

  function syncChartPalette(): void {
    chartPalette.value = {
      primary: readCssColor('--ui-primary', chartPalette.value.primary),
      muted: readCssColor('--ui-text-muted', chartPalette.value.muted),
      grid: readCssColor('--ui-border', chartPalette.value.grid),
    }
  }

  // ─── Polling via VueUse ─────────────────────────────────────────────────────
  const {
    pause: stopPolling,
    resume: startPolling,
    isActive: isPolling,
  } = useIntervalFn(
    async () => {
      if (!pollJobId.value) {
        stopPolling()
        return
      }
      const status = await modelStore.pollStatus(pollJobId.value)
      if (!status || isTerminalStatus(status.status)) {
        pollJobId.value = null
        stopPolling()
        await refreshModelArtifacts()
      }
    },
    1800,
    { immediate: false },
  )

  function beginPolling(jobId: string): void {
    pollJobId.value = jobId
    startPolling()
  }

  // ─── Actions ────────────────────────────────────────────────────────────────
  async function train(): Promise<void> {
    if (!selectedCsv.value || trainingLocked.value) return
    const result = await modelStore.startTraining(selectedCsv.value)
    await Promise.all([modelStore.fetchJobs(), modelStore.fetchRuns()])
    if (result?.job_id) {
      beginPolling(result.job_id)
    }
  }

  async function refreshModelArtifacts(): Promise<void> {
    await Promise.all([
      modelStore.fetchInfo(),
      modelStore.fetchImportance(),
      modelStore.fetchDiagnostics(),
      modelStore.fetchJobs(),
      modelStore.fetchRuns(),
      dataStore.fetchTrainingDataset(),
    ])
  }

  async function syncExistingTraining(): Promise<void> {
    const activeJob = await modelStore.fetchActiveTraining()
    if (activeJob?.job_id && !isTerminalStatus(activeJob.status)) {
      beginPolling(activeJob.job_id)
    }
  }

  // ─── Watchers ───────────────────────────────────────────────────────────────
  watch(
    trainingDataset,
    (dataset) => {
      if (dataset?.exists && !selectedCsv.value) {
        selectedCsv.value = dataset.relative_path
      }
    },
    { immediate: true },
  )

  // ─── Lifecycle ──────────────────────────────────────────────────────────────
  await useAsyncData('admin-model', async () => {
    await Promise.all([
      modelStore.fetchInfo(),
      modelStore.fetchImportance(),
      modelStore.fetchDiagnostics(),
      modelStore.fetchJobs(),
      modelStore.fetchRuns(),
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
    ])
    await syncExistingTraining()
  })

  onMounted(() => {
    syncChartPalette()
    if (typeof window !== 'undefined') {
      themeObserver.value = new MutationObserver(() => {
        syncChartPalette()
      })
      themeObserver.value.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['class', 'style'],
      })
    }
  })

  onUnmounted(() => {
    if (isPolling.value) stopPolling()
    pollJobId.value = null
    themeObserver.value?.disconnect()
    themeObserver.value = null
  })
</script>

<template>
  <div class="model-page">
    <!-- ════════════════════ HERO ════════════════════ -->
    <section v-if="isAdmin" class="card model-hero">
      <div class="section-head">
        <div>
          <p class="eyebrow">{{ t('model.trainModel') }}</p>
          <h1>{{ t('model.trainingTitle') }}</h1>
          <p class="muted">{{ t('model.trainingBody') }}</p>
        </div>
        <div class="hero-actions">
          <NuxtLink v-if="!trainingDataset?.exists" to="/admin/priprava">
            <UButton variant="outline" color="neutral" :label="t('model.goToPrepare')" />
          </NuxtLink>
        </div>
      </div>

      <div class="hero-story-grid">
        <article
          v-for="card in heroStoryCards"
          :key="card.label"
          class="story-card"
          :class="`tone-${card.tone}`"
        >
          <span class="eyebrow">{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.meta }}</p>
        </article>
      </div>

      <div class="hero-shell">
        <div class="hero-grid">
          <!-- Prepared dataset -->
          <article class="metric-card">
            <span class="eyebrow">{{ t('model.preparedDataset') }}</span>
            <strong>{{
              trainingDataset?.exists
                ? t('model.preparedDatasetReady')
                : t('model.preparedDatasetMissing')
            }}</strong>
            <p class="muted">
              {{
                trainingDataset?.exists
                  ? `${fmt(trainingDataset.rows)} ${t('data.rows')} \u00B7 ${formatDate(trainingDataset.updated_at)}`
                  : t('model.prepareDataFirst')
              }}
            </p>
            <span
              class="metric-tone-bar"
              :class="trainingDataset?.exists ? 'tone-success' : 'tone-default'"
            />
          </article>

          <!-- Current model -->
          <article class="metric-card">
            <span class="eyebrow">{{ t('model.currentModel') }}</span>
            <strong>{{ modelInfo ? t('model.modelReady') : t('model.modelMissing') }}</strong>
            <p class="muted">
              {{
                modelInfo
                  ? `${formatDate(modelInfo.trained_at)} \u00B7 ${fmt(modelInfo.rows)} ${t('data.rows')}`
                  : t('model.noModel')
              }}
            </p>
            <span class="metric-tone-bar" :class="modelInfo ? 'tone-success' : 'tone-warning'" />
          </article>
        </div>

        <!-- Spotlight -->
        <article class="hero-spotlight">
          <div class="spotlight-head">
            <span class="eyebrow">
              {{ activeStatus ? t('model.trainingStatus') : t('model.currentSource') }}
            </span>
            <UBadge
              :color="
                activeStatus
                  ? jobBadgeColor(activeStatus.status)
                  : modelInfo
                    ? 'success'
                    : 'neutral'
              "
              :label="
                activeStatus
                  ? jobStatusLabel(activeStatus.status)
                  : modelInfo
                    ? t('model.modelReady')
                    : t('model.modelMissing')
              "
              variant="soft"
            />
          </div>

          <h2>
            {{
              activeStatus
                ? trainingStageLabel
                : selectedSourceMeta?.original_name ||
                  selectedSourceMeta?.name ||
                  modelInfo?.source_csv_path ||
                  t('common.noData')
            }}
          </h2>
          <p>
            {{
              activeStatus
                ? `${activeStatus.progress || 0}% \u00B7 ${activeModelLabel}`
                : selectedSourcePath || t('model.selectSourceHint')
            }}
          </p>

          <div class="spotlight-meta">
            <span>
              {{
                activeStatus
                  ? `${t('model.elapsed')}: ${formatDuration(activeStatus.elapsed_sec)}`
                  : `${fmt(selectedSourceMeta?.row_count || selectedSourceMeta?.rows || modelInfo?.rows || 0)} ${t('data.rows')}`
              }}
            </span>
            <span>
              {{
                activeStatus?.eta_sec != null
                  ? `${t('model.eta')}: ${formatDuration(activeStatus.eta_sec)}`
                  : formatDate(
                      selectedSourceMeta?.uploaded_at ||
                        selectedSourceMeta?.updated_at ||
                        modelInfo?.trained_at,
                    )
              }}
            </span>
          </div>
        </article>
      </div>
    </section>

    <!-- ════════════════════ TRAINING WORKBENCH ════════════════════ -->
    <section v-if="isAdmin" class="card training-workbench">
      <div class="section-head">
        <div>
          <p class="eyebrow subtle">{{ t('model.selectDataset') }}</p>
          <h2>{{ t('model.trainingWorkbench') }}</h2>
          <p class="muted">
            {{ trainingLocked ? t('model.trainingLockedHint') : t('model.selectSourceHint') }}
          </p>
        </div>
      </div>

      <div class="source-shell">
        <div class="source-panel">
          <label class="field">
            <span>{{ t('model.selectDataset') }}</span>
            <USelectMenu
              v-model="selectedCsv"
              :items="sourceOptions"
              value-key="value"
              :placeholder="t('model.selectDataset')"
              :disabled="trainingLocked"
              class="w-full"
            />
          </label>

          <div v-if="selectedSourceMeta" class="selected-source-card">
            <span class="eyebrow">{{ t('model.selectedSource') }}</span>
            <strong>{{ selectedSourceMeta.original_name || selectedSourceMeta.name }}</strong>
            <p>{{ selectedSourcePath }}</p>
            <p class="muted">
              {{ fmt(selectedSourceMeta.row_count || selectedSourceMeta.rows || 0) }}
              {{ t('data.rows') }} &middot;
              {{ formatDate(selectedSourceMeta.uploaded_at || selectedSourceMeta.updated_at) }}
            </p>
          </div>
        </div>

        <div class="action-panel">
          <UButton
            :label="trainingLocked ? t('model.training') : t('model.trainButton')"
            icon="i-lucide-play"
            class="train-btn"
            :disabled="!selectedCsv || trainingLocked"
            :loading="trainingLocked"
            @click="train"
          />
          <p class="muted">
            {{ trainingLocked ? t('model.trainingLockedHint') : t('model.trainingCtaHint') }}
          </p>
        </div>
      </div>

      <div class="launch-rail">
        <article
          v-for="note in launchChecklist"
          :key="note.label"
          class="launch-card"
          :class="`tone-${note.tone}`"
        >
          <span class="eyebrow">{{ note.label }}</span>
          <strong>{{ note.value }}</strong>
          <p>{{ note.meta }}</p>
        </article>
      </div>

      <!-- Live progress -->
      <div v-if="activeStatus" class="live-progress">
        <div class="live-progress-head">
          <div>
            <span class="eyebrow">{{ t('model.trainingStatus') }}</span>
            <h2>{{ trainingStageLabel }}</h2>
          </div>
          <UBadge
            :color="jobBadgeColor(activeStatus.status)"
            :label="jobStatusLabel(activeStatus.status)"
            variant="soft"
          />
        </div>

        <UProgress :value="activeStatus.progress || 0" />

        <div class="hero-grid compact">
          <article v-for="card in runCards" :key="card.label" class="metric-card">
            <span class="eyebrow">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <p v-if="card.meta" class="muted">{{ card.meta }}</p>
          </article>
        </div>

        <UAlert
          v-if="activeStatus.error"
          :description="activeStatus.error"
          color="error"
          variant="soft"
          icon="i-lucide-alert-circle"
        />
      </div>

      <UAlert
        v-if="modelStore.error"
        :description="modelStore.error"
        color="error"
        variant="soft"
        icon="i-lucide-alert-circle"
      />
    </section>

    <!-- ════════════════════ MODEL SNAPSHOT ════════════════════ -->
    <section v-if="modelInfo" class="card">
      <div class="section-head">
        <div>
          <p class="eyebrow subtle">{{ t('model.currentModel') }}</p>
          <h2>{{ t('model.modelSnapshot') }}</h2>
          <p class="muted">
            {{ t('model.trainedAt') }}: {{ formatDate(modelInfo.trained_at) }} &middot;
            {{ fmt(modelInfo.rows) }} {{ t('data.rows') }} &middot;
            {{ formatDuration(modelInfo.duration_sec) }}
          </p>
        </div>
        <span v-if="modelInfo.source_csv_path" class="model-source-pill">
          {{ t('model.currentSource') }}: {{ modelInfo.source_csv_path }}
        </span>
      </div>

      <div class="snapshot-shell">
        <div class="hero-grid compact">
          <article v-for="card in metricsCards" :key="card.label" class="metric-card">
            <span class="eyebrow">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </article>
        </div>

        <article class="snapshot-spotlight">
          <span class="eyebrow">{{ t('model.completedRuns') }}</span>
          <h2>{{ latestRun ? formatDate(latestRun.created_at) : t('model.noCompletedRuns') }}</h2>
          <p>
            {{
              latestRun
                ? `${latestRun.source_csv_path} \u00B7 ${fmt(latestRun.rows)} ${t('data.rows')}`
                : t('model.completedRunsHint')
            }}
          </p>

          <div class="snapshot-meta">
            <span>MAE &middot; {{ latestRun ? fmtCurrency(latestRun.mae) : '\u2014' }}</span>
            <span>RMSE &middot; {{ latestRun ? fmtCurrency(latestRun.rmse) : '\u2014' }}</span>
            <span>MAPE &middot; {{ latestRun ? fmtPercent(latestRun.mape) : '\u2014' }}</span>
          </div>
        </article>
      </div>
    </section>

    <!-- ════════════════════ PER-TYPE METRICS ════════════════════ -->
    <section v-if="modelInfo?.per_type_metrics" class="card">
      <div class="section-head">
        <div>
          <p class="eyebrow subtle">{{ t('model.perTypeMetrics') }}</p>
          <h2>{{ t('model.propertyTypeBreakdown') }}</h2>
          <p class="muted">{{ t('model.propertyTypeBreakdownHint') }}</p>
        </div>
      </div>

      <div class="table-wrap">
        <UTable :columns="perTypeColumns" :data="perTypeRows">
          <template #propertyType-cell="{ row }">
            {{ formatType(row.original.propertyType) }}
          </template>
          <template #mae-cell="{ row }">
            {{ fmtCurrency(row.original.mae) }}
          </template>
          <template #rmse-cell="{ row }">
            {{ fmtCurrency(row.original.rmse) }}
          </template>
          <template #r2-cell="{ row }">
            {{ formatScore(row.original.r2) }}
          </template>
          <template #mape-cell="{ row }">
            {{ fmtPercent(row.original.mape) }}
          </template>
          <template #n_train-cell="{ row }">
            {{ fmt(row.original.n_train) }}
          </template>
        </UTable>
      </div>
    </section>

    <!-- ════════════════════ FEATURE IMPORTANCE ════════════════════ -->
    <section v-if="modelStore.importance.length" class="card">
      <div class="section-head">
        <div>
          <p class="eyebrow subtle">{{ t('model.featureImportance') }}</p>
          <h2>{{ t('model.featureImportanceTitle') }}</h2>
          <p class="muted">{{ t('model.featureImportanceHint') }}</p>
        </div>
      </div>

      <div class="importance-shell">
        <div class="importance-chart">
          <ClientOnly>
            <Bar :data="importanceChart" :options="importanceOptions" />
          </ClientOnly>
        </div>

        <article class="focus-card">
          <span class="eyebrow">{{ t('model.featureImportance') }}</span>
          <h2>{{ featureHighlights[0]?.label || t('common.noData') }}</h2>
          <p>
            {{
              featureHighlights[0]
                ? `${fmt(featureHighlights[0].importance, 3)} \u00B7 ${t('model.importance')}`
                : t('model.featureImportanceHint')
            }}
          </p>

          <div class="feature-list">
            <div v-for="item in featureHighlights" :key="item.label" class="feature-item">
              <div class="feature-copy">
                <strong>{{ item.label }}</strong>
                <span>{{ fmt(item.importance, 3) }}</span>
              </div>
              <span class="feature-bar">
                <span :style="{ width: `${Math.max(10, item.share)}%` }" />
              </span>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- ════════════════════ HISTORY ════════════════════ -->
    <section v-if="isAdmin" class="history-grid">
      <!-- Job history -->
      <article class="card history-panel">
        <div class="section-head">
          <div>
            <p class="eyebrow subtle">{{ t('model.trainingHistory') }}</p>
            <h2>{{ t('model.jobHistoryTitle') }}</h2>
            <p class="muted">{{ t('model.trainingHistoryHint') }}</p>
          </div>
        </div>

        <div class="table-wrap">
          <UTable :columns="jobColumns" :data="recentJobs">
            <template #created_at-cell="{ row }">
              {{ formatDate(row.original.created_at) }}
            </template>
            <template #status-cell="{ row }">
              <UBadge
                :color="jobBadgeColor(row.original.status)"
                :label="jobStatusLabel(row.original.status)"
                variant="soft"
              />
            </template>
            <template #stage-cell="{ row }">
              {{ stageLabel(row.original.stage) }}
            </template>
            <template #progress-cell="{ row }"> {{ row.original.progress || 0 }}% </template>
            <template #current_model-cell="{ row }">
              {{
                row.original.current_model === 'global'
                  ? t('model.globalModel')
                  : formatType(row.original.current_model) || '\u2014'
              }}
            </template>
            <template #elapsed_sec-cell="{ row }">
              {{ formatDuration(row.original.elapsed_sec || row.original.duration_sec) }}
            </template>
          </UTable>
        </div>

        <p v-if="!modelStore.jobsLoading && !recentJobs.length" class="muted history-empty">
          {{ t('model.noTrainingHistory') }}
        </p>
      </article>

      <!-- Completed runs -->
      <article class="card history-panel">
        <div class="section-head">
          <div>
            <p class="eyebrow subtle">{{ t('model.completedRuns') }}</p>
            <h2>{{ t('model.completedRunsTitle') }}</h2>
            <p class="muted">{{ t('model.completedRunsHint') }}</p>
          </div>
        </div>

        <div class="table-wrap">
          <UTable :columns="runColumns" :data="recentRuns">
            <template #created_at-cell="{ row }">
              {{ formatDate(row.original.created_at) }}
            </template>
            <template #rows-cell="{ row }">
              {{ fmt(row.original.rows) }}
            </template>
            <template #mae-cell="{ row }">
              {{ fmtCurrency(row.original.mae) }}
            </template>
            <template #rmse-cell="{ row }">
              {{ fmtCurrency(row.original.rmse) }}
            </template>
            <template #mape-cell="{ row }">
              {{ fmtPercent(row.original.mape) }}
            </template>
            <template #duration_sec-cell="{ row }">
              {{ formatDuration(row.original.duration_sec) }}
            </template>
            <template #per_type_count-cell="{ row }">
              {{ fmt(row.original.per_type_count) }}
            </template>
          </UTable>
        </div>

        <p v-if="!modelStore.runsLoading && !recentRuns.length" class="muted history-empty">
          {{ t('model.noCompletedRuns') }}
        </p>
      </article>
    </section>

    <!-- ════════════════════ EMPTY STATE ════════════════════ -->
    <div v-if="!modelStore.loading && !modelInfo" class="card empty-card">
      <p class="muted">{{ t('model.noModel') }}</p>
      <NuxtLink v-if="isAdmin" to="/admin/priprava" class="ghost-link">
        {{ t('model.prepareDatasetCta') }}
      </NuxtLink>
    </div>
  </div>
</template>

<style scoped>
  .model-page,
  .hero-story-grid,
  .history-grid,
  .launch-rail,
  .snapshot-shell,
  .importance-shell {
    display: grid;
    gap: 1rem;
  }

  .model-hero {
    display: grid;
    gap: 1.1rem;
    overflow: hidden;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--ui-secondary) 12%, transparent) 0%,
        transparent 30%
      ),
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--ui-primary) 14%, transparent) 0%,
        transparent 36%
      ),
      var(--surface-panel-strong);
  }

  .card {
    padding: 1.25rem;
    border-radius: 1.5rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
    display: grid;
    gap: 1rem;
  }

  .section-head h1 {
    font-size: clamp(1.5rem, 2vw, 2rem);
  }

  .hero-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(300px, 0.85fr);
    gap: 1rem;
    align-items: start;
  }

  .hero-story-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .history-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-grid {
    display: grid;
    gap: 0.9rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-grid.compact {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .training-workbench,
  .live-progress,
  .history-panel {
    display: grid;
    gap: 1rem;
  }

  .source-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(260px, 0.75fr);
    gap: 1rem;
    margin-top: 1rem;
  }

  /* ── Glassmorphism cards ──────────────────────────────────── */
  .story-card,
  .launch-card,
  .hero-spotlight,
  .focus-card,
  .snapshot-spotlight,
  .metric-card {
    position: relative;
    overflow: hidden;
    display: grid;
    gap: 0.65rem;
    padding: 1.15rem 1.2rem;
    border-radius: 1.35rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 16px 28px rgb(15 23 42 / 8%);
    transition:
      transform 180ms ease,
      border-color 180ms ease,
      box-shadow 180ms ease,
      background 180ms ease;
  }

  .story-card::before,
  .launch-card::before,
  .hero-spotlight::before,
  .focus-card::before,
  .snapshot-spotlight::before {
    content: '';
    position: absolute;
    inset: auto auto calc(100% - 4.5rem) -1.25rem;
    width: 6rem;
    height: 6rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--ui-primary) 16%, transparent);
    filter: blur(16px);
    opacity: 0.92;
    pointer-events: none;
  }

  .story-card:hover,
  .launch-card:hover,
  .hero-spotlight:hover,
  .focus-card:hover,
  .snapshot-spotlight:hover {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--ui-primary) 26%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 22px 38px rgb(15 23 42 / 12%);
  }

  .story-card strong,
  .launch-card strong,
  .metric-card strong,
  .hero-spotlight h2,
  .focus-card h2,
  .snapshot-spotlight h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.2rem, 2vw, 1.95rem);
    line-height: 1.02;
    letter-spacing: -0.045em;
  }

  .metric-card strong {
    font-size: clamp(1rem, 1.6vw, 1.55rem);
  }

  .story-card p,
  .launch-card p,
  .hero-spotlight p,
  .focus-card p,
  .snapshot-spotlight p {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.9rem;
    line-height: 1.55;
  }

  .tone-success {
    border-color: color-mix(in srgb, var(--success) 26%, var(--border));
  }

  .tone-success::before {
    background: color-mix(in srgb, var(--success) 18%, transparent);
  }

  .tone-warning {
    border-color: color-mix(in srgb, var(--warning) 26%, var(--border));
  }

  .tone-warning::before {
    background: color-mix(in srgb, var(--warning) 18%, transparent);
  }

  /* ── Source / action panels ───────────────────────────────── */
  .source-panel,
  .action-panel,
  .live-progress {
    border-radius: 1.25rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    padding: 1rem;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 16px 28px rgb(15 23 42 / 6%);
  }

  .field {
    display: grid;
    gap: 0.55rem;
  }

  .field span {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.2em;
    text-transform: uppercase;
  }

  .action-panel {
    display: grid;
    align-content: start;
    gap: 0.85rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 10%, transparent),
      color-mix(in srgb, var(--secondary) 10%, transparent)
    );
  }

  .train-btn {
    width: 100%;
  }

  .launch-rail {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .live-progress-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .live-progress-head h2 {
    margin: 0.35rem 0 0;
    font-family: var(--font-display);
    font-size: 1.5rem;
  }

  .selected-source-card {
    margin-top: 1rem;
    padding: 1rem;
    border-radius: 1.25rem;
    border: 1px solid var(--border);
    display: grid;
    gap: 0.5rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

  /* ── Spotlight ────────────────────────────────────────────── */
  .spotlight-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .spotlight-meta,
  .snapshot-meta {
    display: grid;
    gap: 0.6rem;
    margin-top: auto;
  }

  .spotlight-meta span,
  .snapshot-meta span {
    display: inline-flex;
    align-items: center;
    min-height: 2.75rem;
    padding: 0.7rem 0.85rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--ui-primary) 14%, var(--border));
    background: color-mix(in srgb, var(--surface-soft) 84%, transparent);
    color: var(--text);
    font-size: 0.85rem;
    line-height: 1.45;
  }

  .model-source-pill {
    display: inline-flex;
    align-items: center;
    min-height: 2.3rem;
    padding: 0.45rem 0.85rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 22%, var(--border));
    background: color-mix(in srgb, var(--primary) 10%, transparent);
    color: var(--primary);
    font-size: 0.78rem;
    font-weight: 700;
  }

  /* ── Snapshot ─────────────────────────────────────────────── */
  .snapshot-shell {
    grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
    margin-top: 1rem;
  }

  /* ── Feature importance ───────────────────────────────────── */
  .importance-shell {
    grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
    margin-top: 1rem;
  }

  .importance-chart {
    height: 400px;
    padding: 0.85rem;
    border-radius: 1.25rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--surface-muted) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 16px 28px rgb(15 23 42 / 6%);
  }

  .feature-list {
    display: grid;
    gap: 0.75rem;
    margin-top: 0.35rem;
  }

  .feature-item {
    display: grid;
    gap: 0.45rem;
  }

  .feature-copy {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .feature-copy strong {
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--text);
  }

  .feature-copy span {
    color: var(--text-muted);
    font-size: 0.84rem;
    font-variant-numeric: tabular-nums;
  }

  .feature-bar {
    display: block;
    height: 0.5rem;
    border-radius: 999px;
    overflow: hidden;
    background: color-mix(in srgb, var(--surface-soft) 88%, transparent);
  }

  .feature-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--ui-primary) 86%, white 6%),
      color-mix(in srgb, var(--ui-secondary) 24%, var(--ui-primary) 76%)
    );
    box-shadow: 0 8px 18px color-mix(in srgb, var(--ui-primary) 24%, transparent);
  }

  /* ── History ──────────────────────────────────────────────── */
  .history-empty {
    margin-top: 1rem;
  }

  /* ── Empty state ──────────────────────────────────────────── */
  .empty-card {
    text-align: center;
    padding: 2rem;
  }

  .ghost-link {
    color: var(--primary);
    font-weight: 600;
    text-decoration: none;
  }

  .ghost-link:hover {
    text-decoration: underline;
  }

  /* ── Metric card tone indicator ───────────────────────────── */
  .metric-tone-bar {
    display: block;
    height: 3px;
    width: 2.5rem;
    border-radius: 999px;
    background: var(--border);
  }

  .metric-tone-bar.tone-success {
    background: var(--success);
  }

  .metric-tone-bar.tone-warning {
    background: var(--warning);
  }

  .metric-tone-bar.tone-default {
    background: var(--border);
  }

  /* ── Table wrapper ────────────────────────────────────────── */
  .table-wrap {
    overflow-x: auto;
  }

  /* ── Responsive ───────────────────────────────────────────── */
  @media (max-width: 1100px) {
    .hero-shell,
    .hero-story-grid,
    .snapshot-shell,
    .importance-shell,
    .launch-rail,
    .source-shell,
    .history-grid,
    .hero-grid.compact {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .hero-grid {
      grid-template-columns: 1fr;
    }

    .spotlight-head,
    .feature-copy,
    .live-progress-head,
    .section-head {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
