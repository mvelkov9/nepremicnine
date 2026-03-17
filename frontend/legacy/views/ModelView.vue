<script setup>
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
  import { useIntervalFn, useMutationObserver } from '@vueuse/core'
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
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
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

  const selectedCsv = ref('')
  const activeJobId = ref(null)
  let stopThemeObserver = () => {}

  const isAdmin = computed(() => auth.user?.role === 'admin')
  const trainingDataset = computed(() => dataStore.trainingDataset)
  const recentJobs = computed(() => model.jobHistory.slice(0, 6))
  const recentRuns = computed(() => model.modelRuns.slice(0, 6))
  const latestRun = computed(() => recentRuns.value[0] || null)
  const trainingLocked = computed(() => model.training)

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
  const heroStoryCards = computed(() => [
    {
      label: t('model.currentModel'),
      value: model.info ? t('model.modelReady') : t('model.modelMissing'),
      meta: model.info
        ? `${formatDate(model.info.trained_at)} · ${fmt(model.info.rows)} ${t('data.rows')}`
        : t('model.noModel'),
      tone: model.info ? 'success' : 'warning',
    },
    {
      label: t('model.currentSource'),
      value: model.info?.source_csv_path || selectedSourcePath.value || t('common.noData'),
      meta: selectedSourceMeta.value
        ? `${fmt(selectedSourceMeta.value.row_count || selectedSourceMeta.value.rows || 0)} ${t('data.rows')} · ${formatDate(selectedSourceMeta.value.uploaded_at || selectedSourceMeta.value.updated_at)}`
        : t('model.selectSourceHint'),
      tone: selectedSourcePath.value ? 'default' : 'warning',
    },
    {
      label: t('model.completedRuns'),
      value: fmt(model.modelRuns.length),
      meta: latestRun.value
        ? `${fmtCurrency(latestRun.value.mae)} MAE · ${formatDate(latestRun.value.created_at)}`
        : t('model.noCompletedRuns'),
      tone: latestRun.value ? 'success' : 'default',
    },
  ])
  const launchChecklist = computed(() => [
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
        : model.info
          ? t('model.modelReady')
          : t('model.modelMissing'),
      meta: activeStatus.value ? trainingStageLabel.value : t('model.trainingCtaHint'),
      tone: activeStatus.value ? 'warning' : model.info ? 'success' : 'default',
    },
    {
      label: t('model.completedRuns'),
      value: fmt(recentRuns.value.length),
      meta: latestRun.value
        ? `${fmtCurrency(latestRun.value.rmse)} RMSE · ${formatDuration(latestRun.value.duration_sec)}`
        : t('model.noCompletedRuns'),
      tone: latestRun.value ? 'success' : 'default',
    },
  ])
  const featureHighlights = computed(() => {
    const items = model.importance.slice(0, 5)
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
    const items = model.importance.slice(0, 15)
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
    indexAxis: 'y',
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

  function readCssColor(variable, fallback) {
    if (typeof window === 'undefined') return fallback
    const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim()
    return value || fallback
  }

  function syncChartPalette() {
    chartPalette.value = {
      primary: readCssColor('--ui-primary', chartPalette.value.primary),
      muted: readCssColor('--ui-text-muted', chartPalette.value.muted),
      grid: readCssColor('--ui-border', chartPalette.value.grid),
    }
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

  const { pause: pausePolling, resume: resumePolling } = useIntervalFn(
    async () => {
      if (!activeJobId.value) return

      const status = await model.pollStatus(activeJobId.value)
      if (!status || isTerminalStatus(status.status)) {
        stopPolling()
        await refreshModelArtifacts()
      }
    },
    1800,
    { immediate: false },
  )

  function stopPolling() {
    activeJobId.value = null
    pausePolling()
  }

  function isTerminalStatus(status) {
    return status === 'completed' || status === 'failed'
  }

  function startPolling(jobId) {
    stopPolling()
    activeJobId.value = jobId
    resumePolling()
  }

  async function syncExistingTraining() {
    const activeJob = await model.fetchActiveTraining()
    if (activeJob?.job_id && !isTerminalStatus(activeJob.status)) {
      startPolling(activeJob.job_id)
    }
  }

  onMounted(async () => {
    syncChartPalette()
    if (typeof window !== 'undefined') {
      const observer = useMutationObserver(document.documentElement, syncChartPalette, {
        attributes: true,
        attributeFilter: ['class', 'style'],
      })
      stopThemeObserver = observer.stop
    }
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
  })

  onUnmounted(() => {
    stopPolling()
    stopThemeObserver()
  })
</script>

<template>
  <div class="model-page">
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

        <article class="hero-spotlight">
          <div class="spotlight-head">
            <span class="eyebrow">
              {{ activeStatus ? t('model.trainingStatus') : t('model.currentSource') }}
            </span>
            <Tag
              :severity="
                activeStatus
                  ? jobSeverity(activeStatus.status)
                  : model.info
                    ? 'success'
                    : 'secondary'
              "
              :value="
                activeStatus
                  ? jobStatusLabel(activeStatus.status)
                  : model.info
                    ? t('model.modelReady')
                    : t('model.modelMissing')
              "
            />
          </div>

          <h2>
            {{
              activeStatus
                ? trainingStageLabel
                : selectedSourceMeta?.original_name ||
                  selectedSourceMeta?.name ||
                  model.info?.source_csv_path ||
                  t('common.noData')
            }}
          </h2>
          <p>
            {{
              activeStatus
                ? `${activeStatus.progress || 0}% · ${activeModelLabel}`
                : selectedSourcePath || t('model.selectSourceHint')
            }}
          </p>

          <div class="spotlight-meta">
            <span>
              {{
                activeStatus
                  ? `${t('model.elapsed')}: ${formatDuration(activeStatus.elapsed_sec)}`
                  : `${fmt(selectedSourceMeta?.row_count || selectedSourceMeta?.rows || model.info?.rows || 0)} ${t('data.rows')}`
              }}
            </span>
            <span>
              {{
                activeStatus?.eta_sec != null
                  ? `${t('model.eta')}: ${formatDuration(activeStatus.eta_sec)}`
                  : formatDate(
                      selectedSourceMeta?.uploaded_at ||
                        selectedSourceMeta?.updated_at ||
                        model.info?.trained_at,
                    )
              }}
            </span>
          </div>
        </article>
      </div>
    </section>

    <section v-if="isAdmin" class="card training-workbench">
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

      <div class="snapshot-shell">
        <div class="hero-grid compact">
          <MetricCard
            v-for="card in metricsCards"
            :key="card.label"
            :label="card.label"
            :value="card.value"
          />
        </div>

        <article class="snapshot-spotlight">
          <span class="eyebrow">{{ t('model.completedRuns') }}</span>
          <h2>{{ latestRun ? formatDate(latestRun.created_at) : t('model.noCompletedRuns') }}</h2>
          <p>
            {{
              latestRun
                ? `${latestRun.source_csv_path} · ${fmt(latestRun.rows)} ${t('data.rows')}`
                : t('model.completedRunsHint')
            }}
          </p>

          <div class="snapshot-meta">
            <span>MAE · {{ latestRun ? fmtCurrency(latestRun.mae) : '—' }}</span>
            <span>RMSE · {{ latestRun ? fmtCurrency(latestRun.rmse) : '—' }}</span>
            <span>MAPE · {{ latestRun ? fmtPercent(latestRun.mape) : '—' }}</span>
          </div>
        </article>
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
            ...metrics,
          }))
        "
        size="small"
        striped-rows
        table-style="min-width: 100%"
      >
        <Column field="propertyType" :header="t('model.propertyType')">
          <template #body="{ data }">{{ formatType(data.propertyType) }}</template>
        </Column>
        <Column field="mae" header="MAE">
          <template #body="{ data }">{{ fmtCurrency(data.mae) }}</template>
        </Column>
        <Column field="rmse" header="RMSE">
          <template #body="{ data }">{{ fmtCurrency(data.rmse) }}</template>
        </Column>
        <Column field="r2" header="R²">
          <template #body="{ data }">{{ formatScore(data.r2) }}</template>
        </Column>
        <Column field="mape" header="MAPE">
          <template #body="{ data }">{{ fmtPercent(data.mape) }}</template>
        </Column>
        <Column field="n_train" header="N">
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

      <div class="importance-shell">
        <div class="importance-chart">
          <Bar :data="importanceChart" :options="importanceOptions" />
        </div>

        <article class="focus-card">
          <span class="eyebrow">{{ t('model.featureImportance') }}</span>
          <h2>{{ featureHighlights[0]?.label || t('common.noData') }}</h2>
          <p>
            {{
              featureHighlights[0]
                ? `${fmt(featureHighlights[0].importance, 3)} · ${t('model.importance')}`
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
                <span :style="{ width: `${Math.max(10, item.share)}%` }"></span>
              </span>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section v-if="isAdmin" class="history-grid">
      <article class="card history-panel">
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

      <article class="card history-panel">
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

    <div v-if="!model.loading && !model.info" class="card empty-card">
      <p class="muted">{{ t('model.noModel') }}</p>
      <RouterLink v-if="isAdmin" to="/admin/priprava" class="ghost-link">
        {{ t('model.prepareDatasetCta') }}
      </RouterLink>
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

  .story-card,
  .launch-card,
  .hero-spotlight,
  .focus-card,
  .snapshot-spotlight {
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
  .hero-spotlight h2,
  .focus-card h2,
  .snapshot-spotlight h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.2rem, 2vw, 1.95rem);
    line-height: 1.02;
    letter-spacing: -0.045em;
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
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

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

  .snapshot-shell {
    grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
    margin-top: 1rem;
  }

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

  .history-empty {
    margin-top: 1rem;
  }

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
    .live-progress-head {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
