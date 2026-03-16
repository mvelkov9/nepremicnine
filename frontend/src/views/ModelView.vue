<script setup>
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import ProgressBar from 'primevue/progressbar'
  import Tag from 'primevue/tag'
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
  const pollTimer = ref(null)

  const isAdmin = computed(() => auth.user?.role === 'admin')
  const trainingDataset = computed(() => dataStore.trainingDataset)
  const isTerminalStatus = (status) => status === 'completed' || status === 'failed'
  const recentJobs = computed(() => model.jobHistory.slice(0, 6))

  const uploadOptions = computed(() =>
    (Array.isArray(dataStore.datasets) ? dataStore.datasets : []).filter(
      (dataset) => dataset.relative_path !== trainingDataset.value?.relative_path,
    ),
  )

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
      }
    }
    return (
      uploadOptions.value.find((dataset) => dataset.relative_path === selectedCsv.value) || null
    )
  })

  const selectedSourcePath = computed(
    () =>
      selectedSourceMeta.value?.relative_path ||
      trainingDataset.value?.relative_path ||
      model.info?.source_csv_path ||
      '',
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
    if (!status) return '—'
    return status
  }

  const metricsCards = computed(() => {
    const metrics = model.info?.global_metrics
    if (!metrics) return []
    return [
      { label: 'MAE', value: fmtCurrency(metrics.mae) },
      { label: 'RMSE', value: fmtCurrency(metrics.rmse) },
      { label: 'R²', value: formatScore(metrics.r2) },
      { label: 'MAPE', value: fmtPercent(metrics.mape) },
      {
        label: t('model.medianError'),
        value: fmtCurrency(metrics.median_ae),
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
          backgroundColor: '#2563eb',
          borderRadius: 8,
        },
      ],
    }
  })

  const importanceOptions = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { x: { beginAtZero: true } },
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

  async function train() {
    if (!selectedCsv.value) return
    const result = await model.startTraining(selectedCsv.value)
    await model.fetchJobs()
    if (result?.job_id) {
      startPolling(result.job_id)
    }
  }

  async function refreshModelArtifacts() {
    await Promise.all([
      model.fetchInfo(),
      model.fetchImportance(),
      model.fetchDiagnostics(),
      dataStore.fetchTrainingDataset(),
    ])
  }

  function stopPolling() {
    if (pollTimer.value) {
      clearInterval(pollTimer.value)
      pollTimer.value = null
    }
  }

  function startPolling(jobId) {
    stopPolling()

    pollTimer.value = setInterval(async () => {
      const status = await model.pollStatus(jobId)
      if (!status || isTerminalStatus(status.status)) {
        stopPolling()
        if (status?.status === 'completed') {
          await Promise.all([refreshModelArtifacts(), model.fetchJobs()])
        } else {
          await model.fetchJobs()
        }
      }
    }, 2000)
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
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
    ])
    await syncExistingTraining()
  })

  onUnmounted(() => {
    stopPolling()
  })
</script>

<template>
  <div>
    <div v-if="isAdmin" class="card training-hero">
      <div class="training-hero-copy">
        <span class="eyebrow">{{ t('model.trainModel') }}</span>
        <h2>{{ t('model.trainingTitle') }}</h2>
        <p>{{ t('model.trainingBody') }}</p>
      </div>

      <div class="training-hero-status">
        <article class="mini-status-card" :class="{ ready: trainingDataset?.exists }">
          <span class="eyebrow">{{ t('model.preparedDataset') }}</span>
          <strong>{{
            trainingDataset?.exists
              ? t('model.preparedDatasetReady')
              : t('model.preparedDatasetMissing')
          }}</strong>
          <p v-if="trainingDataset?.exists">
            {{ fmt(trainingDataset.rows) }} {{ t('data.rows') }} ·
            {{ formatDate(trainingDataset.updated_at) }}
          </p>
          <p v-else>{{ t('model.prepareDataFirst') }}</p>
        </article>

        <article class="mini-status-card" :class="{ ready: !!model.info }">
          <span class="eyebrow">{{ t('model.currentModel') }}</span>
          <strong>{{ model.info ? t('model.modelReady') : t('model.modelMissing') }}</strong>
          <p v-if="model.info">
            {{ formatDate(model.info.trained_at) }} · {{ fmt(model.info.rows) }}
            {{ t('data.rows') }}
          </p>
          <p v-else>{{ t('model.noModel') }}</p>
        </article>
      </div>
    </div>

    <div v-if="isAdmin" class="card" style="margin-bottom: 1.5rem">
      <div class="section-head">
        <div>
          <div class="card-title">{{ t('model.selectDataset') }}</div>
          <p class="muted">{{ t('model.selectSourceHint') }}</p>
        </div>
        <RouterLink v-if="!trainingDataset?.exists" to="/priprava" class="ghost-link">
          {{ t('model.goToPrepare') }}
        </RouterLink>
      </div>

      <div class="source-stack">
        <label
          class="source-option"
          :class="{ active: selectedCsv === trainingDataset?.relative_path }"
        >
          <input
            v-if="trainingDataset?.exists"
            v-model="selectedCsv"
            type="radio"
            :value="trainingDataset.relative_path"
          />
          <div>
            <strong>{{ t('model.preparedDatasetLabel') }}</strong>
            <p v-if="trainingDataset?.exists">
              {{ trainingDataset.relative_path }} · {{ fmt(trainingDataset.rows) }}
              {{ t('data.rows') }}
            </p>
            <p v-else>{{ t('model.prepareDataFirst') }}</p>
          </div>
          <span v-if="trainingDataset?.exists" class="badge badge-green">{{
            t('model.recommended')
          }}</span>
        </label>

        <div v-if="uploadOptions.length" class="field">
          <label class="form-label">{{ t('model.otherDatasets') }}</label>
          <select v-model="selectedCsv" class="form-input">
            <option value="">{{ t('model.selectDataset') }}</option>
            <option
              v-for="dataset in uploadOptions"
              :key="dataset.id"
              :value="dataset.relative_path"
            >
              {{ dataset.original_name }} ({{ fmt(dataset.row_count) }} {{ t('data.rows') }})
            </option>
          </select>
        </div>
      </div>

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

      <div class="actions">
        <button class="btn btn-primary" :disabled="!selectedCsv || model.training" @click="train">
          {{ model.training ? t('model.training') : t('model.trainButton') }}
        </button>
        <RouterLink v-if="!trainingDataset?.exists" to="/priprava" class="ghost-link">
          {{ t('model.prepareDatasetCta') }}
        </RouterLink>
      </div>

      <div v-if="model.trainingStatus" class="training-progress-card">
        <div class="training-progress-head">
          <div>
            <span class="eyebrow">{{ t('model.trainingStatus') }}</span>
            <strong>{{ jobStatusLabel(model.trainingStatus.status) }}</strong>
          </div>
          <Tag
            :severity="jobSeverity(model.trainingStatus.status)"
            :value="`${model.trainingStatus.progress || 0}%`"
          />
        </div>
        <ProgressBar :value="model.trainingStatus.progress || 0" :showValue="false" />
        <p class="muted">
          {{ model.trainingStatus.stage || t('common.loading') }}
        </p>
        <p v-if="model.trainingStatus.error" class="error-text">
          {{ model.trainingStatus.error }}
        </p>
      </div>

      <p v-if="model.error" class="error-text">{{ model.error }}</p>
    </div>

    <div v-if="model.info" class="card" style="margin-bottom: 1.5rem">
      <div class="section-head">
        <div>
          <h2>{{ t('model.currentModel') }}</h2>
          <p class="muted">
            {{ t('model.trainedAt') }}: {{ formatDate(model.info.trained_at) }} ·
            {{ fmt(model.info.rows) }} {{ t('data.rows') }} ·
            {{ formatDuration(model.info.duration_sec) }}
          </p>
        </div>
        <div class="model-source-pill" v-if="model.info.source_csv_path">
          {{ t('model.currentSource') }}: {{ model.info.source_csv_path }}
        </div>
      </div>

      <div class="kpi-grid" style="margin-top: 1rem">
        <div v-for="card in metricsCards" :key="card.label" class="kpi-card">
          <span class="kpi-label">{{ card.label }}</span>
          <span class="kpi-value">{{ card.value }}</span>
        </div>
      </div>
    </div>

    <div v-if="model.info?.per_type_metrics" class="card" style="margin-bottom: 1.5rem">
      <h2>{{ t('model.perTypeMetrics') }}</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('model.propertyType') }}</th>
              <th>MAE</th>
              <th>RMSE</th>
              <th>R²</th>
              <th>MAPE</th>
              <th>N</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(metrics, propertyType) in model.info.per_type_metrics" :key="propertyType">
              <td>{{ formatType(propertyType) }}</td>
              <td>{{ fmtCurrency(metrics.mae) }}</td>
              <td>{{ fmtCurrency(metrics.rmse) }}</td>
              <td>{{ formatScore(metrics.r2) }}</td>
              <td>{{ fmtPercent(metrics.mape) }}</td>
              <td>{{ fmt(metrics.n_train) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="model.importance.length" class="card">
      <h2>{{ t('model.featureImportance') }}</h2>
      <div style="height: 400px">
        <Bar :data="importanceChart" :options="importanceOptions" />
      </div>
    </div>

    <div v-if="isAdmin" class="card" style="margin-top: 1.5rem">
      <div class="section-head">
        <div>
          <h2>{{ t('model.trainingHistory') }}</h2>
          <p class="muted">{{ t('model.trainingHistoryHint') }}</p>
        </div>
      </div>

      <DataTable
        :value="recentJobs"
        size="small"
        stripedRows
        tableStyle="min-width: 100%"
        responsiveLayout="scroll"
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
          <template #body="{ data }">{{ data.stage || '—' }}</template>
        </Column>
        <Column field="progress" :header="t('model.trainingProgress')">
          <template #body="{ data }">{{ data.progress || 0 }}%</template>
        </Column>
        <Column field="rows" :header="t('data.rows')">
          <template #body="{ data }">{{ fmt(data.rows) }}</template>
        </Column>
        <Column field="duration_sec" :header="t('diag.duration')">
          <template #body="{ data }">{{ formatDuration(data.duration_sec) }}</template>
        </Column>
      </DataTable>

      <p v-if="!model.jobsLoading && !recentJobs.length" class="muted" style="margin-top: 1rem">
        {{ t('model.noTrainingHistory') }}
      </p>
    </div>

    <div v-if="!model.loading && !model.info" class="card empty-card">
      <p class="muted">{{ t('model.noModel') }}</p>
      <RouterLink v-if="isAdmin" to="/priprava" class="ghost-link">
        {{ t('model.prepareDatasetCta') }}
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
  .training-progress-card {
    display: grid;
    gap: 0.75rem;
    margin-top: 1rem;
    padding: 1rem;
    border-radius: 1rem;
    background: var(--surface-muted);
    border: 1px solid var(--border);
  }

  .training-progress-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .training-progress-head strong {
    display: block;
    margin-top: 0.2rem;
  }
</style>
