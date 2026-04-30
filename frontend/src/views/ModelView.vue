<script setup lang="ts">
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tag from 'primevue/tag'
  import Tabs from 'primevue/tabs'
  import AdminRunDetailPanel from '../components/admin/AdminRunDetailPanel.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import EmptyState from '../components/EmptyState.vue'
  import MetricCard from '../components/MetricCard.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useWorkbenchStore } from '../stores/workbench'
  import { useFormat } from '../composables/useFormat'
  import { readQueryString, readQueryTab } from '../utils/routeQuery'
  import { formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import type { AdminRunSummary, AdminRunDetail } from '../types/api'
  import type {
    ModelFeatureImportance,
    ModelInfo,
    ModelResearchAuditRow,
    ModelResearchDraggingRow,
    ModelResearchImpact,
    ModelSourceMeta,
    ModelSourceOption,
    ModelTrainingCard,
    ModelTrainingStatus,
  } from '../features/model/types'
  import ModelTrainingWorkspace from '../features/model/ModelTrainingWorkspace.vue'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

  interface TrainingDatasetSource {
    exists?: boolean
    rows?: number
    relative_path?: string
    updated_at?: string | null
    uploaded_at?: string | null
    original_name?: string | null
    name?: string | null
    row_count?: number | null
  }

  interface ModelDatasetRecord {
    original_name: string
    relative_path: string
    row_count: number
    uploaded_at: string
  }

  interface ModelRunRecord {
    created_at: string
    source_csv_path?: string | null
    rows: number
    mae: number
    rmse: number
    r2: number
    mape?: number | null
    duration_sec?: number | null
    per_type_count?: number | null
  }

  interface ModelDiagnostics {
    research_impact?: ModelResearchImpact | null
  }

  const modelTabs = ['analysis', 'importance', 'history'] as const

  const { t } = useI18n()
  const { fmt, fmtCurrency, formatType } = useFormat()
  const route = useRoute()
  const router = useRouter()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const model = useModelStore()
  const workbench = useWorkbenchStore()

  const selectedCsv = ref('')
  const modelTab = ref<'analysis' | 'importance' | 'history'>(
    readQueryTab(route.query.tab, modelTabs, 'analysis'),
  )
  const pollTimer = ref<number | null>(null)
  const selectedTrainingRunId = ref(readQueryString(route.query.run) || '')
  const modelInfoLoaded = ref(false)
  const modelDiagnosticsLoaded = ref(false)
  const featureImportanceLoaded = ref(false)
  const jobHistoryLoaded = ref(false)
  const modelRunsLoaded = ref(false)
  const sourceDatasetsLoaded = ref(false)
  const trainingDatasetLoaded = ref(false)
  const trainingRunsLoaded = ref(false)
  const activeTrainingLoaded = ref(false)

  const isAdmin = computed(() => auth.user?.role === 'admin')
  const trainingDataset = computed(() => dataStore.trainingDataset as TrainingDatasetSource | null)
  const datasets = computed(() =>
    Array.isArray(dataStore.datasets) ? (dataStore.datasets as ModelDatasetRecord[]) : [],
  )
  const modelInfo = computed(() => model.info as ModelInfo | null)
  const modelDiagnostics = computed(() => model.diagnostics as ModelDiagnostics | null)
  const trainingStatus = computed(() => model.trainingStatus as ModelTrainingStatus | null)
  const recentJobs = computed(() => model.jobHistory.slice(0, 6) as AdminRunSummary[])
  const recentRuns = computed(() => model.modelRuns.slice(0, 6) as ModelRunRecord[])
  const trainingLocked = computed(() => model.training)
  const selectedTrainingRun = computed(() => workbench.selectedTrainingRun as AdminRunDetail | null)
  const featureImportance = computed(() =>
    (Array.isArray(model.importance) ? (model.importance as ModelFeatureImportance[]) : []).slice(
      0,
      15,
    ),
  )

  const uploadOptions = computed<ModelSourceOption[]>(() =>
    datasets.value
      .filter((dataset) => dataset.relative_path !== trainingDataset.value?.relative_path)
      .map((dataset) => ({
        label: `${dataset.original_name} (${fmt(dataset.row_count)} ${t('data.rows')})`,
        value: dataset.relative_path,
      })),
  )

  const sourceOptions = computed<ModelSourceOption[]>(() => {
    const options: ModelSourceOption[] = []
    if (trainingDataset.value?.exists && trainingDataset.value.relative_path) {
      options.push({
        label: `${t('model.preparedDatasetLabel')} (${fmt(trainingDataset.value.rows)} ${t('data.rows')})`,
        value: trainingDataset.value.relative_path,
      })
    }
    return [...options, ...uploadOptions.value]
  })

  const selectedSourceMeta = computed<ModelSourceMeta | null>(() => {
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

    const dataset = datasets.value.find((item) => item.relative_path === selectedCsv.value)
    if (!dataset) return null
    return {
      name: dataset.original_name,
      original_name: dataset.original_name,
      row_count: dataset.row_count,
      uploaded_at: dataset.uploaded_at,
      relative_path: dataset.relative_path,
    }
  })

  const selectedSourcePath = computed(
    () =>
      selectedSourceMeta.value?.relative_path ||
      trainingDataset.value?.relative_path ||
      modelInfo.value?.source_csv_path ||
      '',
  )

  const activeStatus = computed(() => trainingStatus.value)
  const researchImpact = computed(() => modelDiagnostics.value?.research_impact || null)
  const researchDraggingRows = computed(() => researchImpact.value?.dragging_segments || [])
  const researchAuditRows = computed(() => researchImpact.value?.per_type_feature_audit || [])

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

  const metricsCards = computed<ModelTrainingCard[]>(() => {
    const metrics = modelInfo.value?.global_metrics
    if (!metrics) return []
    return [
      { label: 'MAE', value: fmtCurrency(metrics.mae) },
      { label: 'RMSE', value: fmtCurrency(metrics.rmse) },
      { label: 'R²', value: formatScore(metrics.r2) },
      { label: 'MAPE', value: fmtPercent(metrics.mape) },
      { label: t('model.medianError'), value: fmtCurrency(metrics.median_ae) },
    ]
  })

  const runCards = computed<ModelTrainingCard[]>(() => {
    if (!activeStatus.value) return []
    return [
      {
        label: t('model.trainingProgress'),
        value: progressLabel(activeStatus.value.progress),
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
        value: progressLabel(activeStatus.value.current_model_progress),
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

  const heroSummaryCards = computed<ModelTrainingCard[]>(() => [
    {
      label: t('model.preparedDataset'),
      value: trainingDataset.value?.exists
        ? t('model.preparedDatasetReady')
        : t('model.preparedDatasetMissing'),
      meta: trainingDataset.value?.exists
        ? `${fmt(trainingDataset.value.rows)} ${t('data.rows')}`
        : t('model.prepareDataFirst'),
      tone: trainingDataset.value?.exists ? 'success' : 'warning',
    },
    {
      label: t('model.currentModel'),
      value: modelInfo.value ? t('model.modelReady') : t('model.modelMissing'),
      meta: modelInfo.value?.trained_at
        ? formatDate(modelInfo.value.trained_at)
        : t('model.noModel'),
      tone: modelInfo.value ? 'success' : 'warning',
    },
    {
      label: t('model.trainingStatus'),
      value: activeStatus.value ? jobStatusLabel(activeStatus.value.status) : t('common.noData'),
      meta: activeStatus.value ? trainingStageLabel.value : t('model.trainingCtaHint'),
    },
    {
      label: t('model.trainingProgress'),
      value: activeStatus.value ? progressLabel(activeStatus.value.progress) : '0%',
      meta:
        activeStatus.value?.eta_sec != null
          ? `${t('model.eta')}: ${formatDuration(activeStatus.value.eta_sec)}`
          : t('common.noData'),
    },
  ])

  const modelSnapshotDescription = computed(() =>
    modelInfo.value
      ? `${t('model.trainedAt')}: ${formatDate(modelInfo.value.trained_at)} · ${fmt(modelInfo.value.rows)} ${t('data.rows')} · ${formatDuration(modelInfo.value.duration_sec)}`
      : t('model.noModel'),
  )

  const researchSummaryCards = computed<ModelTrainingCard[]>(() => {
    const impact = researchImpact.value
    const best = impact?.best_run?.combined_metrics
    if (!impact || !best) return []
    return [
      {
        label: t('diag.bestResearchRun'),
        value: impact.best_run?.label || t('common.noData'),
        meta: impact.generated_at ? formatDate(impact.generated_at) : '',
      },
      {
        label: 'R²',
        value: formatScore(best.r2),
        meta: t('diag.routedR2'),
      },
      {
        label: 'MAPE',
        value: fmtPercent(best.mape),
        meta: t('diag.mapeDesc'),
      },
      {
        label: t('diag.weakestTypes'),
        value: fmt(researchDraggingRows.value.length),
        meta: t('diag.scoreDrivers'),
      },
    ]
  })

  function getChartColors() {
    const style = getComputedStyle(document.documentElement)
    return {
      bar: style.getPropertyValue('--primary').trim() || '#2d8479',
      tick: style.getPropertyValue('--text-soft').trim() || '#94a3b8',
    }
  }

  const importanceChart = computed(() => {
    const colors = getChartColors()
    return {
      labels: featureImportance.value.map((item) => item.label),
      datasets: [
        {
          label: t('model.importance'),
          data: featureImportance.value.map((item) => item.importance),
          backgroundColor: colors.bar,
          borderRadius: 10,
        },
      ],
    }
  })

  const importanceOptions = computed(() => {
    const colors = getChartColors()
    return {
      indexAxis: 'y' as const,
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { color: colors.tick } },
        y: { ticks: { color: colors.tick } },
      },
    }
  })

  watch(
    trainingDataset,
    (dataset) => {
      if (dataset?.exists && dataset.relative_path && !selectedCsv.value) {
        selectedCsv.value = dataset.relative_path
      }
    },
    { immediate: true },
  )

  watch(
    () => workbench.trainingRuns,
    (runs) => {
      if (!runs.length) return
      const hasRequestedRun = Boolean(readQueryString(route.query.run))

      const resolvedRunId = runs.some((item) => item.id === selectedTrainingRunId.value)
        ? selectedTrainingRunId.value
        : runs[0].id

      if (!resolvedRunId) return

      if (selectedTrainingRunId.value !== resolvedRunId) {
        selectedTrainingRunId.value = resolvedRunId
      }

      if (selectedTrainingRun.value?.id !== resolvedRunId) {
        if (hasRequestedRun) {
          void loadTrainingRunDetail(resolvedRunId)
        } else {
          void workbench.fetchTrainingRunDetail(resolvedRunId)
        }
      }
    },
    { immediate: true },
  )

  function fmtPercent(value?: number | null) {
    return formatPercent(value, { scale: 0.01, minimumFractionDigits: 1 })
  }

  function formatScore(value?: number | null) {
    return formatNumber(value, { minimumFractionDigits: 4, maximumFractionDigits: 4 })
  }

  function formatDate(value?: string | null) {
    if (!value) return t('common.noData')
    return formatDateTime(value)
  }

  function formatDuration(value?: number | null) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    return `${formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }

  function jobSeverity(status?: string | null) {
    if (status === 'completed') return 'success'
    if (status === 'failed') return 'danger'
    if (status === 'running') return 'warn'
    return 'secondary'
  }

  function jobStatusLabel(status?: string | null) {
    return status ? t(`model.status.${status}`) : '—'
  }

  function stageLabel(stage?: string | null) {
    return stage ? t(`model.stages.${stage}`) : '—'
  }

  function progressLabel(value?: number | null) {
    if (value == null || Number.isNaN(Number(value))) return '0%'
    return `${formatNumber(value, { maximumFractionDigits: 0 })}%`
  }

  function currentModelLabel(value?: string | null) {
    if (value === 'global') return t('model.globalModel')
    if (value === 'done') return t('model.completedStage')
    return value ? formatType(value) : t('common.noData')
  }

  function humanizeToken(value?: string | null) {
    if (value == null || String(value).trim() === '') return t('common.noData')
    return String(value)
      .replace(/[_-]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/\b\w/g, (match) => match.toUpperCase())
  }

  function formatGoalGap(row: ModelResearchDraggingRow) {
    const r2Gap = Math.max(0, 0.9 - Number(row?.r2 || 0))
    const mapeGap = Math.max(0, Number(row?.mape || 0) - 10)
    return `R² ${formatNumber(r2Gap, { minimumFractionDigits: 3, maximumFractionDigits: 3 })} · MAPE ${formatNumber(mapeGap, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}pp`
  }

  function formatResearchTopFeatures(row: ModelResearchDraggingRow | ModelResearchAuditRow) {
    const features = Array.isArray(row?.top_features) ? row.top_features : []
    if (!features.length) return t('common.noData')
    return features
      .slice(0, 3)
      .map((item) => item.feature || '')
      .filter(Boolean)
      .join(', ')
  }

  function featureLoadSeverity(value?: string | null) {
    if (value === 'high') return 'warn'
    if (value === 'medium') return 'info'
    return 'secondary'
  }

  function syncModelTabFromRoute(query = route.query) {
    const allowedTabs = isAdmin.value ? modelTabs : modelTabs.filter((tab) => tab !== 'history')
    const nextTab = readQueryTab(query.tab, allowedTabs, 'analysis')
    if (modelTab.value !== nextTab) {
      modelTab.value = nextTab
    }
  }

  function syncModelTabToRoute(tab: string) {
    const allowedTabs = isAdmin.value ? modelTabs : modelTabs.filter((value) => value !== 'history')
    const nextTab = readQueryTab(tab, allowedTabs, 'analysis')
    const currentTab = readQueryTab(route.query.tab, allowedTabs, 'analysis')
    if (currentTab === nextTab) return
    void router.replace({ query: { ...route.query, tab: nextTab } })
  }

  function syncTrainingRunFromRoute(query = route.query) {
    const nextRunId = readQueryString(query.run)
    if (!nextRunId || selectedTrainingRunId.value === nextRunId) return
    selectedTrainingRunId.value = nextRunId
    if (isAdmin.value && modelTab.value !== 'history') {
      modelTab.value = 'history'
    }
    if (
      workbench.trainingRuns.some((item) => item.id === nextRunId) &&
      selectedTrainingRun.value?.id !== nextRunId
    ) {
      void workbench.fetchTrainingRunDetail(nextRunId)
    }
  }

  function syncTrainingRunToRoute(jobId: string) {
    const currentRunId = readQueryString(route.query.run) || ''
    if (currentRunId === jobId) return
    void router.replace({
      query: {
        ...route.query,
        ...(jobId ? { run: jobId } : {}),
      },
    })
  }

  async function loadTrainingRunDetail(jobId: string) {
    if (!jobId) return
    selectedTrainingRunId.value = jobId
    if (isAdmin.value && modelTab.value !== 'history') {
      modelTab.value = 'history'
    }
    syncTrainingRunToRoute(jobId)
    await workbench.fetchTrainingRunDetail(jobId)
  }

  async function ensureModelInfoLoaded(force = false) {
    if (!force && (modelInfoLoaded.value || Boolean(modelInfo.value))) {
      modelInfoLoaded.value = true
      return
    }
    await model.fetchInfo()
    modelInfoLoaded.value = true
  }

  async function ensureDiagnosticsLoaded(force = false) {
    if (!force && (modelDiagnosticsLoaded.value || Boolean(modelDiagnostics.value))) {
      modelDiagnosticsLoaded.value = true
      return
    }
    await model.fetchDiagnostics()
    modelDiagnosticsLoaded.value = true
  }

  async function ensureImportanceLoaded(force = false) {
    if (!force && (featureImportanceLoaded.value || featureImportance.value.length > 0)) {
      featureImportanceLoaded.value = true
      return
    }
    await model.fetchImportance()
    featureImportanceLoaded.value = true
  }

  async function ensureJobsLoaded(force = false) {
    if (!isAdmin.value) return
    if (!force && (jobHistoryLoaded.value || recentJobs.value.length > 0)) {
      jobHistoryLoaded.value = true
      return
    }
    await model.fetchJobs()
    jobHistoryLoaded.value = true
  }

  async function ensureRunsLoaded(force = false) {
    if (!isAdmin.value) return
    if (!force && (modelRunsLoaded.value || recentRuns.value.length > 0)) {
      modelRunsLoaded.value = true
      return
    }
    await model.fetchRuns()
    modelRunsLoaded.value = true
  }

  async function ensureSourceDatasetsLoaded(force = false) {
    if (!isAdmin.value) return
    if (!force && sourceDatasetsLoaded.value) return
    await dataStore.fetchDatasets(false, true, { perPage: 200 })
    sourceDatasetsLoaded.value = true
  }

  async function ensureTrainingDatasetLoaded(force = false) {
    if (!isAdmin.value) return
    if (!force && (trainingDatasetLoaded.value || Boolean(trainingDataset.value?.exists))) {
      trainingDatasetLoaded.value = true
      return
    }
    await dataStore.fetchTrainingDataset()
    trainingDatasetLoaded.value = true
  }

  async function ensureTrainingRunsLoaded(force = false) {
    if (!isAdmin.value) return
    if (!force && (trainingRunsLoaded.value || workbench.trainingRuns.length > 0)) {
      trainingRunsLoaded.value = true
      return
    }
    await workbench.fetchTrainingRuns(force)
    trainingRunsLoaded.value = true
  }

  async function ensureActiveTrainingLoaded(force = false) {
    if (!isAdmin.value) return null
    if (!force && activeTrainingLoaded.value) {
      return trainingStatus.value
    }
    const activeJob = await model.fetchActiveTraining()
    activeTrainingLoaded.value = true
    return activeJob
  }

  async function ensureAdminSetupLoaded(force = false) {
    if (!isAdmin.value) return
    await Promise.allSettled([
      ensureSourceDatasetsLoaded(force),
      ensureTrainingDatasetLoaded(force),
      ensureActiveTrainingLoaded(force),
    ])
  }

  async function ensureHistoryLoaded(force = false) {
    if (!isAdmin.value) return
    await Promise.allSettled([
      ensureJobsLoaded(force),
      ensureRunsLoaded(force),
      ensureTrainingRunsLoaded(force),
    ])
  }

  async function loadActiveModelTabData(force = false) {
    if (modelTab.value === 'importance') {
      await Promise.allSettled([ensureModelInfoLoaded(force), ensureImportanceLoaded(force)])
      return
    }

    if (modelTab.value === 'history' && isAdmin.value) {
      await Promise.allSettled([ensureModelInfoLoaded(force), ensureHistoryLoaded(force)])
      return
    }

    await Promise.allSettled([ensureModelInfoLoaded(force), ensureDiagnosticsLoaded(force)])
  }

  async function train() {
    if (!selectedCsv.value || trainingLocked.value) return
    const result = await model.startTraining(selectedCsv.value)
    if (isAdmin.value) {
      await Promise.allSettled([ensureJobsLoaded(true), ensureRunsLoaded(true)])
      void workbench.fetchTrainingRuns(true)
    }
    if (result?.job_id) {
      startPolling(result.job_id)
    }
  }

  async function refreshModelArtifacts() {
    if (modelTab.value !== 'analysis') {
      modelDiagnosticsLoaded.value = false
    }
    if (modelTab.value !== 'importance') {
      featureImportanceLoaded.value = false
    }
    if (modelTab.value !== 'history') {
      jobHistoryLoaded.value = false
      modelRunsLoaded.value = false
      trainingRunsLoaded.value = false
    }

    await Promise.allSettled([ensureAdminSetupLoaded(true), loadActiveModelTabData(true)])
    if (modelTab.value !== 'history' && isAdmin.value) {
      void ensureHistoryLoaded(true)
    }
  }

  function stopPolling() {
    if (pollTimer.value != null) {
      window.clearInterval(pollTimer.value)
      pollTimer.value = null
    }
  }

  function isTerminalStatus(status?: string | null) {
    return status === 'completed' || status === 'failed'
  }

  function startPolling(jobId: string) {
    stopPolling()

    pollTimer.value = window.setInterval(async () => {
      const status = await model.pollStatus(jobId)
      if (!status || isTerminalStatus(status.status)) {
        stopPolling()
        await refreshModelArtifacts()
      }
    }, 1800)
  }

  async function syncExistingTraining() {
    const activeJob = await ensureActiveTrainingLoaded()
    if (activeJob?.job_id && !isTerminalStatus(activeJob.status)) {
      startPolling(activeJob.job_id)
    }
  }

  async function initializePage() {
    await Promise.allSettled([ensureAdminSetupLoaded(), loadActiveModelTabData()])
    await syncExistingTraining()
  }

  onMounted(async () => {
    syncModelTabFromRoute(route.query)
    syncTrainingRunFromRoute(route.query)
    await initializePage()
  })

  onUnmounted(() => {
    stopPolling()
  })

  watch(
    () => route.query.tab,
    () => {
      syncModelTabFromRoute(route.query)
    },
  )

  watch(
    () => route.query.run,
    () => {
      syncTrainingRunFromRoute(route.query)
      if (isAdmin.value && readQueryString(route.query.run)) {
        void ensureHistoryLoaded()
      }
    },
  )

  watch(modelTab, (tab) => {
    syncModelTabToRoute(tab)
    void loadActiveModelTabData()
  })
</script>

<template>
  <div class="model-page">
    <AdminWorkspaceHero
      v-if="isAdmin"
      :eyebrow="t('model.trainModel')"
      :title="t('model.trainingTitle')"
      :description="t('model.trainingBody')"
      :metrics="heroSummaryCards"
      :links="adminWorkspaceLinks"
      :status="activeStatus ? jobStatusLabel(activeStatus.status) : ''"
      :status-severity="activeStatus ? jobSeverity(activeStatus.status) : 'secondary'"
    >
      <template #actions>
        <Button
          v-if="!trainingDataset?.exists"
          :as="RouterLink"
          to="/admin/priprava"
          class="hero-link"
          severity="contrast"
          outlined
          icon="pi pi-arrow-right"
          :label="t('model.goToPrepare')"
        />
      </template>
    </AdminWorkspaceHero>

    <section class="model-primary-grid" :class="{ 'viewer-mode': !isAdmin }">
      <ModelTrainingWorkspace
        v-if="isAdmin"
        v-model="selectedCsv"
        :eyebrow="t('model.selectDataset')"
        :title="t('model.trainingWorkbench')"
        :description="trainingLocked ? t('model.trainingLockedHint') : t('model.selectSourceHint')"
        :options="sourceOptions"
        :selected-source-meta="selectedSourceMeta"
        :selected-source-path="selectedSourcePath"
        :training-locked="trainingLocked"
        :active-status="activeStatus"
        :status-label="activeStatus ? jobStatusLabel(activeStatus.status) : ''"
        :status-severity="activeStatus ? jobSeverity(activeStatus.status) : 'secondary'"
        :stage-label="trainingStageLabel"
        :run-cards="runCards"
        :action-label="trainingLocked ? t('model.training') : t('model.trainButton')"
        :action-hint="t('model.trainingCtaHint')"
        :locked-hint="t('model.trainingLockedHint')"
        :error="model.error || ''"
        @train="train"
        @retry="initializePage"
      />

      <SectionPanel
        class="model-snapshot-panel"
        :eyebrow="t('model.currentModel')"
        :title="t('model.modelSnapshot')"
        :description="modelSnapshotDescription"
      >
        <template #actions>
          <Tag v-if="modelInfo?.source_csv_path" severity="secondary">
            {{ t('model.currentSource') }}: {{ modelInfo.source_csv_path }}
          </Tag>
        </template>

        <EmptyState
          v-if="!model.loading && !modelInfo"
          icon="pi pi-chart-line"
          :message="t('model.noModel')"
        />

        <template v-else-if="modelInfo">
          <div class="model-snapshot-metrics">
            <MetricCard
              v-for="card in metricsCards"
              :key="card.label"
              :label="card.label"
              :value="card.value"
              :meta="card.meta"
              :tone="card.tone || 'default'"
            />
          </div>

          <p class="model-snapshot-note">
            {{ t('model.featureImportanceHint') }}
          </p>
        </template>
      </SectionPanel>
    </section>

    <Tabs v-model:value="modelTab" class="model-tabs">
      <TabList>
        <Tab value="analysis">{{ t('common.overview') }}</Tab>
        <Tab value="importance">{{ t('model.featureImportance') }}</Tab>
        <Tab v-if="isAdmin" value="history">{{ t('model.trainingHistory') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="analysis">
          <section class="model-secondary-grid">
            <SectionPanel
              v-if="modelInfo?.per_type_metrics"
              class="model-analysis-panel"
              :eyebrow="t('model.perTypeMetrics')"
              :title="t('model.propertyTypeBreakdown')"
              :description="t('model.propertyTypeBreakdownHint')"
            >
              <DataTable
                :value="
                  Object.entries(modelInfo.per_type_metrics).map(([propertyType, metrics]) => ({
                    propertyType,
                    ...(metrics as Record<string, unknown>),
                  }))
                "
                size="small"
                striped-rows
                table-style="min-width: 100%"
              >
                <Column field="propertyType" :header="t('model.propertyType')" sortable>
                  <template #body="{ data }">{{ formatType(data.propertyType) }}</template>
                </Column>
                <Column field="mae" header="MAE" sortable>
                  <template #body="{ data }">{{ fmtCurrency(data.mae) }}</template>
                </Column>
                <Column field="rmse" header="RMSE" sortable>
                  <template #body="{ data }">{{ fmtCurrency(data.rmse) }}</template>
                </Column>
                <Column field="r2" :header="t('diag.r2Metric')" sortable>
                  <template #body="{ data }">
                    <Tag
                      :severity="data.r2 >= 0.7 ? 'success' : data.r2 >= 0.4 ? 'warn' : 'danger'"
                      :value="formatScore(data.r2)"
                    />
                  </template>
                </Column>
                <Column field="mape" header="MAPE" sortable>
                  <template #body="{ data }">{{ fmtPercent(data.mape) }}</template>
                </Column>
                <Column field="n_train" :header="t('diag.sampleCount')" sortable>
                  <template #body="{ data }">{{ fmt(data.n_train) }}</template>
                </Column>
              </DataTable>
            </SectionPanel>

            <SectionPanel
              v-if="researchImpact"
              class="model-analysis-panel"
              :eyebrow="t('diag.researchImpact')"
              :title="t('diag.perTypeFeaturePlan')"
              :description="t('diag.researchImpactDesc')"
            >
              <div class="model-snapshot-metrics">
                <MetricCard
                  v-for="card in researchSummaryCards"
                  :key="card.label"
                  :label="card.label"
                  :value="card.value"
                  :meta="card.meta"
                  :tone="card.tone || 'default'"
                />
              </div>

              <DataTable
                v-if="researchDraggingRows.length"
                :value="researchDraggingRows"
                size="small"
                striped-rows
                table-style="min-width: 100%"
              >
                <Column field="property_type" :header="t('diag.weakestTypes')" sortable>
                  <template #body="{ data }">{{ formatType(data.property_type) }}</template>
                </Column>
                <Column field="r2" :header="t('diag.r2Metric')" sortable>
                  <template #body="{ data }">
                    <Tag
                      :severity="data.r2 >= 0.7 ? 'success' : data.r2 >= 0.4 ? 'warn' : 'danger'"
                      :value="formatScore(data.r2)"
                    />
                  </template>
                </Column>
                <Column field="mape" header="MAPE" sortable>
                  <template #body="{ data }">{{ fmtPercent(data.mape) }}</template>
                </Column>
                <Column field="n_test" :header="t('diag.sampleCount')" sortable>
                  <template #body="{ data }">{{ fmt(data.n_test) }}</template>
                </Column>
                <Column :header="t('diag.gapToGoal')">
                  <template #body="{ data }">{{ formatGoalGap(data) }}</template>
                </Column>
              </DataTable>

              <DataTable
                v-if="researchAuditRows.length"
                :value="researchAuditRows"
                size="small"
                striped-rows
                table-style="min-width: 100%"
              >
                <Column field="property_type" :header="t('diag.type')" sortable>
                  <template #body="{ data }">{{ formatType(data.property_type) }}</template>
                </Column>
                <Column field="feature_load" :header="t('diag.featureLoad')" sortable>
                  <template #body="{ data }">
                    <Tag
                      :severity="featureLoadSeverity(data.feature_load)"
                      :value="humanizeToken(data.feature_load)"
                    />
                  </template>
                </Column>
                <Column field="selected_total" :header="t('diag.featureCount')" sortable>
                  <template #body="{ data }">
                    {{ fmt(data.selected_total) }} ({{ fmt(data.selected_numeric) }}/{{
                      fmt(data.selected_categorical)
                    }})
                  </template>
                </Column>
                <Column field="chosen_feature_variant" :header="t('diag.featureVariant')" sortable>
                  <template #body="{ data }">
                    {{ humanizeToken(data.chosen_feature_variant) }}
                  </template>
                </Column>
                <Column
                  field="chosen_target_transform"
                  :header="t('diag.targetTransform')"
                  sortable
                >
                  <template #body="{ data }">
                    {{ humanizeToken(data.chosen_target_transform) }}
                  </template>
                </Column>
                <Column field="training_policy" :header="t('diag.trainingPolicy')" sortable>
                  <template #body="{ data }">{{ humanizeToken(data.training_policy) }}</template>
                </Column>
                <Column field="routing_mode" :header="t('diag.routing')" sortable>
                  <template #body="{ data }">
                    {{ humanizeToken(data.routing_mode) }} ·
                    {{
                      formatNumber(data.blend_weight, {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })
                    }}
                  </template>
                </Column>
                <Column :header="t('diag.topFeatureStack')">
                  <template #body="{ data }">{{ formatResearchTopFeatures(data) }}</template>
                </Column>
              </DataTable>
            </SectionPanel>
          </section>
        </TabPanel>

        <TabPanel value="importance">
          <SectionPanel
            v-if="featureImportance.length"
            class="model-chart-panel"
            :eyebrow="t('model.featureImportance')"
            :title="t('model.featureImportanceTitle')"
            :description="t('model.featureImportanceHint')"
          >
            <div class="importance-chart">
              <Bar :data="importanceChart" :options="importanceOptions" />
            </div>
          </SectionPanel>
        </TabPanel>

        <TabPanel v-if="isAdmin" value="history">
          <section v-if="isAdmin" class="history-grid">
            <SectionPanel
              class="model-history-panel"
              :eyebrow="t('model.trainingHistory')"
              :title="t('model.jobHistoryTitle')"
              :description="t('model.trainingHistoryHint')"
            >
              <DataTable
                :value="recentJobs"
                size="small"
                striped-rows
                table-style="min-width: 100%"
                responsive-layout="scroll"
              >
                <Column field="created_at" :header="t('predict.date')">
                  <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
                </Column>
                <Column field="status" :header="t('model.trainingStatus')">
                  <template #body="{ data }">
                    <Tag
                      :severity="jobSeverity(data.status)"
                      :value="jobStatusLabel(data.status)"
                    />
                  </template>
                </Column>
                <Column field="stage" :header="t('model.trainingStage')">
                  <template #body="{ data }">{{ stageLabel(data.stage) }}</template>
                </Column>
                <Column field="progress" :header="t('model.trainingProgress')">
                  <template #body="{ data }">{{ progressLabel(data.progress) }}</template>
                </Column>
                <Column field="current_model" :header="t('model.currentModel')">
                  <template #body="{ data }">{{ currentModelLabel(data.current_model) }}</template>
                </Column>
                <Column field="elapsed_sec" :header="t('model.elapsed')">
                  <template #body="{ data }">
                    {{ formatDuration(data.elapsed_sec || data.duration_sec) }}
                  </template>
                </Column>
              </DataTable>

              <p v-if="!model.jobsLoading && !recentJobs.length" class="muted history-empty">
                {{ t('model.noTrainingHistory') }}
              </p>
            </SectionPanel>

            <SectionPanel
              class="model-history-panel"
              :eyebrow="t('model.completedRuns')"
              :title="t('model.completedRunsTitle')"
              :description="t('model.completedRunsHint')"
            >
              <DataTable
                :value="recentRuns"
                size="small"
                striped-rows
                table-style="min-width: 100%"
                responsive-layout="scroll"
              >
                <Column field="created_at" :header="t('predict.date')">
                  <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
                </Column>
                <Column field="source_csv_path" :header="t('model.currentSource')" />
                <Column field="rows" :header="t('data.rows')">
                  <template #body="{ data }">{{ fmt(data.rows) }}</template>
                </Column>
                <Column field="mae" header="MAE">
                  <template #body="{ data }">{{ fmtCurrency(data.mae) }}</template>
                </Column>
                <Column field="rmse" header="RMSE">
                  <template #body="{ data }">{{ fmtCurrency(data.rmse) }}</template>
                </Column>
                <Column field="mape" header="MAPE">
                  <template #body="{ data }">{{ fmtPercent(data.mape) }}</template>
                </Column>
                <Column field="duration_sec" :header="t('diag.duration')">
                  <template #body="{ data }">{{ formatDuration(data.duration_sec) }}</template>
                </Column>
                <Column field="per_type_count" :header="t('model.perTypeModels')">
                  <template #body="{ data }">{{ fmt(data.per_type_count) }}</template>
                </Column>
              </DataTable>

              <p v-if="!model.runsLoading && !recentRuns.length" class="muted history-empty">
                {{ t('model.noCompletedRuns') }}
              </p>
            </SectionPanel>
          </section>

          <AdminRunDetailPanel
            v-if="isAdmin"
            :eyebrow="t('nav.model')"
            :title="t('workbench.recentTrainingRuns')"
            :description="t('workbench.trainingRunDetailHint')"
            run-type="training"
            :runs="workbench.trainingRuns.slice(0, 8)"
            :selected-run-id="selectedTrainingRunId"
            :selected-run="selectedTrainingRun"
            :loading="workbench.trainingRunDetailLoading"
            :error="workbench.trainingRunDetailError || workbench.trainingRunsError"
            @select="loadTrainingRunDetail"
          />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
  .model-page {
    display: grid;
    gap: var(--space-section);
    --page-accent: var(--primary);
    --page-accent-2: var(--accent);
  }

  .model-tabs {
    display: grid;
    gap: var(--space-section);
  }

  .model-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--page-accent) 40%);
    background: color-mix(in srgb, var(--surface-soft) 84%, var(--page-accent) 16%);
  }

  .model-tabs :deep(.p-tab) {
    min-height: 2.6rem;
    border-radius: calc(var(--radius-sm) - 2px);
    font-weight: 700;
  }

  .model-primary-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.85fr);
    gap: var(--space-section);
    align-items: start;
  }

  .model-primary-grid.viewer-mode {
    grid-template-columns: minmax(0, 1fr);
  }

  .model-secondary-grid,
  .history-grid {
    display: grid;
    gap: var(--space-section);
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  }

  .model-snapshot-panel,
  .model-analysis-panel,
  .model-chart-panel,
  .model-history-panel {
    position: relative;
    overflow: hidden;
    border-radius: var(--radius-lg);
    background:
      linear-gradient(
        140deg,
        color-mix(in srgb, var(--page-accent) 8%, transparent),
        transparent 50%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 98%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .model-snapshot-panel::before,
  .model-analysis-panel::before,
  .model-chart-panel::before,
  .model-history-panel::before {
    content: '';
    position: absolute;
    inset: 0 auto auto 0;
    width: 100%;
    height: 0.35rem;
    background: linear-gradient(
      90deg,
      var(--primary),
      color-mix(in srgb, var(--primary) 35%, transparent)
    );
    opacity: 0.72;
    pointer-events: none;
  }

  .model-analysis-panel::before {
    background: linear-gradient(
      90deg,
      var(--accent),
      color-mix(in srgb, var(--accent) 35%, transparent)
    );
  }

  .model-chart-panel::before {
    background: linear-gradient(
      90deg,
      var(--warning),
      color-mix(in srgb, var(--warning) 35%, transparent)
    );
  }

  .model-history-panel::before {
    background: linear-gradient(
      90deg,
      var(--text-soft),
      color-mix(in srgb, var(--text-soft) 35%, transparent)
    );
  }

  .model-snapshot-metrics {
    display: grid;
    gap: 0.9rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .model-snapshot-note {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.6;
  }

  .importance-chart {
    height: 400px;
  }

  .history-empty {
    margin-top: 1rem;
  }

  @media (max-width: 1100px) {
    .model-primary-grid,
    .model-secondary-grid,
    .history-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .model-tabs :deep(.p-tablist) {
      overflow-x: auto;
      overscroll-behavior-x: contain;
    }

    .model-tabs :deep(.p-tab) {
      flex: 0 0 auto;
      white-space: nowrap;
    }

    .model-snapshot-metrics {
      grid-template-columns: 1fr;
    }

    .importance-chart {
      height: 300px;
    }
  }
</style>
