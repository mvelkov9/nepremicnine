<script setup>
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import { Bar, Doughnut, Line } from 'vue-chartjs'
  import {
    ArcElement,
    BarElement,
    CategoryScale,
    Chart as ChartJS,
    Filler,
    Legend,
    LineElement,
    LinearScale,
    PointElement,
    Title,
    Tooltip,
  } from 'chart.js'
  import api from '../composables/useApi'
  import AppIcon from '../components/AppIcon.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import { useAuthStore } from '../stores/auth'
  import { useDataStore } from '../stores/data'
  import { useStatsStore } from '../stores/stats'
  import { getApiErrorMessage } from '../utils/apiError'

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
  const auth = useAuthStore()
  const dataStore = useDataStore()
  const stats = useStatsStore()

  const selectedType = ref('')
  const modelInfo = ref(null)
  const featureImportance = ref([])
  const modelError = ref(null)
  const chartPalette = {
    primary: '#2563eb',
    primarySoft: '#93c5fd',
    primaryFill: '#2563eb22',
    slate: '#334155',
    amber: '#f59e0b',
    amberFill: '#f59e0b22',
    cyan: '#0891b2',
    emerald: '#059669',
    red: '#dc2626',
  }

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
    await Promise.all([
      stats.fetchAll(),
      dataStore.fetchTrainingDataset().catch(() => null),
      api
        .get('/api/model/info')
        .then((response) => {
          modelInfo.value = response.data
        })
        .catch((error) => {
          modelError.value = getApiErrorMessage(error, t)
        }),
      api
        .get('/api/model/importance')
        .then((response) => {
          featureImportance.value = response.data || []
        })
        .catch(() => {
          featureImportance.value = []
        }),
    ])
  })

  watch(selectedType, (value) => {
    const params = value ? { property_type: value } : {}
    stats.fetchOverview(params)
  })

  function fmt(value, decimals = 0) {
    if (value == null) return '—'
    return Number(value).toLocaleString('sl-SI', { maximumFractionDigits: decimals })
  }

  const quickLinks = computed(() => {
    const links = [
      {
        to: '/napoved',
        icon: 'prediction',
        title: t('dashboard.quickPrediction'),
      },
      {
        to: '/zemljevid',
        icon: 'map',
        title: t('dashboard.quickMap'),
      },
    ]

    if (auth.isAdmin) {
      links.unshift(
        {
          to: '/priprava',
          icon: 'prepare',
          title: t('dashboard.quickPrepare'),
        },
        {
          to: '/model',
          icon: 'model',
          title: t('dashboard.quickTrain'),
        },
      )
    }

    return links
  })

  const statusCards = computed(() => {
    if (!auth.isAdmin) return []

    return [
      {
        icon: 'prepare',
        label: t('dashboard.preparedDataset'),
        title: dataStore.trainingDataset?.exists
          ? t('dashboard.preparedReady')
          : t('dashboard.preparedMissing'),
        detail: dataStore.trainingDataset?.exists
          ? `${fmt(dataStore.trainingDataset.rows)} ${t('data.rows')}`
          : t('dashboard.preparedMissingDetail'),
      },
      {
        icon: 'model',
        label: t('dashboard.modelStatus'),
        title: modelInfo.value ? t('dashboard.modelReady') : t('dashboard.modelMissing'),
        detail: modelInfo.value
          ? `${fmt(modelInfo.value.rows)} ${t('data.rows')}`
          : t('dashboard.modelMissingDetail'),
      },
    ]
  })

  const regionChartData = computed(() => {
    if (!stats.regions.length) return null
    const sorted = [...stats.regions].sort(
      (a, b) => (b.avg_price_per_m2 || 0) - (a.avg_price_per_m2 || 0),
    )
    return {
      labels: sorted.map((item) => item.region),
      datasets: [
        {
          label: '€/m²',
          data: sorted.map((item) => item.avg_price_per_m2 || 0),
          backgroundColor: chartPalette.primary,
          borderRadius: 10,
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
          backgroundColor: chartPalette.primaryFill,
          borderColor: chartPalette.primary,
          borderWidth: 1,
          borderRadius: 8,
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
      labels: stats.trend.map((item) => item.year),
      datasets: [
        {
          label: t('dashboard.medianPrice'),
          data: stats.trend.map((item) => item.median_price),
          borderColor: chartPalette.primary,
          backgroundColor: chartPalette.primaryFill,
          fill: true,
          tension: 0.3,
        },
        {
          label: t('dashboard.avgPrice'),
          data: stats.trend.map((item) => item.avg_price),
          borderColor: chartPalette.amber,
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
      labels: stats.overview.property_types.map((item) => item.type),
      datasets: [
        {
          data: stats.overview.property_types.map((item) => item.count),
          backgroundColor: [
            chartPalette.primary,
            chartPalette.slate,
            chartPalette.amber,
            chartPalette.cyan,
            chartPalette.emerald,
            chartPalette.red,
          ],
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
      labels: sorted.map((item) => item.feature),
      datasets: [
        {
          label: t('model.importance'),
          data: sorted.map((item) => item.importance),
          backgroundColor: chartPalette.primary,
          borderRadius: 8,
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
          data: types.map((type) => metrics[type].r2 || 0),
          backgroundColor: [
            chartPalette.primary,
            chartPalette.amber,
            chartPalette.slate,
            chartPalette.cyan,
            chartPalette.red,
            chartPalette.emerald,
          ],
          borderRadius: 8,
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
    <section class="hero-panel">
      <div class="hero-copy">
        <span class="hero-kicker">{{ t('dashboard.title') }}</span>
        <h2>{{ t('dashboard.heroTitle') }}</h2>
        <p>{{ t('dashboard.heroBody') }}</p>
      </div>

      <div class="hero-actions-grid">
        <RouterLink
          v-for="link in quickLinks"
          :key="link.to"
          :to="link.to"
          class="action-tile compact"
        >
          <span class="tile-icon">
            <AppIcon :name="link.icon" :size="18" />
          </span>
          <strong>{{ link.title }}</strong>
        </RouterLink>
      </div>
    </section>

    <div v-if="statusCards.length" class="spotlight-grid compact">
      <article v-for="card in statusCards" :key="card.label" class="spotlight-card compact">
        <div class="status-card-head">
          <span class="tile-icon subtle">
            <AppIcon :name="card.icon" :size="16" />
          </span>
          <span class="eyebrow">{{ card.label }}</span>
        </div>
        <strong>{{ card.title }}</strong>
        <p>{{ card.detail }}</p>
      </article>
    </div>

    <div class="card filter-card">
      <div class="filter-card-head">
        <div>
          <p class="eyebrow">{{ t('dashboard.filterByType') }}</p>
          <h3>{{ t('dashboard.dataLens') }}</h3>
        </div>
        <select v-model="selectedType" class="form-input" style="max-width: 240px">
          <option value="">{{ t('map.allTypes') }}</option>
          <option
            v-for="propertyType in propertyTypes.slice(1)"
            :key="propertyType"
            :value="propertyType"
          >
            {{ propertyType }}
          </option>
        </select>
      </div>
    </div>

    <LoadingSpinner v-if="stats.loading" :label="t('common.loading')" />

    <p v-if="modelError" class="error-text" style="margin-bottom: 1rem">
      {{ t('dashboard.modelLoadError') }}: {{ modelError }}
    </p>

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
            <tr v-for="municipality in stats.overview.top_municipalities" :key="municipality.name">
              <td>{{ municipality.name }}</td>
              <td>{{ fmt(municipality.count) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

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
