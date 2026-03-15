<script setup>
  import { ref, onMounted, computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip } from 'chart.js'
  import { useModelStore } from '../stores/model'
  import { useDataStore } from '../stores/data'
  import { useAuthStore } from '../stores/auth'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

  const { t } = useI18n()
  const model = useModelStore()
  const data = useDataStore()
  const auth = useAuthStore()

  const selectedCsv = ref('')
  const pollTimer = ref(null)

  const isAdmin = computed(() => auth.user?.role === 'admin')

  const metricsCards = computed(() => {
    const m = model.info?.global_metrics
    if (!m) return []
    return [
      { label: 'MAE', value: `€${Math.round(m.mae).toLocaleString()}` },
      { label: 'RMSE', value: `€${Math.round(m.rmse).toLocaleString()}` },
      { label: 'R²', value: m.r2?.toFixed(4) },
      { label: 'MAPE', value: `${m.mape?.toFixed(1)}%` },
      { label: t('model.medianError'), value: `€${Math.round(m.median_ae).toLocaleString()}` },
    ]
  })

  const importanceChart = computed(() => {
    const items = model.importance.slice(0, 15)
    return {
      labels: items.map((i) => i.label),
      datasets: [
        {
          label: t('model.importance'),
          data: items.map((i) => i.importance),
          backgroundColor: '#3b82f6',
          borderRadius: 4,
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
            await model.fetchInfo()
            await model.fetchImportance()
          }
        }
      }, 2000)
    }
  }

  onMounted(async () => {
    await Promise.all([model.fetchInfo(), model.fetchImportance(), data.fetchDatasets()])
  })
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.model') }}</h1>

    <!-- Training section (admin only) -->
    <div v-if="isAdmin" class="card" style="margin-bottom: 1.5rem">
      <h2>{{ t('model.trainModel') }}</h2>
      <div style="display: flex; gap: 1rem; align-items: end; flex-wrap: wrap">
        <div style="flex: 1; min-width: 250px">
          <label class="form-label">{{ t('model.selectDataset') }}</label>
          <select v-model="selectedCsv" class="form-input">
            <option value="">-- {{ t('model.selectDataset') }} --</option>
            <option value="data/raw/train.csv">train.csv (default)</option>
            <option v-for="ds in data.datasets" :key="ds.id" :value="ds.stored_path">
              {{ ds.original_name }} ({{ ds.row_count }} {{ t('data.rows') }})
            </option>
          </select>
        </div>
        <button class="btn btn-primary" :disabled="!selectedCsv || model.training" @click="train">
          {{ model.training ? t('model.training') : t('model.trainButton') }}
        </button>
      </div>

      <!-- Progress -->
      <div v-if="model.trainingStatus" style="margin-top: 1rem">
        <div class="progress-bar">
          <div
            class="progress-bar-fill"
            :style="{ width: (model.trainingStatus.progress || 0) + '%' }"
          />
        </div>
        <p class="muted" style="margin-top: 0.5rem">
          {{ model.trainingStatus.status }} — {{ model.trainingStatus.stage || '' }} ({{
            model.trainingStatus.progress || 0
          }}%)
        </p>
      </div>

      <p v-if="model.error" class="error-text">{{ model.error }}</p>
    </div>

    <!-- Model info -->
    <div v-if="model.info" class="card" style="margin-bottom: 1.5rem">
      <h2>{{ t('model.currentModel') }}</h2>
      <p class="muted">
        {{ t('model.trainedAt') }}: {{ new Date(model.info.trained_at).toLocaleString() }} ·
        {{ model.info.rows?.toLocaleString() }} {{ t('data.rows') }} ·
        {{ model.info.duration_sec?.toFixed(1) }}s · {{ model.info.per_type_count }}
        {{ t('model.perTypeModels') }}
      </p>

      <!-- Metrics cards -->
      <div class="kpi-grid" style="margin-top: 1rem">
        <div v-for="card in metricsCards" :key="card.label" class="kpi-card">
          <span class="kpi-label">{{ card.label }}</span>
          <span class="kpi-value">{{ card.value }}</span>
        </div>
      </div>
    </div>

    <!-- Per-type metrics -->
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
            <tr v-for="(metrics, ptype) in model.info.per_type_metrics" :key="ptype">
              <td>{{ ptype }}</td>
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

    <!-- Feature importance chart -->
    <div v-if="model.importance.length" class="card">
      <h2>{{ t('model.featureImportance') }}</h2>
      <div style="height: 400px">
        <Bar :data="importanceChart" :options="importanceOptions" />
      </div>
    </div>

    <!-- No model -->
    <div v-if="!model.loading && !model.info" class="card">
      <p class="muted">{{ t('model.noModel') }}</p>
    </div>
  </div>
</template>
