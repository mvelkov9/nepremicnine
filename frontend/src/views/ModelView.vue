<script setup lang="ts">
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import ProgressBar from 'primevue/progressbar'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import AdminRunDetailPanel from '../components/admin/AdminRunDetailPanel.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useWorkbenchStore } from '../stores/workbench'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const model = useModelStore()
  const workbench = useWorkbenchStore()

  const selectedCsv = ref('')
  const pollTimer = ref(null)
  const selectedTrainingRunId = ref('')

  const isAdmin = computed(() => auth.user?.role === 'admin')
  const trainingDataset = computed(() => dataStore.trainingDataset)
  const recentJobs = computed(() => model.jobHistory.slice(0, 6))
  const recentRuns = computed(() => model.modelRuns.slice(0, 6))
  const trainingLocked = computed(() => model.training)
  const selectedTrainingRun = computed(() => workbench.selectedTrainingRun)

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

  const heroSummaryCards = computed(() => [
    {
      label: t('model.preparedDataset'),
      value: trainingDataset.value?.exists
        ? t('model.preparedDatasetReady')
        : t('model.preparedDatasetMissing'),
      meta: trainingDataset.value?.exists
        ? `${fmt(trainingDataset.value.rows)} ${t('data.rows')}`
        : t('model.prepareDataFirst'),
      tone: (trainingDataset.value?.exists ? 'success' : 'warning') as 'success' | 'warning',
    },
    {
      label: t('model.currentModel'),
      value: model.info ? t('model.modelReady') : t('model.modelMissing'),
      meta: model.info?.trained_at ? formatDate(model.info.trained_at) : t('model.noModel'),
      tone: (model.info ? 'success' : 'warning') as 'success' | 'warning',
    },
    {
      label: t('model.trainingStatus'),
      value: activeStatus.value ? jobStatusLabel(activeStatus.value.status) : t('common.noData'),
      meta: activeStatus.value ? trainingStageLabel.value : t('model.trainingCtaHint'),
    },
    {
      label: t('model.trainingProgress'),
      value: activeStatus.value ? `${activeStatus.value.progress || 0}%` : '0%',
      meta:
        activeStatus.value?.eta_sec != null
          ? `${t('model.eta')}: ${formatDuration(activeStatus.value.eta_sec)}`
          : t('common.noData'),
    },
  ])

  function getChartColors() {
    const style = getComputedStyle(document.documentElement)
    return {
      bar: style.getPropertyValue('--primary').trim() || '#2d8479',
      tick: style.getPropertyValue('--text-soft').trim() || '#94a3b8',
    }
  }

  const importanceChart = computed(() => {
    const items = model.importance.slice(0, 15)
    const colors = getChartColors()
    return {
      labels: items.map((item) => item.label),
      datasets: [
        {
          label: t('model.importance'),
          data: items.map((item) => item.importance),
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
      if (dataset?.exists && !selectedCsv.value) {
        selectedCsv.value = dataset.relative_path
      }
    },
    { immediate: true },
  )

  watch(
    () => workbench.trainingRuns,
    (runs) => {
      if (!runs.length || selectedTrainingRunId.value) return
      selectedTrainingRunId.value = runs[0].id
      void loadTrainingRunDetail(runs[0].id)
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

  async function loadTrainingRunDetail(jobId) {
    selectedTrainingRunId.value = jobId
    await workbench.fetchTrainingRunDetail(jobId)
  }

  async function train() {
    if (!selectedCsv.value || trainingLocked.value) return
    const result = await model.startTraining(selectedCsv.value)
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

  onMounted(async () => {
    await Promise.all([
      model.fetchInfo(),
      model.fetchImportance(),
      model.fetchDiagnostics(),
      model.fetchJobs(),
      model.fetchRuns(),
      dataStore.fetchDatasets(false, true, { perPage: 200 }),
      dataStore.fetchTrainingDataset(),
      workbench.fetchTrainingRuns(),
    ])
    await syncExistingTraining()
  })

  onUnmounted(() => {
    stopPolling()
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
        <RouterLink v-if="!trainingDataset?.exists" to="/admin/priprava">
          <Button
            severity="contrast"
            outlined
            icon="pi pi-arrow-right"
            :label="t('model.goToPrepare')"
          />
        </RouterLink>
      </template>
    </AdminWorkspaceHero>

    <div v-if="false" class="hero-grid">
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
          <Tag v-if="model.info.source_csv_path" severity="secondary">
            {{ t('model.currentSource') }}: {{ model.info.source_csv_path }}
          </Tag>
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

      <DataTable
        :value="
          Object.entries(model.info.per_type_metrics).map(([propertyType, metrics]) => ({
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
              <Tag :severity="jobSeverity(data.status)" :value="jobStatusLabel(data.status)" />
            </template>
          </Column>
          <Column field="stage" :header="t('model.trainingStage')">
            <template #body="{ data }">{{ stageLabel(data.stage) }}</template>
          </Column>
          <Column field="progress" :header="t('model.trainingProgress')">
            <template #body="{ data }">{{ data.progress || 0 }}%</template>
          </Column>
          <Column field="current_model" :header="t('model.currentModel')">
            <template #body="{ data }">
              {{
                data.current_model === 'global'
                  ? t('model.globalModel')
                  : formatType(data.current_model) || '—'
              }}
            </template>
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
      </article>

      <article class="card">
        <PageHeader
          compact
          :eyebrow="t('model.completedRuns')"
          :title="t('model.completedRunsTitle')"
          :description="t('model.completedRunsHint')"
        />

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
      </article>
    </section>

    <AdminRunDetailPanel
      v-if="isAdmin"
      :eyebrow="t('nav.model')"
      :title="t('workbench.recentTrainingRuns')"
      :description="t('workbench.trainingRunDetailHint')"
      :runs="workbench.trainingRuns.slice(0, 8)"
      :selected-run="selectedTrainingRun"
      @select="loadTrainingRunDetail"
    />

    <div v-if="!model.loading && !model.info" class="card empty-card">
      <p class="muted">{{ t('model.noModel') }}</p>
      <RouterLink v-if="isAdmin" to="/admin/priprava" style="text-decoration: none">
        <Button
          severity="secondary"
          text
          icon="pi pi-arrow-right"
          :label="t('model.prepareDatasetCta')"
        />
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
    background: linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft));
    padding: 1rem;
    box-shadow: var(--shadow-sm);
  }

  .action-panel {
    display: grid;
    align-content: start;
    gap: 0.85rem;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 70%, transparent),
        var(--surface-soft)
      ),
      var(--surface-soft);
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
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 1rem;
    background: color-mix(in srgb, var(--surface-strong) 76%, white 24%);
  }

  .selected-source-card strong {
    display: block;
    margin-bottom: 0.4rem;
    font-size: 1rem;
  }

  .selected-source-card p {
    margin: 0.15rem 0 0;
  }

  .live-progress {
    margin-top: 1rem;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--warning-overlay) 68%, transparent),
        var(--surface-soft)
      ),
      var(--surface-soft);
  }

  .importance-chart {
    height: 400px;
    margin-top: 1rem;
  }

  .history-empty {
    margin-top: 1rem;
  }

  .history-grid > .card {
    background: linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft));
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
