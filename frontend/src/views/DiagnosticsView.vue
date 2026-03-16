<script setup>
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import {
    BarElement,
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    Tooltip,
  } from 'chart.js'
  import EmptyState from '../components/EmptyState.vue'
  import { useModelStore } from '../stores/model'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

  const { t } = useI18n()
  const model = useModelStore()

  const selectedMetric = ref('r2')
  const selectedType = ref('all')
  const metrics = ['mae', 'rmse', 'r2', 'mape', 'median_ae']

  function formatType(value) {
    return getPropertyTypeLabel(value, t)
  }

  function formatMetric(value, digits = 4) {
    return formatNumber(value, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  }

  function formatDuration(value) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    return `${formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }

  const availableTypes = computed(() => Object.keys(model.info?.per_type_metrics || {}))

  const selectedTypeMetrics = computed(() => {
    if (selectedType.value === 'all') return model.info?.global_metrics || null
    return model.info?.per_type_metrics?.[selectedType.value] || null
  })

  const focusMetrics = computed(() => {
    const metricsData = selectedTypeMetrics.value
    if (!metricsData) return []
    return [
      { label: 'MAE', value: formatCurrency(metricsData.mae), desc: t('diag.maeDesc') },
      { label: 'RMSE', value: formatCurrency(metricsData.rmse), desc: t('diag.rmseDesc') },
      { label: 'R²', value: formatMetric(metricsData.r2), desc: t('diag.r2Desc') },
      {
        label: 'MAPE',
        value:
          metricsData.mape == null
            ? '—'
            : formatPercent(metricsData.mape, { scale: 0.01, minimumFractionDigits: 1 }),
        desc: t('diag.mapeDesc'),
      },
      {
        label: t('diag.medianError'),
        value: formatCurrency(metricsData.median_ae),
        desc: t('diag.medianDesc'),
      },
      {
        label: t('diag.trainSamples'),
        value: formatNumber(metricsData.n_train),
        desc:
          selectedType.value === 'all'
            ? t('diag.focusAllDesc')
            : t('diag.focusTypeDesc', { type: formatType(selectedType.value) }),
      },
      {
        label: t('diag.testSamples'),
        value: formatNumber(metricsData.n_test),
        desc: t('diag.testRows'),
      },
    ]
  })

  const featureHighlights = computed(() => model.importance.slice(0, 8))

  const perTypeChart = computed(() => {
    const ptm = model.info?.per_type_metrics
    if (!ptm) return null
    const labels = Object.keys(ptm)
    const data = labels.map((k) => ptm[k]?.[selectedMetric.value] ?? 0)
    return {
      labels: labels.map((label) => formatType(label)),
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: labels.map((label) =>
            selectedType.value === 'all' || selectedType.value === label ? '#2563eb' : '#bfdbfe',
          ),
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

  const combinedMetrics = computed(() => {
    const metricsData = model.diagnostics?.combined_metrics
    if (!metricsData) return []
    return [
      { label: 'MAE', value: formatCurrency(metricsData.mae) },
      { label: 'RMSE', value: formatCurrency(metricsData.rmse) },
      { label: 'R²', value: formatMetric(metricsData.r2) },
      {
        label: 'MAPE',
        value:
          metricsData.mape == null
            ? '—'
            : formatPercent(metricsData.mape, { scale: 0.01, minimumFractionDigits: 1 }),
      },
      { label: t('diag.medianError'), value: formatCurrency(metricsData.median_ae) },
    ]
  })

  onMounted(async () => {
    await Promise.all([model.fetchInfo(), model.fetchDiagnostics(), model.fetchImportance()])
  })
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.diagnostics') }}</h1>

    <div v-if="!model.info" class="card">
      <p class="muted">{{ t('diag.noModel') }}</p>
    </div>

    <template v-else>
      <div class="card" style="margin-bottom: 1.5rem">
        <div class="focus-head">
          <div>
            <h2>{{ t('diag.focusType') }}</h2>
            <p class="muted">
              {{
                selectedType === 'all'
                  ? t('diag.focusAllDesc')
                  : t('diag.focusTypeDesc', { type: formatType(selectedType) })
              }}
            </p>
          </div>
          <div class="focus-chips">
            <button
              type="button"
              class="focus-chip"
              :class="{ active: selectedType === 'all' }"
              @click="selectedType = 'all'"
            >
              {{ t('diag.allTypes') }}
            </button>
            <button
              v-for="type in availableTypes"
              :key="type"
              type="button"
              class="focus-chip"
              :class="{ active: selectedType === type }"
              @click="selectedType = type"
            >
              {{ formatType(type) }}
            </button>
          </div>
        </div>

        <div class="kpi-grid" style="margin-top: 1rem">
          <div v-for="item in focusMetrics" :key="item.label" class="kpi-card">
            <span class="kpi-label">{{ item.label }}</span>
            <span class="kpi-value">{{ item.value }}</span>
            <span class="muted" style="font-size: 11px">{{ item.desc }}</span>
          </div>
        </div>
      </div>

      <div v-if="combinedMetrics.length" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.combinedMetrics') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.combinedDesc') }}</p>
        <div class="kpi-grid">
          <div v-for="item in combinedMetrics" :key="item.label" class="kpi-card">
            <span class="kpi-label">{{ item.label }}</span>
            <span class="kpi-value">{{ item.value }}</span>
          </div>
        </div>
      </div>

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
                <td>{{ formatDateTime(model.info.trained_at) }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.rows') }}</td>
                <td>{{ formatNumber(model.info.rows) }}</td>
              </tr>
              <tr v-if="model.diagnostics?.train_rows">
                <td class="muted">{{ t('diag.trainRows') }}</td>
                <td>{{ formatNumber(model.diagnostics.train_rows) }}</td>
              </tr>
              <tr v-if="model.diagnostics?.test_rows">
                <td class="muted">{{ t('diag.testRows') }}</td>
                <td>{{ formatNumber(model.diagnostics.test_rows) }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.duration') }}</td>
                <td>{{ formatDuration(model.info.duration_sec) }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.perTypeModels') }}</td>
                <td>{{ formatNumber(model.info.per_type_count) }}</td>
              </tr>
              <tr v-if="model.diagnostics?.model_type">
                <td class="muted">{{ t('diag.modelType') }}</td>
                <td>{{ model.diagnostics.model_type }}</td>
              </tr>
              <tr v-if="model.diagnostics?.type_models_trained?.length">
                <td class="muted">{{ t('diag.trainedTypes') }}</td>
                <td>
                  {{
                    model.diagnostics.type_models_trained.map((type) => formatType(type)).join(', ')
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card" style="margin-bottom: 1.5rem">
        <div class="focus-head">
          <div>
            <h2 style="margin: 0">{{ t('diag.compareMetrics') }}</h2>
            <p class="muted">{{ t('diag.byPropertyType') }} / {{ t('diag.byRegion') }}</p>
          </div>
          <select v-model="selectedMetric" class="form-input" style="width: auto; min-width: 120px">
            <option v-for="metric in metrics" :key="metric" :value="metric">
              {{ metric.toUpperCase() }}
            </option>
          </select>
        </div>

        <div v-if="perTypeChart" style="margin-bottom: 2rem">
          <h3>{{ t('diag.byPropertyType') }}</h3>
          <div style="height: 300px">
            <Bar :data="perTypeChart" :options="chartOptions" />
          </div>
        </div>

        <div v-if="perRegionChart">
          <h3>{{ t('diag.byRegion') }}</h3>
          <div style="height: 300px">
            <Bar :data="perRegionChart" :options="chartOptions" />
          </div>
        </div>
      </div>

      <div v-if="featureHighlights.length" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.topFeatures') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.topFeaturesDesc') }}</p>
        <div class="feature-list">
          <div v-for="item in featureHighlights" :key="item.feature" class="feature-row">
            <div class="feature-copy">
              <strong>{{ item.label }}</strong>
              <small>{{ item.feature }}</small>
            </div>
            <div class="feature-bar">
              <span :style="{ width: `${Math.max(10, Math.round(item.importance * 100))}%` }" />
            </div>
            <strong>{{ formatMetric(item.importance) }}</strong>
          </div>
        </div>
      </div>

      <div v-if="model.info.per_type_metrics" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.perTypeTable') }}</h2>
        <EmptyState
          v-if="!Object.keys(model.info.per_type_metrics).length"
          icon="📊"
          :message="t('empty.noResults')"
        />
        <div v-else class="table-wrap">
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
              <tr
                v-for="(metricsData, propertyType) in model.info.per_type_metrics"
                :key="propertyType"
                :class="{ 'active-focus-row': selectedType === propertyType }"
              >
                <td>{{ formatType(propertyType) }}</td>
                <td>{{ formatCurrency(metricsData.mae) }}</td>
                <td>{{ formatCurrency(metricsData.rmse) }}</td>
                <td
                  :class="{
                    'badge-green': metricsData.r2 > 0.7,
                    'badge-yellow': metricsData.r2 > 0.4 && metricsData.r2 <= 0.7,
                    'badge-red': metricsData.r2 <= 0.4,
                  }"
                >
                  {{ formatMetric(metricsData.r2) }}
                </td>
                <td>
                  {{
                    metricsData.mape == null
                      ? '—'
                      : formatPercent(metricsData.mape, { scale: 0.01, minimumFractionDigits: 1 })
                  }}
                </td>
                <td>{{ formatNumber(metricsData.n_train) }}</td>
                <td>{{ formatNumber(metricsData.n_test) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="model.info.per_region_metrics" class="card">
        <h2>{{ t('diag.perRegionTable') }}</h2>
        <EmptyState
          v-if="!Object.keys(model.info.per_region_metrics).length"
          icon="🗺️"
          :message="t('empty.noResults')"
        />
        <div v-else class="table-wrap">
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
              <tr v-for="(metricsData, region) in model.info.per_region_metrics" :key="region">
                <td>{{ region }}</td>
                <td>{{ formatCurrency(metricsData.mae) }}</td>
                <td>{{ formatCurrency(metricsData.rmse) }}</td>
                <td>{{ formatMetric(metricsData.r2) }}</td>
                <td>
                  {{
                    metricsData.mape == null
                      ? '—'
                      : formatPercent(metricsData.mape, { scale: 0.01, minimumFractionDigits: 1 })
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
  .focus-head {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .focus-chips {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  .focus-chip {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: rgb(255 255 255 / 78%);
    color: var(--text);
    padding: 0.45rem 0.8rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }

  .focus-chip.active {
    border-color: rgb(37 99 235 / 34%);
    background: linear-gradient(135deg, rgb(37 99 235 / 14%), rgb(245 158 11 / 14%));
    color: var(--primary-strong);
  }

  .feature-list {
    display: grid;
    gap: 0.8rem;
  }

  .feature-row {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(140px, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
  }

  .feature-copy {
    display: grid;
    gap: 0.15rem;
  }

  .feature-copy small {
    color: var(--text-muted);
  }

  .feature-bar {
    height: 0.7rem;
    overflow: hidden;
    border-radius: 999px;
    background: rgb(15 23 42 / 8%);
  }

  .feature-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--primary), #7dd3fc);
  }

  .active-focus-row {
    background: rgb(37 99 235 / 6%);
  }
</style>
