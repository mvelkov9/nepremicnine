<script setup>
  import { ref, onMounted, computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import {
    Chart as ChartJS,
    BarElement,
    CategoryScale,
    LinearScale,
    Tooltip,
    Legend,
  } from 'chart.js'
  import { useModelStore } from '../stores/model'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

  const { t } = useI18n()
  const model = useModelStore()

  const selectedMetric = ref('r2')
  const metrics = ['mae', 'rmse', 'r2', 'mape', 'median_ae']

  const perTypeChart = computed(() => {
    const ptm = model.info?.per_type_metrics
    if (!ptm) return null
    const labels = Object.keys(ptm)
    const data = labels.map((k) => ptm[k]?.[selectedMetric.value] ?? 0)
    return {
      labels,
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: '#3b82f6',
          borderRadius: 4,
        },
      ],
    }
  })

  const perRegionChart = computed(() => {
    const prm = model.info?.per_region_metrics
    if (!prm) return null
    const labels = Object.keys(prm)
    const data = labels.map((k) => prm[k]?.[selectedMetric.value] ?? 0)
    return {
      labels,
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: '#22c55e',
          borderRadius: 4,
        },
      ],
    }
  })

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } },
  }

  const globalMetrics = computed(() => {
    const m = model.info?.global_metrics
    if (!m) return []
    return [
      { label: 'MAE', value: `€${Math.round(m.mae).toLocaleString()}`, desc: t('diag.maeDesc') },
      { label: 'RMSE', value: `€${Math.round(m.rmse).toLocaleString()}`, desc: t('diag.rmseDesc') },
      { label: 'R²', value: m.r2?.toFixed(4), desc: t('diag.r2Desc') },
      { label: 'MAPE', value: `${m.mape?.toFixed(1)}%`, desc: t('diag.mapeDesc') },
      {
        label: t('diag.medianError'),
        value: `€${Math.round(m.median_ae).toLocaleString()}`,
        desc: t('diag.medianDesc'),
      },
    ]
  })

  onMounted(async () => {
    await model.fetchInfo()
  })
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.diagnostics') }}</h1>

    <div v-if="!model.info" class="card">
      <p class="muted">{{ t('diag.noModel') }}</p>
    </div>

    <template v-else>
      <!-- Global metrics -->
      <div class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.globalMetrics') }}</h2>
        <div class="kpi-grid" style="margin-top: 1rem">
          <div v-for="m in globalMetrics" :key="m.label" class="kpi-card">
            <span class="kpi-label">{{ m.label }}</span>
            <span class="kpi-value">{{ m.value }}</span>
            <span class="muted" style="font-size: 11px">{{ m.desc }}</span>
          </div>
        </div>
      </div>

      <!-- Model info -->
      <div class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.modelDetails') }}</h2>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr>
                <td class="muted">{{ t('diag.version') }}</td>
                <td>{{ model.info.version }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.trainedAt') }}</td>
                <td>{{ new Date(model.info.trained_at).toLocaleString() }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.rows') }}</td>
                <td>{{ model.info.rows?.toLocaleString() }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.duration') }}</td>
                <td>{{ model.info.duration_sec?.toFixed(1) }}s</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.perTypeModels') }}</td>
                <td>{{ model.info.per_type_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Metric selector -->
      <div class="card" style="margin-bottom: 1.5rem">
        <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem">
          <h2 style="margin: 0">{{ t('diag.compareMetrics') }}</h2>
          <select v-model="selectedMetric" class="form-input" style="width: auto; min-width: 120px">
            <option v-for="m in metrics" :key="m" :value="m">{{ m.toUpperCase() }}</option>
          </select>
        </div>

        <!-- Per-type chart -->
        <div v-if="perTypeChart" style="margin-bottom: 2rem">
          <h3>{{ t('diag.byPropertyType') }}</h3>
          <div style="height: 300px">
            <Bar :data="perTypeChart" :options="chartOptions" />
          </div>
        </div>

        <!-- Per-region chart -->
        <div v-if="perRegionChart">
          <h3>{{ t('diag.byRegion') }}</h3>
          <div style="height: 300px">
            <Bar :data="perRegionChart" :options="chartOptions" />
          </div>
        </div>
      </div>

      <!-- Per-type table -->
      <div v-if="model.info.per_type_metrics" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.perTypeTable') }}</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{{ t('diag.type') }}</th>
                <th>MAE</th>
                <th>RMSE</th>
                <th>R²</th>
                <th>MAPE</th>
                <th>{{ t('diag.trainSamples') }}</th>
                <th>{{ t('diag.testSamples') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, ptype) in model.info.per_type_metrics" :key="ptype">
                <td>{{ ptype }}</td>
                <td>€{{ Math.round(m.mae).toLocaleString() }}</td>
                <td>€{{ Math.round(m.rmse).toLocaleString() }}</td>
                <td
                  :class="{
                    'badge-green': m.r2 > 0.7,
                    'badge-yellow': m.r2 > 0.4 && m.r2 <= 0.7,
                    'badge-red': m.r2 <= 0.4,
                  }"
                >
                  {{ m.r2?.toFixed(4) }}
                </td>
                <td>{{ m.mape?.toFixed(1) }}%</td>
                <td>{{ m.n_train?.toLocaleString() }}</td>
                <td>{{ m.n_test?.toLocaleString() }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Per-region table -->
      <div v-if="model.info.per_region_metrics" class="card">
        <h2>{{ t('diag.perRegionTable') }}</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{{ t('diag.region') }}</th>
                <th>MAE</th>
                <th>RMSE</th>
                <th>R²</th>
                <th>MAPE</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(m, region) in model.info.per_region_metrics" :key="region">
                <td>{{ region }}</td>
                <td>€{{ Math.round(m.mae).toLocaleString() }}</td>
                <td>€{{ Math.round(m.rmse).toLocaleString() }}</td>
                <td>{{ m.r2?.toFixed(4) }}</td>
                <td>{{ m.mape?.toFixed(1) }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
