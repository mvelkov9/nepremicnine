<script setup>
  import { ref, onMounted, computed, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { Bar, Doughnut, Line } from 'vue-chartjs'
  import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    ArcElement,
    Title,
    Tooltip,
    Legend,
    Filler,
  } from 'chart.js'
  import { useStatsStore } from '../stores/stats'
  import api from '../composables/useApi'
  import LoadingSpinner from '../components/LoadingSpinner.vue'

  ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    ArcElement,
    Title,
    Tooltip,
    Legend,
    Filler,
  )

  const { t } = useI18n()
  const stats = useStatsStore()

  const selectedType = ref('')
  const modelInfo = ref(null)
  const featureImportance = ref([])

  const propertyTypes = [
    '',
    'stanovanje',
    'hisa',
    'poslovni_prostor',
    'industrijski',
    'turisticni',
    'gostinstvo',
    'garaza',
    'kmetijsko',
  ]

  onMounted(async () => {
    stats.fetchAll()
    try {
      const [infoRes, impRes] = await Promise.all([
        api.get('/api/model/info').catch(() => ({ data: {} })),
        api.get('/api/model/importance').catch(() => ({ data: [] })),
      ])
      modelInfo.value = infoRes.data
      featureImportance.value = impRes.data || []
    } catch {
      /* ignore */
    }
  })

  watch(selectedType, (val) => {
    const params = val ? { property_type: val } : {}
    stats.fetchOverview(params)
  })

  function fmt(val, decimals = 0) {
    if (val == null) return '—'
    return Number(val).toLocaleString('sl-SI', { maximumFractionDigits: decimals })
  }

  const regionChartData = computed(() => {
    if (!stats.regions.length) return null
    const sorted = [...stats.regions].sort(
      (a, b) => (b.avg_price_per_m2 || 0) - (a.avg_price_per_m2 || 0),
    )
    return {
      labels: sorted.map((r) => r.region),
      datasets: [
        {
          label: '€/m²',
          data: sorted.map((r) => r.avg_price_per_m2 || 0),
          backgroundColor: '#3b82f6',
          borderRadius: 6,
        },
      ],
    }
  })

  const regionChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: { legend: { display: false } },
    scales: { x: { grid: { display: false } } },
  }

  const distributionChartData = computed(() => {
    if (!stats.priceDistribution) return null
    return {
      labels: stats.priceDistribution.bin_labels,
      datasets: [
        {
          label: t('dashboard.transactions'),
          data: stats.priceDistribution.counts,
          backgroundColor: '#3b82f680',
          borderColor: '#3b82f6',
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    }
  })

  const distributionChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 45, font: { size: 10 } } },
      y: { beginAtZero: true },
    },
  }

  const trendChartData = computed(() => {
    if (!stats.trend.length) return null
    return {
      labels: stats.trend.map((p) => p.year),
      datasets: [
        {
          label: t('dashboard.medianPrice'),
          data: stats.trend.map((p) => p.median_price),
          borderColor: '#3b82f6',
          backgroundColor: '#3b82f620',
          fill: true,
          tension: 0.3,
        },
        {
          label: t('dashboard.avgPrice'),
          data: stats.trend.map((p) => p.avg_price),
          borderColor: '#f59e0b',
          borderDash: [5, 5],
          fill: false,
          tension: 0.3,
        },
      ],
    }
  })

  const trendChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' } },
    scales: { y: { beginAtZero: false } },
  }

  const typeChartData = computed(() => {
    if (!stats.overview?.property_types?.length) return null
    return {
      labels: stats.overview.property_types.map((p) => p.type),
      datasets: [
        {
          data: stats.overview.property_types.map((p) => p.count),
          backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
        },
      ],
    }
  })

  const typeChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } },
  }

  const importanceChartData = computed(() => {
    if (!featureImportance.value.length) return null
    const sorted = [...featureImportance.value]
      .sort((a, b) => b.importance - a.importance)
      .slice(0, 15)
    return {
      labels: sorted.map((f) => f.feature),
      datasets: [
        {
          label: t('model.importance'),
          data: sorted.map((f) => f.importance),
          backgroundColor: '#10b981',
          borderRadius: 6,
        },
      ],
    }
  })

  const importanceChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: { legend: { display: false } },
    scales: { x: { grid: { display: false } } },
  }

  const perTypeR2Data = computed(() => {
    if (!modelInfo.value?.per_type_metrics) return null
    const metrics = modelInfo.value.per_type_metrics
    const types = Object.keys(metrics).sort()
    return {
      labels: types,
      datasets: [
        {
          label: 'R²',
          data: types.map((t) => metrics[t].r2 || 0),
          backgroundColor: types.map(
            (t) =>
              ({
                stanovanje: '#3b82f6',
                hisa: '#22c55e',
                poslovni_prostor: '#f59e0b',
                garaza: '#6b7280',
                turisticni: '#a855f7',
                gostinstvo: '#ef4444',
                industrijski: '#64748b',
                kmetijsko: '#84cc16',
              })[t] || '#3b82f6',
          ),
          borderRadius: 6,
        },
      ],
    }
  })

  const perTypeR2Options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { beginAtZero: true, max: 1 },
      x: { grid: { display: false } },
    },
  }
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('dashboard.title') }}</h1>

    <!-- Type filter -->
    <div class="card" style="padding: 12px 20px; margin-bottom: 1rem">
      <div style="display: flex; align-items: center; gap: 12px">
        <label class="form-label" style="margin: 0">{{ t('dashboard.filterByType') }}:</label>
        <select v-model="selectedType" class="form-input" style="max-width: 220px">
          <option value="">{{ t('map.allTypes') }}</option>
          <option v-for="pt in propertyTypes.slice(1)" :key="pt" :value="pt">{{ pt }}</option>
        </select>
      </div>
    </div>

    <LoadingSpinner v-if="stats.loading" :label="t('common.loading')" />

    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.totalRecords') }}</span>
        <span class="kpi-value">{{ fmt(stats.overview?.total_records) }}</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.medianPrice') }}</span>
        <span class="kpi-value">{{ fmt(stats.overview?.median_price) }} €</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.pricePerM2') }}</span>
        <span class="kpi-value">{{ fmt(stats.overview?.avg_price_per_m2) }} €</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('dashboard.avgArea') }}</span>
        <span class="kpi-value">{{ fmt(stats.overview?.avg_area, 1) }} m²</span>
      </div>
    </div>

    <div class="charts-grid">
      <div class="card">
        <div class="card-title">{{ t('dashboard.regionPrices') }}</div>
        <div v-if="regionChartData" style="height: 320px">
          <Bar :data="regionChartData" :options="regionChartOptions" />
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </div>

      <div class="card">
        <div class="card-title">{{ t('dashboard.priceDistribution') }}</div>
        <div v-if="distributionChartData" style="height: 320px">
          <Bar :data="distributionChartData" :options="distributionChartOptions" />
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </div>

      <div class="card">
        <div class="card-title">{{ t('dashboard.priceTrend') }}</div>
        <div v-if="trendChartData" style="height: 320px">
          <Line :data="trendChartData" :options="trendChartOptions" />
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </div>

      <div class="card">
        <div class="card-title">{{ t('dashboard.propertyTypes') }}</div>
        <div v-if="typeChartData" style="height: 320px">
          <Doughnut :data="typeChartData" :options="typeChartOptions" />
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </div>
    </div>

    <div v-if="stats.overview?.top_municipalities?.length" class="card">
      <div class="card-title">{{ t('dashboard.topMunicipalities') }}</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('dashboard.municipality') }}</th>
              <th>{{ t('dashboard.transactions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in stats.overview.top_municipalities" :key="m.municipality">
              <td>{{ m.municipality }}</td>
              <td>{{ fmt(m.count) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Feature importance & per-type R² -->
    <div class="charts-grid">
      <div class="card">
        <div class="card-title">{{ t('dashboard.featureImportance') }}</div>
        <div v-if="importanceChartData" style="height: 360px">
          <Bar :data="importanceChartData" :options="importanceChartOptions" />
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </div>

      <div class="card">
        <div class="card-title">{{ t('dashboard.perTypeR2') }}</div>
        <div v-if="perTypeR2Data" style="height: 360px">
          <Bar :data="perTypeR2Data" :options="perTypeR2Options" />
        </div>
        <p v-else class="muted">{{ t('common.noData') }}</p>
      </div>
    </div>
  </div>
</template>
