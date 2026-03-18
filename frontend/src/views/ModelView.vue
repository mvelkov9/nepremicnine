<script setup>
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
  import Button from 'primevue/button'
  import ProgressBar from 'primevue/progressbar'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import AppDataTable from '../components/AppDataTable.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useToast } from '../composables/useToast'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const model = useModelStore()
  const { showToast } = useToast()

  const selectedCsv = ref('')
  const pollTimer = ref(null)
  const pageLoading = ref(false)

  const isAdmin = computed(() => auth.user?.role === 'admin')
  const trainingDataset = computed(() => dataStore.trainingDataset)
  const recentJobs = computed(() => model.jobHistory.slice(0, 6))
  const recentRuns = computed(() => model.modelRuns.slice(0, 6))
  const trainingLocked = computed(() => model.training)
  const perTypeRows = computed(() =>
    Object.entries(model.info?.per_type_metrics || {}).map(([propertyType, metrics]) => ({
      propertyType,
      ...metrics,
    })),
  )

  const perTypeColumns = computed(() => [
    { key: 'propertyType', label: t('model.propertyType'), sortable: true },
    { key: 'mae', label: 'MAE', sortable: true },
    { key: 'rmse', label: 'RMSE', sortable: true },
    { key: 'r2', label: 'R²', sortable: true },
    { key: 'mape', label: 'MAPE', sortable: true },
    { key: 'n_train', label: 'N', sortable: true },
  ])

  const jobColumns = computed(() => [
    { key: 'created_at', label: t('predict.date'), sortable: true },
    { key: 'status', label: t('model.trainingStatus'), sortable: true },
    { key: 'stage', label: t('model.trainingStage'), sortable: true },
    { key: 'progress', label: t('model.trainingProgress'), sortable: true },
    { key: 'current_model', label: t('model.currentModel'), sortable: true },
    { key: 'elapsed_sec', label: t('model.elapsed'), sortable: true },
  ])

  const runColumns = computed(() => [
    { key: 'created_at', label: t('predict.date'), sortable: true },
    { key: 'source_csv_path', label: t('model.currentSource'), sortable: true },
    { key: 'rows', label: t('data.rows'), sortable: true },
    { key: 'mae', label: 'MAE', sortable: true },
    { key: 'rmse', label: 'RMSE', sortable: true },
    { key: 'mape', label: 'MAPE', sortable: true },
    { key: 'duration_sec', label: t('diag.duration'), sortable: true },
    { key: 'per_type_count', label: t('model.perTypeModels'), sortable: true },
  ])

  const uploadOptions = computed(() =>
    (Array.isArray(dataStore.datasets) ? dataStore.datasets : [])
      .filter((dataset) => dataset.relative_path !== trainingDataset.value?.relative_path)
      .map((dataset) => ({
        label: `${dataset.original_name} (${fmt(dataset.row_count)} ${t('data.rows')})`,
        value: dataset.relative_path,
        dataset,
      })),
  )

  const sourceOptions = computed(() => {
    const options = []
    if (trainingDataset.value?.exists) {
      options.push({
        label: `${t('model.preparedDatasetLabel')} (${fmt(trainingDataset.value.rows)} ${t('data.rows')})`,
        value: trainingDataset.value.relative_path,
      })
    }
    return [...options, ...uploadOptions.value]
  })

  const selectedSourceMeta = computed(() => {
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
    return uploadOptions.value.find((option) => option.value === selectedCsv.value)?.dataset || null
  })

  const selectedSourcePath = computed(
    () =>
      selectedSourceMeta.value?.relative_path ||
      trainingDataset.value?.relative_path ||
      model.info?.source_csv_path ||
      '',
  )

  const activeStatus = computed(() => model.trainingStatus)

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

  const metricsCards = computed(() => {
    const metrics = model.info?.global_metrics
    if (!metrics) return []
    return [
      { label: 'MAE', value: fmtCurrency(metrics.mae) },
      { label: 'RMSE', value: fmtCurrency(metrics.rmse) },
      { label: 'R²', value: formatScore(metrics.r2) },
      { label: 'MAPE', value: fmtPercent(metrics.mape) },
      { label: t('model.medianError'), value: fmtCurrency(metrics.median_ae) },
    ]
  })

  const runCards = computed(() => {
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

  const importanceChart = computed(() => {
    const items = model.importance.slice(0, 15)
    return {
      labels: items.map((item) => item.label),
      datasets: [
        {
          label: t('model.importance'),
          data: items.map((item) => item.importance),
          backgroundColor: '#3b82f6',
          borderRadius: 10,
        },
      ],
    }
  })

  const importanceOptions = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { beginAtZero: true, ticks: { color: '#94a3b8' } },
      y: { ticks: { color: '#94a3b8' } },
    },
  }

  watch(
    trainingDataset,
    (dataset) => {
      if (dataset?.exists && !selectedCsv.value) {
        selectedCsv.value = dataset.relative_path
      }
    },
    { immediate: true },
  )

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value) {
    return formatCurrency(value)
  }

  function fmtPercent(value) {
    return formatPercent(value, { scale: 0.01, minimumFractionDigits: 1 })
  }

  function formatScore(value) {
    return formatNumber(value, { minimumFractionDigits: 4, maximumFractionDigits: 4 })
  }

  function formatType(value) {
    return getPropertyTypeLabel(value, t)
  }

  function formatDate(value) {
    if (!value) return t('common.noData')
    return formatDateTime(value)
  }

  function formatDuration(value) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    return `${formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }

  function jobSeverity(status) {
    if (status === 'completed') return 'success'
    if (status === 'failed') return 'danger'
    if (status === 'running') return 'warn'
    return 'secondary'
  }

  function jobStatusLabel(status) {
    return status ? t(`model.status.${status}`) : '—'
  }

  function stageLabel(stage) {
    return stage ? t(`model.stages.${stage}`) : '—'
  }

  async function train() {
    if (!selectedCsv.value || trainingLocked.value) return
    const result = await model.startTraining(selectedCsv.value)
    if (result?.job_id) {
      showToast(t('model.trainingQueued'), 'success')
    }
    await Promise.all([model.fetchJobs(), model.fetchRuns()])
    if (result?.job_id) {
      startPolling(result.job_id)
    }
  }

  async function refreshModelArtifacts() {
    await Promise.all([
      model.fetchInfo(),
      model.fetchImportance(),
      model.fetchDiagnostics(),
      model.fetchJobs(),
      model.fetchRuns(),
      dataStore.fetchTrainingDataset(),
    ])
  }

  function stopPolling() {
    if (pollTimer.value) {
      clearInterval(pollTimer.value)
      pollTimer.value = null
    }
  }

  function isTerminalStatus(status) {
    return status === 'completed' || status === 'failed'
  }

  function startPolling(jobId) {
    stopPolling()

    pollTimer.value = setInterval(async () => {
      const status = await model.pollStatus(jobId)
      if (!status || isTerminalStatus(status.status)) {
        stopPolling()
        await refreshModelArtifacts()
      }
    }, 1800)
  }

  async function syncExistingTraining() {
    const activeJob = await model.fetchActiveTraining()
    if (activeJob?.job_id && !isTerminalStatus(activeJob.status)) {
      startPolling(activeJob.job_id)
    }
  }

  async function loadModelView() {
    pageLoading.value = true
    try {
      await Promise.all([
        model.fetchInfo(),
        model.fetchImportance(),
        model.fetchDiagnostics(),
        model.fetchJobs(),
        model.fetchRuns(),
        dataStore.fetchDatasets(),
        dataStore.fetchTrainingDataset(),
      ])
      await syncExistingTraining()
    } finally {
      pageLoading.value = false
    }
  }

  onMounted(async () => {
    await loadModelView()
  })

  onUnmounted(() => {
    stopPolling()
  })
</script>

<template>
  <div class="model-page">
    <section v-if="pageLoading" class="card loading-card">
      <LoadingSpinner :label="t('common.loading')" />
    </section>

    <section v-if="isAdmin" class="card model-hero">
      <PageHeader
        :eyebrow="t('model.trainModel')"
        :title="t('model.trainingTitle')"
        :description="t('model.trainingBody')"
      >
        <template #actions>
          <RouterLink v-if="!trainingDataset?.exists" to="/admin/priprava">
            <Button severity="contrast" outlined :label="t('model.goToPrepare')" />
          </RouterLink>
        </template>
      </PageHeader>

      <div class="hero-grid">
        <MetricCard
          :label="t('model.preparedDataset')"
          :value="
            trainingDataset?.exists
              ? t('model.preparedDatasetReady')
              : t('model.preparedDatasetMissing')
          "
          :meta="
            trainingDataset?.exists
              ? `${fmt(trainingDataset.rows)} ${t('data.rows')} · ${formatDate(trainingDataset.updated_at)}`
              : t('model.prepareDataFirst')
          "
          :tone="trainingDataset?.exists ? 'success' : 'default'"
        />
        <MetricCard
          :label="t('model.currentModel')"
          :value="model.info ? t('model.modelReady') : t('model.modelMissing')"
          :meta="
            model.info
              ? `${formatDate(model.info.trained_at)} · ${fmt(model.info.rows)} ${t('data.rows')}`
              : t('model.noModel')
          "
          :tone="model.info ? 'success' : 'warning'"
        />
      </div>
    </section>

    <section v-if="isAdmin" class="card">
      <PageHeader
        compact
        :eyebrow="t('model.selectDataset')"
        :title="t('model.trainingWorkbench')"
        :description="trainingLocked ? t('model.trainingLockedHint') : t('model.selectSourceHint')"
      />

      <div class="source-shell">
        <div class="source-panel">
          <label class="field">
            <span>{{ t('model.selectDataset') }}</span>
            <Select
              v-model="selectedCsv"
              :options="sourceOptions"
              option-label="label"
              option-value="value"
              class="w-full"
              :placeholder="t('model.selectDataset')"
              :disabled="trainingLocked"
            />
          </label>

          <div v-if="selectedSourceMeta" class="selected-source-card">
            <span class="eyebrow">{{ t('model.selectedSource') }}</span>
            <strong>{{ selectedSourceMeta.original_name || selectedSourceMeta.name }}</strong>
            <p>{{ selectedSourcePath }}</p>
            <p class="muted">
              {{ fmt(selectedSourceMeta.row_count || selectedSourceMeta.rows || 0) }}
              {{ t('data.rows') }} ·
              {{ formatDate(selectedSourceMeta.uploaded_at || selectedSourceMeta.updated_at) }}
            </p>
          </div>
        </div>

        <div class="action-panel">
          <Button
            :label="trainingLocked ? t('model.training') : t('model.trainButton')"
            icon="pi pi-play"
            class="train-btn"
            :disabled="!selectedCsv || trainingLocked"
            @click="train"
          />
          <p class="muted">
            {{ trainingLocked ? t('model.trainingLockedHint') : t('model.trainingCtaHint') }}
          </p>
        </div>
      </div>

      <div v-if="activeStatus" class="live-progress">
        <div class="live-progress-head">
          <div>
            <span class="eyebrow">{{ t('model.trainingStatus') }}</span>
            <h2>{{ trainingStageLabel }}</h2>
          </div>
          <Tag
            :severity="jobSeverity(activeStatus.status)"
            :value="jobStatusLabel(activeStatus.status)"
          />
        </div>

        <ProgressBar :value="activeStatus.progress || 0" :show-value="false" />

        <div class="hero-grid compact">
          <MetricCard
            v-for="card in runCards"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :meta="card.meta"
          />
        </div>

        <p v-if="activeStatus.error" class="error-text">{{ activeStatus.error }}</p>
      </div>

      <p v-if="model.error" class="error-text">{{ model.error }}</p>
    </section>

    <section v-if="model.info" class="card">
      <PageHeader
        compact
        :eyebrow="t('model.currentModel')"
        :title="t('model.modelSnapshot')"
        :description="`${t('model.trainedAt')}: ${formatDate(model.info.trained_at)} · ${fmt(model.info.rows)} ${t('data.rows')} · ${formatDuration(model.info.duration_sec)}`"
      >
        <template #actions>
          <span v-if="model.info.source_csv_path" class="model-source-pill">
            {{ t('model.currentSource') }}: {{ model.info.source_csv_path }}
          </span>
        </template>
      </PageHeader>

      <div class="hero-grid compact">
        <MetricCard
          v-for="card in metricsCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
        />
      </div>
    </section>

    <section v-if="model.info?.per_type_metrics" class="card">
      <PageHeader
        compact
        :eyebrow="t('model.perTypeMetrics')"
        :title="t('model.propertyTypeBreakdown')"
        :description="t('model.propertyTypeBreakdownHint')"
      />

      <AppDataTable
        :rows="perTypeRows"
        :columns="perTypeColumns"
        row-key="propertyType"
        :page-size="8"
        :empty-message="t('empty.noResults')"
      >
        <template #cell-propertyType="{ row }">{{ formatType(row.propertyType) }}</template>
        <template #cell-mae="{ row }">{{ fmtCurrency(row.mae) }}</template>
        <template #cell-rmse="{ row }">{{ fmtCurrency(row.rmse) }}</template>
        <template #cell-r2="{ row }">{{ formatScore(row.r2) }}</template>
        <template #cell-mape="{ row }">{{ fmtPercent(row.mape) }}</template>
        <template #cell-n_train="{ row }">{{ fmt(row.n_train) }}</template>
      </AppDataTable>
    </section>

    <section v-if="model.importance.length" class="card">
      <PageHeader
        compact
        :eyebrow="t('model.featureImportance')"
        :title="t('model.featureImportanceTitle')"
        :description="t('model.featureImportanceHint')"
      />

      <div class="importance-chart">
        <Bar :data="importanceChart" :options="importanceOptions" />
      </div>
    </section>

    <section v-if="isAdmin" class="history-grid">
      <article class="card">
        <PageHeader
          compact
          :eyebrow="t('model.trainingHistory')"
          :title="t('model.jobHistoryTitle')"
          :description="t('model.trainingHistoryHint')"
        />

        <AppDataTable
          :rows="recentJobs"
          :columns="jobColumns"
          row-key="job_id"
          :page-size="6"
          :empty-message="t('model.noTrainingHistory')"
        >
          <template #cell-created_at="{ row }">{{ formatDate(row.created_at) }}</template>
          <template #cell-status="{ row }">
            <Tag :severity="jobSeverity(row.status)" :value="jobStatusLabel(row.status)"></Tag>
          </template>
          <template #cell-stage="{ row }">{{ stageLabel(row.stage) }}</template>
          <template #cell-progress="{ row }">{{ row.progress || 0 }}%</template>
          <template #cell-current_model="{ row }">
            {{ row.current_model === 'global' ? t('model.globalModel') : formatType(row.current_model) || '—' }}
          </template>
          <template #cell-elapsed_sec="{ row }">
            {{ formatDuration(row.elapsed_sec || row.duration_sec) }}
          </template>
        </AppDataTable>

        <p v-if="!model.jobsLoading && !recentJobs.length" class="muted history-empty">
          {{ t('model.noTrainingHistory') }}
        </p>
      </article>

      <article class="card">
        <PageHeader
          compact
          :eyebrow="t('model.completedRuns')"
          :title="t('model.completedRunsTitle')"
          :description="t('model.completedRunsHint')"
        />

        <AppDataTable
          :rows="recentRuns"
          :columns="runColumns"
          row-key="id"
          :page-size="6"
          :empty-message="t('model.noCompletedRuns')"
        >
          <template #cell-created_at="{ row }">{{ formatDate(row.created_at) }}</template>
          <template #cell-rows="{ row }">{{ fmt(row.rows) }}</template>
          <template #cell-mae="{ row }">{{ fmtCurrency(row.mae) }}</template>
          <template #cell-rmse="{ row }">{{ fmtCurrency(row.rmse) }}</template>
          <template #cell-mape="{ row }">{{ fmtPercent(row.mape) }}</template>
          <template #cell-duration_sec="{ row }">{{ formatDuration(row.duration_sec) }}</template>
          <template #cell-per_type_count="{ row }">{{ fmt(row.per_type_count) }}</template>
        </AppDataTable>

        <p v-if="!model.runsLoading && !recentRuns.length" class="muted history-empty">
          {{ t('model.noCompletedRuns') }}
        </p>
      </article>
    </section>

    <div v-if="!pageLoading && !model.loading && !model.info" class="card empty-card">
      <p class="muted">{{ t('model.noModel') }}</p>
      <RouterLink v-if="isAdmin" to="/admin/priprava" class="ghost-link">
        {{ t('model.prepareDatasetCta') }}
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
  .model-page,
  .history-grid {
    display: grid;
    gap: 1rem;
  }

  .history-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .loading-card {
    display: grid;
    place-items: center;
    min-height: 12rem;
  }

  .model-hero,
  .live-progress {
    display: grid;
    gap: 1rem;
  }

  .hero-grid {
    display: grid;
    gap: 0.9rem;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-grid.compact {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .source-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(260px, 0.75fr);
    gap: 1rem;
    margin-top: 1rem;
  }

  .source-panel,
  .action-panel,
  .live-progress {
    border-radius: 1.25rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    padding: 1rem;
  }

  .action-panel {
    display: grid;
    align-content: start;
    gap: 0.85rem;
  }

  .train-btn {
    width: 100%;
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
  }

  .importance-chart {
    height: 400px;
    margin-top: 1rem;
  }

  .history-empty {
    margin-top: 1rem;
  }

  @media (max-width: 1100px) {
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
  }
</style>
