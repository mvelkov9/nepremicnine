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
  import PageHeader from '../components/PageHeader.vue'
  import Select from 'primevue/select'
  import { useModelStore } from '../stores/model'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

  const { t } = useI18n()
  const model = useModelStore()

  const selectedMetric = ref('r2')
  const selectedType = ref('all')
  const metrics = ['mae', 'rmse', 'r2', 'mape', 'median_ae']
  const metricOptions = computed(() =>
    metrics.map((metric) => ({ label: metric.toUpperCase(), value: metric })),
  )

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

  const modelStoryCards = computed(() => {
    if (!model.info) return []

    return [
      {
        label: t('diag.version'),
        value: model.info.version || '—',
        meta: t('diag.modelDetails'),
      },
      {
        label: t('diag.trainedAt'),
        value: formatDateTime(model.info.trained_at),
        meta: formatDuration(model.info.duration_sec),
      },
      {
        label: t('diag.rows'),
        value: formatNumber(model.info.rows),
        meta: t('diag.trainRows'),
      },
      {
        label: t('diag.focusType'),
        value: selectedType.value === 'all' ? t('diag.allTypes') : formatType(selectedType.value),
        meta: selectedMetric.value.toUpperCase(),
      },
    ]
  })

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
  <div class="diagnostics-page">
    <section class="card diagnostics-hero">
      <PageHeader
        :eyebrow="t('nav.diagnostics')"
        :title="t('nav.diagnostics')"
        :description="t('layout.page.diagnostics')"
      />

      <div v-if="model.info" class="diagnostics-story-grid">
        <article v-for="item in modelStoryCards" :key="item.label" class="diagnostics-story-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.meta }}</small>
        </article>
      </div>
    </section>

    <div v-if="!model.info" class="card">
      <p class="muted">{{ t('diag.noModel') }}</p>
    </div>

    <template v-else>
      <div class="card diagnostics-section">
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

      <div v-if="combinedMetrics.length" class="card diagnostics-section">
        <h2>{{ t('diag.combinedMetrics') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.combinedDesc') }}</p>
        <div class="kpi-grid">
          <div v-for="item in combinedMetrics" :key="item.label" class="kpi-card">
            <span class="kpi-label">{{ item.label }}</span>
            <span class="kpi-value">{{ item.value }}</span>
          </div>
        </div>
      </div>

      <div class="card diagnostics-section">
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

      <div class="card diagnostics-section">
        <div class="focus-head">
          <div>
            <h2 style="margin: 0">{{ t('diag.compareMetrics') }}</h2>
            <p class="muted">{{ t('diag.byPropertyType') }} / {{ t('diag.byRegion') }}</p>
          </div>
          <Select
            v-model="selectedMetric"
            :options="metricOptions"
            option-label="label"
            option-value="value"
            class="metric-select"
          />
        </div>

        <div v-if="perTypeChart" class="chart-panel chart-panel-spaced">
          <h3>{{ t('diag.byPropertyType') }}</h3>
          <div class="chart-frame">
            <Bar :data="perTypeChart" :options="chartOptions" />
          </div>
        </div>

        <div v-if="perRegionChart" class="chart-panel">
          <h3>{{ t('diag.byRegion') }}</h3>
          <div class="chart-frame">
            <Bar :data="perRegionChart" :options="chartOptions" />
          </div>
        </div>
      </div>

      <div v-if="featureHighlights.length" class="card diagnostics-section">
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

      <div v-if="model.info.per_type_metrics" class="card diagnostics-section">
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

      <div v-if="model.info.per_region_metrics" class="card diagnostics-section">
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
  .diagnostics-page {
    display: grid;
    gap: 1rem;
  }

  .diagnostics-hero,
  .diagnostics-section {
    display: grid;
    gap: 1rem;
  }

  .diagnostics-story-grid {
    display: grid;
    gap: 0.8rem;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .diagnostics-story-card {
    display: grid;
    gap: 0.25rem;
    padding: 0.95rem 1rem;
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

  .diagnostics-story-card span {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .diagnostics-story-card strong {
    font-size: 1rem;
  }

  .diagnostics-story-card small {
    color: var(--text-muted);
  }

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
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--surface-muted) 82%, transparent)
    );
    color: var(--text);
    padding: 0.45rem 0.8rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 10px 18px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease,
      box-shadow 160ms ease;
  }

  .focus-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 14px 24px rgb(15 23 42 / 10%);
  }

  .focus-chip.active {
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border));
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--primary) 14%, transparent),
      color-mix(in srgb, var(--secondary) 11%, transparent)
    );
    color: var(--primary-strong);
  }

  .metric-select {
    min-width: 9rem;
  }

  .chart-panel {
    display: grid;
    gap: 0.7rem;
    padding: 1rem;
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--surface-muted) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

  .chart-panel-spaced {
    margin-bottom: 1rem;
  }

  .chart-frame {
    height: 300px;
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
    padding: 0.9rem 1rem;
    border-radius: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
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
    background: color-mix(in srgb, var(--ui-bg-muted) 90%, transparent);
  }

  .feature-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--primary) 86%, white 6%),
      color-mix(in srgb, var(--secondary) 20%, var(--primary) 80%)
    );
  }

  .active-focus-row {
    background: color-mix(in srgb, var(--primary) 7%, transparent);
  }

  .active-focus-row td {
    background: color-mix(in srgb, var(--primary) 7%, transparent);
  }

  @media (max-width: 1100px) {
    .diagnostics-story-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .diagnostics-story-grid,
    .feature-row {
      grid-template-columns: 1fr;
    }
  }
</style>
