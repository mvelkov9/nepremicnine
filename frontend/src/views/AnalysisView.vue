<script setup>
  import { ref, computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { Doughnut } from 'vue-chartjs'
  import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
  import api from '../composables/useApi'
  import { useExport } from '../composables/useExport'
  import { getApiErrorMessage } from '../utils/apiError'

  ChartJS.register(ArcElement, Tooltip, Legend)

  const { t } = useI18n()
  const { exportToCSV } = useExport()

  const jsonInput = ref('')
  const threshold = ref(15)
  const loading = ref(false)
  const error = ref(null)
  const result = ref(null)

  const summaryChart = computed(() => {
    if (!result.value) return null
    return {
      labels: [t('analysis.overpriced'), t('analysis.underpriced'), t('analysis.marketAligned')],
      datasets: [
        {
          data: [result.value.overpriced, result.value.underpriced, result.value.market_aligned],
          backgroundColor: ['#ef4444', '#22c55e', '#3b82f6'],
        },
      ],
    }
  })

  function parseListings() {
    try {
      const parsed = JSON.parse(jsonInput.value)
      return Array.isArray(parsed) ? parsed : [parsed]
    } catch {
      error.value = t('analysis.invalidJson')
      return null
    }
  }

  async function analyze() {
    const listings = parseListings()
    if (!listings) return

    loading.value = true
    error.value = null
    result.value = null

    try {
      const { data } = await api.post('/api/analysis/score', {
        listings,
        threshold: threshold.value,
      })
      result.value = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  function loadSample() {
    jsonInput.value = JSON.stringify(
      [
        {
          size_m2: 65,
          rooms: 2.5,
          year_built: 2005,
          municipality: 'Ljubljana',
          property_type: 'stanovanje',
          asking_price: 250000,
        },
        {
          size_m2: 120,
          rooms: 4,
          year_built: 1990,
          municipality: 'Maribor',
          property_type: 'hisa',
          asking_price: 180000,
        },
        {
          size_m2: 45,
          rooms: 1.5,
          year_built: 2018,
          municipality: 'Koper',
          property_type: 'stanovanje',
          asking_price: 195000,
        },
      ],
      null,
      2,
    )
  }

  function labelColor(label) {
    if (label === 'overpriced') return 'badge-red'
    if (label === 'underpriced') return 'badge-green'
    return 'badge-blue'
  }
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.analysis') }}</h1>

    <!-- Input -->
    <div class="card" style="margin-bottom: 1.5rem">
      <h2>{{ t('analysis.title') }}</h2>
      <p class="muted" style="margin-bottom: 1rem">{{ t('analysis.desc') }}</p>

      <div style="display: flex; gap: 1rem; align-items: end; margin-bottom: 1rem; flex-wrap: wrap">
        <div style="flex: 0 0 auto">
          <label class="form-label">{{ t('analysis.threshold') }} (%)</label>
          <input
            v-model.number="threshold"
            type="number"
            min="1"
            max="100"
            class="form-input"
            style="width: 100px"
          />
        </div>
        <button class="secondary" @click="loadSample" style="height: fit-content">
          {{ t('analysis.loadSample') }}
        </button>
      </div>

      <textarea
        v-model="jsonInput"
        class="form-input"
        style="min-height: 180px; font-family: monospace; font-size: 13px"
        :placeholder="t('analysis.jsonPlaceholder')"
      />

      <div class="actions">
        <button @click="analyze" :disabled="loading || !jsonInput.trim()">
          {{ loading ? t('common.loading') : t('analysis.analyzeButton') }}
        </button>
      </div>

      <p v-if="error" class="error-text" style="margin-top: 0.75rem">{{ error }}</p>
    </div>

    <!-- Results -->
    <template v-if="result">
      <!-- Summary -->
      <div class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('analysis.results') }}</h2>
        <div
          style="display: grid; grid-template-columns: 1fr 250px; gap: 2rem; align-items: center"
        >
          <div class="kpi-grid">
            <div class="kpi-card">
              <span class="kpi-label">{{ t('analysis.total') }}</span>
              <span class="kpi-value">{{ result.total }}</span>
            </div>
            <div class="kpi-card" style="border-left: 3px solid #ef4444">
              <span class="kpi-label">{{ t('analysis.overpriced') }}</span>
              <span class="kpi-value">{{ result.overpriced }}</span>
            </div>
            <div class="kpi-card" style="border-left: 3px solid #22c55e">
              <span class="kpi-label">{{ t('analysis.underpriced') }}</span>
              <span class="kpi-value">{{ result.underpriced }}</span>
            </div>
            <div class="kpi-card" style="border-left: 3px solid #3b82f6">
              <span class="kpi-label">{{ t('analysis.marketAligned') }}</span>
              <span class="kpi-value">{{ result.market_aligned }}</span>
            </div>
          </div>
          <div v-if="summaryChart" style="max-width: 220px">
            <Doughnut
              :data="summaryChart"
              :options="{ responsive: true, plugins: { legend: { position: 'bottom' } } }"
            />
          </div>
        </div>
      </div>

      <!-- Listings table -->
      <div class="card">
        <div
          style="
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
          "
        >
          <h2 style="margin: 0">{{ t('analysis.scoredListings') }}</h2>
          <button
            v-if="result.listings && result.listings.length"
            class="secondary"
            @click="exportToCSV(result.listings, 'analysis.csv')"
          >
            {{ t('analysis.export') }}
          </button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>{{ t('analysis.askingPrice') }}</th>
                <th>{{ t('analysis.predictedPrice') }}</th>
                <th>{{ t('analysis.deviation') }}</th>
                <th>{{ t('analysis.label') }}</th>
                <th>{{ t('predict.propertyType') }}</th>
                <th>{{ t('predict.municipality') }}</th>
                <th>m²</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in result.listings" :key="item.index">
                <td>{{ item.index + 1 }}</td>
                <td>€{{ Math.round(item.asking_price).toLocaleString() }}</td>
                <td>€{{ Math.round(item.predicted_price).toLocaleString() }}</td>
                <td
                  :style="{
                    color: item.deviation_pct > 0 ? '#ef4444' : '#22c55e',
                    fontWeight: 600,
                  }"
                >
                  {{ item.deviation_pct > 0 ? '+' : '' }}{{ item.deviation_pct.toFixed(1) }}%
                </td>
                <td>
                  <span class="badge" :class="labelColor(item.label)">{{
                    t('analysis.' + item.label)
                  }}</span>
                </td>
                <td>{{ item.property_type || '—' }}</td>
                <td>{{ item.municipality || '—' }}</td>
                <td>{{ item.size_m2 || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
