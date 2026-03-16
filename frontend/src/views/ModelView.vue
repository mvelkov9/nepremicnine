<script setup>
  import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

  const { t } = useI18n()
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const model = useModelStore()

  const selectedCsv = ref('')
  const pollTimer = ref(null)

  const isAdmin = computed(() => auth.user?.role === 'admin')
  const trainingDataset = computed(() => dataStore.trainingDataset)

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

  const metricsCards = computed(() => {
    const metrics = model.info?.global_metrics
    if (!metrics) return []
    return [
      { label: 'MAE', value: `€${Math.round(metrics.mae).toLocaleString()}` },
      { label: 'RMSE', value: `€${Math.round(metrics.rmse).toLocaleString()}` },
      { label: 'R²', value: metrics.r2?.toFixed(4) },
      { label: 'MAPE', value: `${metrics.mape?.toFixed(1)}%` },
      {
        label: t('model.medianError'),
        value: `€${Math.round(metrics.median_ae).toLocaleString()}`,
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
          backgroundColor: '#0f766e',
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
    if (result?.job_id) {
      pollTimer.value = setInterval(async () => {
        const status = await model.pollStatus(result.job_id)
        if (!status || status.status === 'completed' || status.status === 'failed') {
          clearInterval(pollTimer.value)
          pollTimer.value = null
          if (status?.status === 'completed') {
            await Promise.all([
              model.fetchInfo(),
              model.fetchImportance(),
              model.fetchDiagnostics(),
              dataStore.fetchTrainingDataset(),
            ])
          }
        }
      }, 2000)
    }
  }

  function formatDate(value) {
    if (!value) return t('common.noData')
    return new Date(value).toLocaleString()
  }

  onMounted(async () => {
    await Promise.all([
      model.fetchInfo(),
      model.fetchImportance(),
      model.fetchDiagnostics(),
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
    ])
  })

  onUnmounted(() => {
    if (pollTimer.value) {
      clearInterval(pollTimer.value)
      pollTimer.value = null
    }
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
            {{ trainingDataset.rows?.toLocaleString() || 0 }} {{ t('data.rows') }} ·
            {{ formatDate(trainingDataset.updated_at) }}
          </p>
          <p v-else>{{ t('model.prepareDataFirst') }}</p>
        </article>

        <article class="mini-status-card" :class="{ ready: !!model.info }">
          <span class="eyebrow">{{ t('model.currentModel') }}</span>
          <strong>{{ model.info ? t('model.modelReady') : t('model.modelMissing') }}</strong>
          <p v-if="model.info">
            {{ formatDate(model.info.trained_at) }} · {{ model.info.rows?.toLocaleString() || 0 }}
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
              {{ trainingDataset.relative_path }} ·
              {{ trainingDataset.rows?.toLocaleString() || 0 }}
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
              {{ dataset.original_name }} ({{ dataset.row_count?.toLocaleString() ?? 0 }}
              {{ t('data.rows') }})
            </option>
          </select>
        </div>
      </div>

      <div v-if="selectedSourceMeta" class="selected-source-card">
        <span class="eyebrow">{{ t('model.selectedSource') }}</span>
        <strong>{{ selectedSourceMeta.original_name || selectedSourceMeta.name }}</strong>
        <p>{{ selectedSourcePath }}</p>
        <p class="muted">
          {{ selectedSourceMeta.row_count || selectedSourceMeta.rows || 0 }} {{ t('data.rows') }} ·
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

      <div v-if="model.trainingStatus" style="margin-top: 1rem">
        <div
          class="progress-bar"
          role="progressbar"
          :aria-valuenow="model.trainingStatus.progress || 0"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <div
            class="progress-bar-fill"
            :style="{ width: `${model.trainingStatus.progress || 0}%` }"
          />
        </div>
        <p class="muted" style="margin-top: 0.5rem">
          {{ model.trainingStatus.status }} ·
          {{ model.trainingStatus.stage || t('common.loading') }} ({{
            model.trainingStatus.progress || 0
          }}%)
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
            {{ model.info.rows?.toLocaleString() }} {{ t('data.rows') }} ·
            {{ model.info.duration_sec?.toFixed(1) }}s
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
              <td>{{ propertyType }}</td>
              <td>€{{ Math.round(metrics.mae).toLocaleString() }}</td>
              <td>€{{ Math.round(metrics.rmse).toLocaleString() }}</td>
              <td>{{ metrics.r2?.toFixed(4) }}</td>
              <td>{{ metrics.mape?.toFixed(1) }}%</td>
              <td>{{ metrics.n_train }}</td>
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

    <div v-if="!model.loading && !model.info" class="card empty-card">
      <p class="muted">{{ t('model.noModel') }}</p>
      <RouterLink v-if="isAdmin" to="/priprava" class="ghost-link">
        {{ t('model.prepareDatasetCta') }}
      </RouterLink>
    </div>
  </div>
</template>
