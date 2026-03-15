<script setup>
  import { ref, reactive, onMounted, onBeforeUnmount, watch, computed, nextTick } from 'vue'
  import { useI18n } from 'vue-i18n'
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import api from '../composables/useApi'

  const { t } = useI18n()

  /* ── state ─────────────────────────────────────────────── */
  const mapContainer = ref(null)
  let map = null
  let markersLayer = null

  const loading = ref(false)
  const error = ref('')
  const selectedType = ref('')

  const coords = ref({}) // { municipality: {lat, lon} }
  const municipalities = ref([]) // [{name, count, avg_price}]
  const propertyTypes = ref([]) // [{type, count}]
  const regionStats = ref([]) // [{region, count, avg_price, ...}]

  const TYPE_COLORS = {
    stanovanje: '#3b82f6',
    hisa: '#22c55e',
    poslovni_prostor: '#f59e0b',
    garaza: '#6b7280',
    turisticni: '#a855f7',
    gostinstvo: '#ef4444',
    industrijski: '#64748b',
    kmetijsko: '#84cc16',
  }
  const DEFAULT_COLOR = '#3b82f6'

  /* ── computed ──────────────────────────────────────────── */
  const markersData = computed(() => {
    const out = []
    for (const m of municipalities.value) {
      const c = coords.value[m.name]
      if (!c) continue
      out.push({ ...m, lat: c.lat, lon: c.lon })
    }
    return out
  })

  const totalCount = computed(() => municipalities.value.reduce((s, m) => s + m.count, 0))
  const avgPrice = computed(() => {
    const withPrice = municipalities.value.filter((m) => m.avg_price)
    if (!withPrice.length) return null
    return (
      withPrice.reduce((s, m) => s + m.avg_price * m.count, 0) /
      withPrice.reduce((s, m) => s + m.count, 0)
    )
  })
  const topMunicipality = computed(() => municipalities.value[0] || null)
  const regionCount = computed(() => regionStats.value.length)

  /* ── helpers ───────────────────────────────────────────── */
  function fmt(val, decimals = 0) {
    if (val == null) return '—'
    return Number(val).toLocaleString('sl-SI', { maximumFractionDigits: decimals })
  }

  function markerRadius(count) {
    if (!totalCount.value) return 5
    const ratio = count / totalCount.value
    return Math.max(4, Math.min(30, 4 + ratio * 400))
  }

  function markerColor(municipality) {
    if (selectedType.value) {
      return TYPE_COLORS[selectedType.value] || DEFAULT_COLOR
    }
    return DEFAULT_COLOR
  }

  /* ── map ───────────────────────────────────────────────── */
  function initMap() {
    if (!mapContainer.value) return
    map = L.map(mapContainer.value, { preferCanvas: true }).setView([46.1512, 14.9955], 8)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map)

    markersLayer = L.layerGroup().addTo(map)
  }

  function renderMarkers() {
    if (!markersLayer) return
    markersLayer.clearLayers()

    for (const m of markersData.value) {
      const color = markerColor(m.name)
      const radius = markerRadius(m.count)

      const circle = L.circleMarker([m.lat, m.lon], {
        radius,
        fillColor: color,
        color: '#1e3a5f',
        weight: 1,
        opacity: 0.85,
        fillOpacity: 0.6,
      })

      circle.bindPopup(
        `<div style="font-size:13px;line-height:1.6;min-width:140px">
        <strong>${m.name}</strong><br>
        ${t('map.transactions')}: <b>${fmt(m.count)}</b><br>
        ${t('map.avgPrice')}: <b>${fmt(m.avg_price)} €</b>
      </div>`,
      )

      markersLayer.addLayer(circle)
    }
  }

  /* ── data fetching ─────────────────────────────────────── */
  async function fetchData() {
    loading.value = true
    error.value = ''
    try {
      const params = selectedType.value ? { property_type: selectedType.value } : {}

      const [overviewRes, regionsRes, modelRes] = await Promise.all([
        api.get('/api/stats/overview', { params }),
        api.get('/api/stats/regions'),
        api.get('/api/model/info').catch(() => ({ data: {} })),
      ])

      municipalities.value = overviewRes.data.top_municipalities || []
      propertyTypes.value = overviewRes.data.property_types || []
      regionStats.value = regionsRes.data || []
      coords.value = modelRes.data.coords_by_municipality || {}

      await nextTick()
      renderMarkers()
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message
    } finally {
      loading.value = false
    }
  }

  /* ── watchers ──────────────────────────────────────────── */
  watch(selectedType, () => fetchData())

  /* ── lifecycle ─────────────────────────────────────────── */
  onMounted(() => {
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
    <h1 class="page-title">{{ t('map.title') }}</h1>

    <!-- controls -->
    <div class="card map-controls">
      <div class="control-row">
        <div class="control-field">
          <label class="form-label">{{ t('map.propertyType') }}</label>
          <select v-model="selectedType" class="form-input" :disabled="loading">
            <option value="">{{ t('map.allTypes') }}</option>
            <option v-for="pt in propertyTypes" :key="pt.type" :value="pt.type">
              {{ pt.type }} ({{ fmt(pt.count) }})
            </option>
          </select>
        </div>

        <div v-if="selectedType" class="active-filter">
          <span class="badge-blue">{{ selectedType }}</span>
          <button class="clear-btn" @click="selectedType = ''" :title="t('map.clearFilter')">
            ✕
          </button>
        </div>

        <p v-if="loading" class="muted loading-text">{{ t('map.loading') }}</p>
        <p v-if="error" class="muted error-text">{{ error }}</p>
      </div>
    </div>

    <!-- map -->
    <div class="card map-card">
      <div ref="mapContainer" class="map-container"></div>

      <!-- legend -->
      <div class="map-legend">
        <span class="legend-title">{{ t('map.legend') }}:</span>
        <template v-if="selectedType">
          <span class="legend-item">
            <span
              class="legend-dot"
              :style="{ background: TYPE_COLORS[selectedType] || DEFAULT_COLOR }"
            ></span>
            {{ selectedType }}
          </span>
        </template>
        <template v-else>
          <span class="legend-item">
            <span class="legend-dot" :style="{ background: DEFAULT_COLOR }"></span>
            {{ t('map.allTypes') }}
          </span>
        </template>
        <span class="legend-hint">{{ t('map.sizeHint') }}</span>
      </div>
    </div>

    <!-- stats summary -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">{{ t('map.totalTransactions') }}</span>
        <span class="kpi-value">{{ fmt(totalCount) }}</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('map.avgPrice') }}</span>
        <span class="kpi-value">{{ fmt(avgPrice) }} €</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('map.municipalities') }}</span>
        <span class="kpi-value">{{ markersData.length }}</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">{{ t('map.regions') }}</span>
        <span class="kpi-value">{{ regionCount }}</span>
      </div>
    </div>

    <!-- top municipalities table -->
    <div v-if="municipalities.length" class="card">
      <div class="card-title">{{ t('map.topMunicipalities') }}</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>{{ t('map.municipality') }}</th>
              <th>{{ t('map.count') }}</th>
              <th>{{ t('map.avgPrice') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, i) in municipalities.slice(0, 15)" :key="m.name">
              <td>{{ i + 1 }}</td>
              <td>{{ m.name }}</td>
              <td>
                <span class="badge-blue">{{ fmt(m.count) }}</span>
              </td>
              <td>{{ fmt(m.avg_price) }} €</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- region stats -->
    <div v-if="regionStats.length" class="card">
      <div class="card-title">{{ t('map.regionStats') }}</div>
      <div class="table-wrap">
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
            <tr v-for="r in regionStats" :key="r.region">
              <td>{{ r.region }}</td>
              <td>
                <span class="badge-green">{{ fmt(r.count) }}</span>
              </td>
              <td>{{ fmt(r.avg_price) }} €</td>
              <td>{{ fmt(r.median_price) }} €</td>
              <td>{{ fmt(r.avg_price_per_m2) }} €</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .map-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .map-controls {
    padding: 16px 20px;
  }
  .control-row {
    display: flex;
    align-items: flex-end;
    gap: 16px;
    flex-wrap: wrap;
  }
  .control-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 220px;
  }

  .active-filter {
    display: flex;
    align-items: center;
    gap: 6px;
    padding-bottom: 2px;
  }
  .clear-btn {
    background: none;
    border: none;
    color: var(--danger);
    cursor: pointer;
    font-size: 14px;
    padding: 2px 4px;
    line-height: 1;
  }
  .clear-btn:hover {
    background: #fee2e2;
    border-radius: 4px;
  }

  .loading-text {
    color: var(--primary);
  }
  .error-text {
    color: var(--danger);
  }

  .map-card {
    padding: 0;
    overflow: hidden;
  }
  .map-container {
    width: 100%;
    height: 560px;
    z-index: 1;
  }

  .map-legend {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    font-size: 12px;
    border-top: 1px solid #e5e7eb;
    flex-wrap: wrap;
  }
  .legend-title {
    font-weight: 600;
    color: #374151;
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
    color: #555;
  }
  .legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    border: 1px solid rgba(0, 0, 0, 0.15);
  }
  .legend-hint {
    color: #9ca3af;
    font-style: italic;
  }
</style>
