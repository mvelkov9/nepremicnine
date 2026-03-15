<script setup>
import { onMounted, computed } from 'vue'
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

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Title, Tooltip, Legend, Filler)

const { t } = useI18n()
const stats = useStatsStore()

onMounted(() => stats.fetchAll())

function fmt(val, decimals = 0) {
  if (val == null) return '—'
  return Number(val).toLocaleString('sl-SI', { maximumFractionDigits: decimals })
}

const regionChartData = computed(() => {
  if (!stats.regions.length) return null
  const sorted = [...stats.regions].sort((a, b) => (b.avg_price_per_m2 || 0) - (a.avg_price_per_m2 || 0))
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
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('dashboard.title') }}</h1>

    <p v-if="stats.loading" class="muted">{{ t('common.loading') }}</p>

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
  </div>
</template>
