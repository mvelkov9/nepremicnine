<script setup>
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import api from '../composables/useApi'
  import AppIcon from '../components/AppIcon.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import { getApiErrorMessage } from '../utils/apiError'
  import { municipalitySlug } from '../utils/municipality'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()

  const mapContainer = ref(null)
  let map = null
  let markersLayer = null

  const loading = ref(false)
  const error = ref('')
  const selectedType = ref('')
  const selectedRegion = ref('')
  const selectedYear = ref('')
  const selectedMunicipality = ref('')
  const viewMode = ref('transactions')
  const initialMunicipality = ref('')

  const coords = ref({})
  const municipalities = ref([])
  const propertyTypes = ref([])
  const regionStats = ref([])
  const transactions = ref([])
  const availableYears = ref([])
  const regionMunicipalities = ref([])

  const TYPE_COLORS = {
    stanovanje: '#2563eb',
    hisa: '#16a34a',
    poslovni_prostor: '#f59e0b',
    garaza: '#64748b',
    turisticni: '#ef4444',
    gostinstvo: '#f97316',
    industrijski: '#0f766e',
    kmetijsko: '#65a30d',
  }

  const DEFAULT_COLOR = '#2563eb'

  const markersData = computed(() => {
    const output = []
    for (const municipality of municipalities.value) {
      const coordinate = coords.value[municipality.name]
      if (!coordinate) continue
      output.push({ ...municipality, lat: coordinate.lat, lon: coordinate.lon })
    }
    return output
  })

  const totalCount = computed(() => {
    if (viewMode.value === 'transactions') return transactions.value.length
    return municipalities.value.reduce((sum, item) => sum + item.count, 0)
  })

  const avgPrice = computed(() => {
    if (viewMode.value === 'transactions') {
      if (!transactions.value.length) return null
      return (
        transactions.value.reduce((sum, item) => sum + (item.price_eur || 0), 0) /
        transactions.value.length
      )
    }

    const items = municipalities.value.filter((item) => item.avg_price)
    if (!items.length) return null

    return (
      items.reduce((sum, item) => sum + item.avg_price * item.count, 0) /
      items.reduce((sum, item) => sum + item.count, 0)
    )
  })

  const topMunicipality = computed(() => municipalities.value[0] || null)
  const activeChips = computed(() =>
    [
      selectedType.value,
      selectedRegion.value,
      selectedYear.value,
      selectedMunicipality.value,
    ].filter(Boolean),
  )

  const activityFeed = computed(() =>
    viewMode.value === 'transactions'
      ? transactions.value.slice(0, 12)
      : municipalities.value.slice(0, 12),
  )

  function fmt(value, decimals = 0) {
    if (value == null) return '—'
    return Number(value).toLocaleString('sl-SI', { maximumFractionDigits: decimals })
  }

  function markerRadius(count) {
    if (!totalCount.value) return 6
    const ratio = count / totalCount.value
    return Math.max(5, Math.min(30, 6 + ratio * 420))
  }

  function priceGradientColor(pricePerM2) {
    const min = 500
    const max = 5000
    const clamped = Math.max(min, Math.min(max, pricePerM2 || min))
    const ratio = (clamped - min) / (max - min)
    if (ratio < 0.5) {
      const r = Math.round(255 * (ratio * 2))
      return `rgb(${r}, 190, 60)`
    }
    const g = Math.round(190 * (1 - (ratio - 0.5) * 2))
    return `rgb(255, ${g}, 60)`
  }

  function initMap() {
    if (!mapContainer.value) return

    map = L.map(mapContainer.value, { preferCanvas: true }).setView([46.1512, 14.9955], 8)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map)

    markersLayer = L.layerGroup().addTo(map)
  }

  function renderTransactionMarkers() {
    if (!markersLayer) return
    markersLayer.clearLayers()

    for (const item of transactions.value) {
      const color = priceGradientColor(
        item.price_per_m2 || (item.size_m2 ? item.price_eur / item.size_m2 : null),
      )

      const marker = L.circleMarker([item.lat, item.lon], {
        radius: 5,
        fillColor: color,
        color: '#0f172a',
        weight: 0.6,
        opacity: 0.9,
        fillOpacity: 0.78,
      })

      marker.bindPopup(
        `<div style="font-size:13px;line-height:1.6;min-width:160px">
          <strong>${item.municipality || '—'}</strong><br>
          ${t('map.price')}: <b>${fmt(item.price_eur)} €</b><br>
          ${t('predict.size')}: <b>${fmt(item.size_m2, 1)} m²</b><br>
          €/m²: <b>${fmt(item.price_per_m2)} €</b><br>
          ${item.property_type ? `${t('map.propertyType')}: ${item.property_type}<br>` : ''}
          ${item.year ? `${t('map.year')}: ${item.year}` : ''}
        </div>`,
      )

      markersLayer.addLayer(marker)
    }
  }

  function renderOverviewMarkers() {
    if (!markersLayer) return
    markersLayer.clearLayers()

    for (const item of markersData.value) {
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: markerRadius(item.count),
        fillColor: TYPE_COLORS[selectedType.value] || DEFAULT_COLOR,
        color: '#16324f',
        weight: 1,
        opacity: 0.9,
        fillOpacity: 0.58,
      })

      marker.bindPopup(
        `<div style="font-size:13px;line-height:1.6;min-width:150px">
          <strong>${item.name}</strong><br>
          ${t('map.transactions')}: <b>${fmt(item.count)}</b><br>
          ${t('map.avgPrice')}: <b>${fmt(item.avg_price)} €</b>
        </div>`,
      )

      markersLayer.addLayer(marker)
    }
  }

  function renderMarkers() {
    if (viewMode.value === 'transactions') {
      renderTransactionMarkers()
    } else {
      renderOverviewMarkers()
    }
  }

  async function fetchTransactions() {
    const params = { limit: 5000 }
    if (selectedType.value) params.property_type = selectedType.value
    if (selectedRegion.value) params.statistical_region = selectedRegion.value
    if (selectedYear.value) params.year = parseInt(selectedYear.value, 10)
    if (selectedMunicipality.value) params.municipality = selectedMunicipality.value

    const { data } = await api.get('/api/stats/map-transactions', { params })
    transactions.value = [...(data.transactions || [])].sort((left, right) => {
      if ((right.year || '') !== (left.year || ''))
        return String(right.year || '').localeCompare(String(left.year || ''))
      return (right.price_eur || 0) - (left.price_eur || 0)
    })
  }

  async function fetchMunicipalitiesByRegion() {
    if (!selectedRegion.value) {
      regionMunicipalities.value = []
      return
    }

    try {
      const { data } = await api.get('/api/stats/municipalities-by-region', {
        params: { region: selectedRegion.value },
      })
      regionMunicipalities.value = (data || []).map((item) => item.municipality)
    } catch {
      regionMunicipalities.value = []
    }
  }

  async function fetchData() {
    loading.value = true
    error.value = ''

    try {
      const params = selectedType.value ? { property_type: selectedType.value } : {}

      const requests = [
        api.get('/api/stats/overview', { params }),
        api.get('/api/stats/regions'),
        api.get('/api/model/info').catch(() => ({ data: {} })),
      ]

      if (viewMode.value === 'transactions') {
        requests.push(fetchTransactions())
      }

      const [overviewRes, regionsRes, modelRes] = await Promise.all(requests)

      municipalities.value = overviewRes.data.top_municipalities || []
      propertyTypes.value = overviewRes.data.property_types || []
      regionStats.value = regionsRes.data || []
      coords.value = modelRes.data.coords_by_municipality || {}

      if (!availableYears.value.length) {
        try {
          const { data } = await api.get('/api/stats/trend')
          availableYears.value = (data || [])
            .map((item) => item.year)
            .sort((left, right) => Number(right) - Number(left))
        } catch {
          availableYears.value = []
        }
      }

      await nextTick()
      renderMarkers()
    } catch (err) {
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  function clearFilters() {
    selectedType.value = ''
    selectedRegion.value = ''
    selectedYear.value = ''
    selectedMunicipality.value = ''
  }

  function openMunicipality(name) {
    router.push(`/obcine/${municipalitySlug(name)}`)
  }

  function useForPrediction(item = null) {
    router.push({
      name: 'prediction',
      query: {
        municipality:
          item?.municipality || selectedMunicipality.value || topMunicipality.value?.name || '',
        property_type: item?.property_type || selectedType.value || 'stanovanje',
        size_m2: item?.size_m2 || '',
        price_eur: item?.price_eur || '',
      },
    })
  }

  function applyRouteQuery() {
    selectedType.value = route.query.property_type ? String(route.query.property_type) : ''
    selectedRegion.value = route.query.region ? String(route.query.region) : ''
    selectedYear.value = route.query.year ? String(route.query.year) : ''
    initialMunicipality.value = route.query.municipality ? String(route.query.municipality) : ''
    selectedMunicipality.value = initialMunicipality.value
    viewMode.value = route.query.view === 'overview' ? 'overview' : 'transactions'
  }

  watch(selectedType, () => fetchData())
  watch(viewMode, () => fetchData())
  watch(selectedYear, () => {
    if (viewMode.value === 'transactions') fetchData()
  })
  watch(selectedRegion, async () => {
    selectedMunicipality.value = initialMunicipality.value
    initialMunicipality.value = ''
    await fetchMunicipalitiesByRegion()
    if (viewMode.value === 'transactions') fetchData()
  })
  watch(selectedMunicipality, () => {
    if (viewMode.value === 'transactions') fetchData()
  })

  onMounted(async () => {
    applyRouteQuery()
    await fetchMunicipalitiesByRegion()
    initMap()
    fetchData()
  })

  onBeforeUnmount(() => {
    if (map) {
      map.remove()
      map = null
    }
  })
</script>

<template>
  <div class="map-page">
    <section class="map-hero">
      <div>
        <span class="eyebrow">{{ t('map.title') }}</span>
        <h1>{{ t('map.explorerTitle') }}</h1>
        <p>{{ t('map.explorerBody') }}</p>
      </div>

      <div class="hero-actions">
        <button class="hero-btn primary" @click="useForPrediction()">
          <AppIcon name="prediction" :size="16" />
          <span>{{ t('map.useFiltersForPrediction') }}</span>
        </button>
        <button
          v-if="topMunicipality?.name"
          class="hero-btn"
          @click="openMunicipality(topMunicipality.name)"
        >
          <AppIcon name="market" :size="16" />
          <span>{{ t('map.openTopMunicipality') }}</span>
        </button>
      </div>
    </section>

    <section class="panel filters-panel">
      <div class="filters-grid">
        <label class="field">
          <span>{{ t('map.viewMode') }}</span>
          <select v-model="viewMode" class="form-input">
            <option value="transactions">{{ t('map.transactionView') }}</option>
            <option value="overview">{{ t('map.overviewMode') }}</option>
          </select>
        </label>

        <label class="field">
          <span>{{ t('map.propertyType') }}</span>
          <select v-model="selectedType" class="form-input">
            <option value="">{{ t('map.allTypes') }}</option>
            <option v-for="item in propertyTypes" :key="item.type" :value="item.type">
              {{ item.type }} ({{ fmt(item.count) }})
            </option>
          </select>
        </label>

        <label v-if="viewMode === 'transactions'" class="field">
          <span>{{ t('map.regionFilter') }}</span>
          <select v-model="selectedRegion" class="form-input">
            <option value="">{{ t('map.allRegions') }}</option>
            <option v-for="item in regionStats" :key="item.region" :value="item.region">
              {{ item.region }}
            </option>
          </select>
        </label>

        <label v-if="viewMode === 'transactions'" class="field">
          <span>{{ t('map.yearFilter') }}</span>
          <select v-model="selectedYear" class="form-input">
            <option value="">{{ t('map.allYears') }}</option>
            <option v-for="year in availableYears" :key="year" :value="year">{{ year }}</option>
          </select>
        </label>

        <label v-if="viewMode === 'transactions' && regionMunicipalities.length" class="field">
          <span>{{ t('map.municipalityFilter') }}</span>
          <select v-model="selectedMunicipality" class="form-input">
            <option value="">{{ t('map.allMunicipalities') }}</option>
            <option v-for="item in regionMunicipalities" :key="item" :value="item">
              {{ item }}
            </option>
          </select>
        </label>
      </div>

      <div class="filter-footer">
        <div class="chip-row">
          <span v-for="chip in activeChips" :key="chip" class="chip">{{ chip }}</span>
          <span v-if="!activeChips.length" class="chip muted">{{ t('map.noActiveFilters') }}</span>
        </div>

        <button class="ghost-btn" @click="clearFilters">
          {{ t('map.clearFilter') }}
        </button>
      </div>
    </section>

    <div v-if="loading" class="state-card">
      <LoadingSpinner :label="t('map.loading')" />
    </div>
    <p v-else-if="error" class="state-card error-text">{{ error }}</p>

    <template v-else>
      <section class="metric-band">
        <article class="metric-card">
          <span>{{ t('map.totalTransactions') }}</span>
          <strong>{{ fmt(totalCount) }}</strong>
        </article>
        <article class="metric-card">
          <span>{{ t('map.avgPrice') }}</span>
          <strong>{{ fmt(avgPrice) }} €</strong>
        </article>
        <article class="metric-card">
          <span>{{ t('map.municipalities') }}</span>
          <strong>{{ fmt(markersData.length) }}</strong>
        </article>
        <article class="metric-card">
          <span>{{ t('map.regions') }}</span>
          <strong>{{ fmt(regionStats.length) }}</strong>
        </article>
      </section>

      <section class="explorer-grid">
        <article class="panel map-panel">
          <div ref="mapContainer" class="map-container"></div>

          <div class="map-legend">
            <span class="legend-title">{{ t('map.legend') }}</span>
            <span class="legend-item">
              <span class="legend-dot" style="background: rgb(0, 190, 60)"></span>
              {{ t('map.cheap') }}
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background: rgb(255, 190, 60)"></span>
              {{ t('map.mid') }}
            </span>
            <span class="legend-item">
              <span class="legend-dot" style="background: rgb(255, 0, 60)"></span>
              {{ t('map.expensive') }}
            </span>
            <span class="legend-note">
              {{ viewMode === 'transactions' ? t('map.priceGradientHint') : t('map.sizeHint') }}
            </span>
          </div>
        </article>

        <aside class="panel rail-panel">
          <div class="rail-head">
            <div>
              <span class="eyebrow subtle">{{ t('map.transactions') }}</span>
              <h2>
                {{
                  viewMode === 'transactions' ? t('map.activityFeed') : t('map.topMunicipalities')
                }}
              </h2>
            </div>
          </div>

          <div v-if="activityFeed.length" class="rail-list">
            <article
              v-for="item in activityFeed"
              :key="
                viewMode === 'transactions'
                  ? `${item.municipality}-${item.price_eur}-${item.year}`
                  : item.name
              "
              class="rail-card"
            >
              <template v-if="viewMode === 'transactions'">
                <div class="rail-copy">
                  <strong>{{ item.municipality || '—' }}</strong>
                  <small>{{ item.property_type || '—' }} · {{ item.year || '—' }}</small>
                </div>
                <div class="rail-metric">
                  <strong>{{ fmt(item.price_eur) }} €</strong>
                  <small>{{ fmt(item.price_per_m2) }} €/m²</small>
                </div>
                <div class="rail-actions">
                  <button class="mini-btn" @click="openMunicipality(item.municipality)">
                    {{ t('map.openMunicipality') }}
                  </button>
                  <button class="mini-btn primary" @click="useForPrediction(item)">
                    {{ t('map.useForPrediction') }}
                  </button>
                </div>
              </template>

              <template v-else>
                <div class="rail-copy">
                  <strong>{{ item.name }}</strong>
                  <small>{{ fmt(item.count) }} {{ t('map.transactions') }}</small>
                </div>
                <div class="rail-metric">
                  <strong>{{ fmt(item.avg_price) }} €</strong>
                </div>
                <div class="rail-actions">
                  <button class="mini-btn" @click="openMunicipality(item.name)">
                    {{ t('map.openMunicipality') }}
                  </button>
                </div>
              </template>
            </article>
          </div>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
        </aside>
      </section>

      <section class="panel table-panel">
        <div class="rail-head">
          <div>
            <span class="eyebrow subtle">{{ t('map.regionStats') }}</span>
            <h2>{{ t('map.regionSnapshot') }}</h2>
          </div>
        </div>

        <div v-if="regionStats.length" class="table-shell">
          <table>
            <thead>
              <tr>
                <th>{{ t('map.region') }}</th>
                <th>{{ t('map.count') }}</th>
                <th>{{ t('map.avgPrice') }}</th>
                <th>{{ t('map.medianPrice') }}</th>
                <th>€/m²</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in regionStats" :key="item.region">
                <td>{{ item.region }}</td>
                <td>{{ fmt(item.count) }}</td>
                <td>{{ fmt(item.avg_price) }} €</td>
                <td>{{ fmt(item.median_price) }} €</td>
                <td>{{ fmt(item.avg_price_per_m2) }} €</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="empty-text">{{ t('common.noData') }}</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .map-page,
  .hero-actions,
  .filters-grid,
  .metric-band,
  .rail-list {
    display: grid;
    gap: 1rem;
  }

  .map-hero,
  .panel,
  .metric-card,
  .state-card {
    border-radius: 1.6rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 78%);
    box-shadow: var(--shadow-sm);
  }

  .map-hero,
  .panel {
    padding: 1.1rem;
  }

  .map-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) auto;
    align-items: end;
    background:
      linear-gradient(135deg, rgb(255 255 255 / 82%), rgb(255 255 255 / 70%)),
      radial-gradient(circle at top left, rgb(37 99 235 / 15%), transparent 32%),
      radial-gradient(circle at right, rgb(245 158 11 / 12%), transparent 26%);
  }

  .map-hero h1,
  .rail-head h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  .map-hero p,
  .metric-card span,
  .legend-note,
  .rail-copy small,
  .rail-metric small,
  .empty-text,
  .error-text {
    color: var(--text-muted);
  }

  .eyebrow {
    display: inline-flex;
    margin-bottom: 0.55rem;
    color: var(--primary-strong);
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.17em;
    text-transform: uppercase;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  .hero-actions {
    grid-auto-flow: column;
    grid-auto-columns: max-content;
    justify-content: end;
    gap: 0.75rem;
  }

  .hero-btn,
  .mini-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.8rem 1rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 88%);
  }

  .hero-btn.primary,
  .mini-btn.primary {
    border-color: rgb(37 99 235 / 24%);
    background: linear-gradient(135deg, var(--primary), var(--primary-strong));
    color: #eff6ff;
  }

  .filters-panel {
    display: grid;
    gap: 1rem;
  }

  .filters-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }

  .field {
    display: grid;
    gap: 0.38rem;
  }

  .field span {
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--text-muted);
  }

  .filter-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .chip {
    display: inline-flex;
    padding: 0.4rem 0.7rem;
    border-radius: 999px;
    background: rgb(37 99 235 / 10%);
    color: var(--primary-strong);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .chip.muted {
    background: rgb(15 23 42 / 7%);
    color: var(--text-soft);
  }

  .ghost-btn {
    border: none;
    background: none;
    color: var(--primary-strong);
    font-weight: 700;
  }

  .metric-band {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .metric-card {
    padding: 1rem;
  }

  .metric-card strong {
    display: block;
    margin-top: 0.25rem;
    font-size: 1.5rem;
  }

  .explorer-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.9fr);
    gap: 1rem;
  }

  .map-panel {
    overflow: hidden;
    padding: 0;
  }

  .map-container {
    width: 100%;
    height: 620px;
    z-index: 1;
  }

  .map-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding: 0.9rem 1rem;
    border-top: 1px solid var(--border);
    font-size: 0.82rem;
  }

  .legend-title {
    font-weight: 800;
  }

  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    border: 1px solid rgb(15 23 42 / 18%);
  }

  .rail-head {
    margin-bottom: 0.95rem;
  }

  .rail-card {
    display: grid;
    gap: 0.45rem;
    padding: 0.95rem;
    border-radius: 1.1rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 74%);
  }

  .rail-copy,
  .rail-metric {
    display: grid;
    gap: 0.15rem;
  }

  .rail-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .mini-btn {
    padding: 0.62rem 0.82rem;
    font-size: 0.82rem;
  }

  .table-shell {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    padding: 0.78rem 0.4rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }

  th {
    color: var(--text-soft);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .state-card {
    padding: 1.4rem;
  }

  @media (max-width: 1180px) {
    .filters-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .explorer-grid,
    .map-hero {
      grid-template-columns: 1fr;
    }

    .hero-actions {
      justify-content: start;
      grid-auto-flow: row;
      grid-auto-columns: auto;
    }
  }

  @media (max-width: 760px) {
    .metric-band,
    .filters-grid {
      grid-template-columns: 1fr;
    }

    .map-container {
      height: 460px;
    }
  }
</style>
