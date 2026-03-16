<script setup>
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Drawer from 'primevue/drawer'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import api from '../composables/useApi'
  import { getApiErrorMessage } from '../utils/apiError'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { municipalitySlug } from '../utils/municipality'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()

  const mapContainer = ref(null)
  let map = null
  let markersLayer = null

  const loading = ref(false)
  const error = ref('')
  const mapMetaReason = ref(null)
  const mapLegend = ref(null)
  const selectedType = ref('')
  const selectedRegion = ref('')
  const selectedYear = ref('')
  const selectedMunicipality = ref('')
  const selectedPriceBand = ref('')
  const viewMode = ref('transactions')
  const initialMunicipality = ref('')

  const municipalities = ref([])
  const propertyTypes = ref([])
  const regionStats = ref([])
  const transactions = ref([])
  const availableYears = ref([])
  const regionMunicipalities = ref([])

  const drawerVisible = ref(false)
  const drawerMode = ref('transaction')
  const selectedRecord = ref(null)

  const bandColors = {
    low: '#22c55e',
    mid: '#f59e0b',
    high: '#ef4444',
  }

  const overviewColor = '#3b82f6'

  const markersData = computed(() =>
    viewMode.value === 'transactions' ? transactions.value : municipalities.value,
  )

  const totalCount = computed(() =>
    viewMode.value === 'transactions'
      ? transactions.value.length
      : municipalities.value.reduce((sum, item) => sum + item.count, 0),
  )

  const avgPrice = computed(() => {
    const values =
      viewMode.value === 'transactions'
        ? transactions.value.map((item) => item.price_eur).filter(Boolean)
        : municipalities.value.map((item) => item.avg_price).filter(Boolean)
    if (!values.length) return null
    return values.reduce((sum, value) => sum + value, 0) / values.length
  })

  const topMunicipality = computed(() => municipalities.value[0] || transactions.value[0] || null)

  const activityFeed = computed(() =>
    viewMode.value === 'transactions'
      ? transactions.value.slice(0, 10)
      : municipalities.value.slice(0, 10),
  )

  const bandOptions = computed(() => [
    { label: t('map.allBands'), value: '', count: totalCount.value },
    ...(mapLegend.value
      ? ['low', 'mid', 'high'].map((key) => ({
          label: t(`map.${key}`),
          value: key,
          count: mapLegend.value?.counts?.[key] || 0,
          range: bandRangeLabel(key),
        }))
      : []),
  ])

  const propertyTypeOptions = computed(() => [
    { label: t('map.allTypes'), value: '' },
    ...propertyTypes.value.map((item) => ({
      label: `${formatType(item.type)} (${fmt(item.count)})`,
      value: item.type,
    })),
  ])

  const regionOptions = computed(() => [
    { label: t('map.allRegions'), value: '' },
    ...regionStats.value.map((item) => ({ label: item.region, value: item.region })),
  ])

  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: '' },
    ...availableYears.value.map((year) => ({ label: String(year), value: String(year) })),
  ])

  const municipalityOptions = computed(() => [
    { label: t('map.allMunicipalities'), value: '' },
    ...regionMunicipalities.value.map((item) => ({ label: item, value: item })),
  ])

  const comparisonUrl = computed(() => {
    if (!selectedRecord.value) return '#'
    return buildNepremicnineSearchUrl({
      municipality: selectedRecord.value.municipality,
      propertyType:
        drawerMode.value === 'transaction'
          ? formatType(selectedRecord.value.property_type)
          : formatType(selectedType.value || 'stanovanje'),
      rooms: selectedRecord.value.rooms,
      sizeM2: selectedRecord.value.uporabna_povrsina || selectedRecord.value.size_m2,
    })
  })

  const mapStateMessage = computed(() => {
    if (!mapMetaReason.value) return ''
    if (mapMetaReason.value === 'no_train_dataset') return t('map.noPreparedData')
    if (mapMetaReason.value === 'no_coordinates') return t('map.noCoordinates')
    if (mapMetaReason.value === 'no_matches') return t('map.noMatches')
    return t('common.noData')
  })

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value, decimals = 0) {
    return formatCurrency(value, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  function formatType(value) {
    return getPropertyTypeLabel(value, t)
  }

  function bandColor(key) {
    return bandColors[key] || overviewColor
  }

  function bandRangeLabel(key) {
    const thresholds = mapLegend.value?.thresholds
    if (!thresholds) return ''
    if (key === 'low') return `≤ ${fmtCurrency(thresholds.low_max)}`
    if (key === 'mid')
      return `${fmtCurrency(thresholds.low_max)} - ${fmtCurrency(thresholds.mid_max)}`
    return `≥ ${fmtCurrency(thresholds.mid_max)}`
  }

  function markerRadius(count) {
    if (!totalCount.value) return 8
    const ratio = count / totalCount.value
    return Math.max(7, Math.min(28, 8 + ratio * 280))
  }

  function initMap() {
    if (!mapContainer.value) return

    map = L.map(mapContainer.value, { preferCanvas: true, zoomControl: true }).setView(
      [46.1512, 14.9955],
      8,
    )

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 18,
    }).addTo(map)

    markersLayer = L.layerGroup().addTo(map)
  }

  function focusMapItem(item) {
    if (!map || !item?.lat || !item?.lon) return
    map.flyTo([item.lat, item.lon], viewMode.value === 'transactions' ? 11 : 9, {
      duration: 0.45,
    })
  }

  function openDrawer(item, mode = 'transaction') {
    selectedRecord.value = item
    drawerMode.value = mode
    drawerVisible.value = true
    focusMapItem(item)
  }

  function renderTransactionMarkers() {
    if (!markersLayer) return
    markersLayer.clearLayers()

    for (const item of transactions.value) {
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: 5,
        fillColor: bandColor(item.price_band),
        color: '#0f172a',
        weight: 0.9,
        opacity: 0.95,
        fillOpacity: 0.82,
      })

      marker.on('click', () => openDrawer(item, 'transaction'))
      markersLayer.addLayer(marker)
    }
  }

  function renderOverviewMarkers() {
    if (!markersLayer) return
    markersLayer.clearLayers()

    for (const item of municipalities.value) {
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: markerRadius(item.count),
        fillColor: bandColor(item.price_band) || overviewColor,
        color: '#16324f',
        weight: 1.1,
        opacity: 0.92,
        fillOpacity: 0.58,
      })

      marker.on('click', () => openDrawer(item, 'overview'))
      markersLayer.addLayer(marker)
    }
  }

  function renderMarkers() {
    if (!markersLayer) return
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
    if (selectedYear.value) params.year = selectedYear.value
    if (selectedMunicipality.value) params.municipality = selectedMunicipality.value
    if (selectedPriceBand.value) params.price_band = selectedPriceBand.value

    const { data } = await api.get('/api/stats/map-transactions', { params })
    mapMetaReason.value = data.meta?.reason || null
    mapLegend.value = data.meta?.legend || null
    transactions.value = data.transactions || []
  }

  async function fetchOverviewMarkers() {
    const params = {}
    if (selectedType.value) params.property_type = selectedType.value
    if (selectedRegion.value) params.statistical_region = selectedRegion.value
    if (selectedYear.value) params.year = selectedYear.value
    if (selectedPriceBand.value) params.price_band = selectedPriceBand.value

    const { data } = await api.get('/api/stats/map-overview', { params })
    mapMetaReason.value = data.meta?.reason || null
    mapLegend.value = data.meta?.legend || null
    municipalities.value = data.municipalities || []
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
    mapMetaReason.value = null

    try {
      const params = selectedType.value ? { property_type: selectedType.value } : {}
      const requests = [api.get('/api/stats/overview', { params }), api.get('/api/stats/regions')]

      if (viewMode.value === 'transactions') {
        requests.push(fetchTransactions())
      } else {
        requests.push(fetchOverviewMarkers())
      }

      const [overviewRes, regionsRes] = await Promise.all(requests)
      propertyTypes.value = overviewRes.data.property_types || []
      regionStats.value = regionsRes.data || []

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
      map?.invalidateSize()
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
    selectedPriceBand.value = ''
  }

  function openMunicipality(name = selectedRecord.value?.municipality) {
    if (!name) return
    router.push(`/obcine/${municipalitySlug(name)}`)
  }

  function useForPrediction(item = selectedRecord.value) {
    router.push({
      name: 'prediction',
      query: {
        municipality:
          item?.municipality ||
          selectedMunicipality.value ||
          topMunicipality.value?.municipality ||
          '',
        property_type: item?.property_type || selectedType.value || 'stanovanje',
        size_m2: item?.size_m2 || '',
        year_built: item?.year_built || '',
        price_eur: item?.price_eur || '',
      },
    })
  }

  function applyRouteQuery() {
    selectedType.value = route.query.property_type ? String(route.query.property_type) : ''
    selectedRegion.value = route.query.region ? String(route.query.region) : ''
    selectedYear.value = route.query.year ? String(route.query.year) : ''
    selectedPriceBand.value = route.query.price_band ? String(route.query.price_band) : ''
    initialMunicipality.value = route.query.municipality ? String(route.query.municipality) : ''
    selectedMunicipality.value = initialMunicipality.value
    viewMode.value = route.query.view === 'overview' ? 'overview' : 'transactions'
  }

  watch([selectedType, selectedYear, selectedPriceBand, viewMode], () => fetchData())

  watch(selectedRegion, async () => {
    selectedMunicipality.value = initialMunicipality.value
    initialMunicipality.value = ''
    await fetchMunicipalitiesByRegion()
    fetchData()
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
    <section class="card map-hero">
      <PageHeader
        :eyebrow="t('map.title')"
        :title="t('map.explorerTitle')"
        :description="t('map.explorerBody')"
      >
        <template #actions>
          <Button
            icon="pi pi-chart-line"
            :label="t('map.useFiltersForPrediction')"
            @click="useForPrediction()"
          />
          <Button
            v-if="topMunicipality?.municipality"
            severity="secondary"
            outlined
            icon="pi pi-building"
            :label="t('map.openTopMunicipality')"
            @click="openMunicipality(topMunicipality.municipality)"
          />
        </template>
      </PageHeader>

      <div class="metric-band">
        <MetricCard :label="t('map.totalTransactions')" :value="fmt(totalCount)" />
        <MetricCard :label="t('map.avgPrice')" :value="fmtCurrency(avgPrice)" />
        <MetricCard :label="t('map.municipalities')" :value="fmt(municipalities.length)" />
        <MetricCard :label="t('map.regions')" :value="fmt(regionStats.length)" />
      </div>
    </section>

    <section class="card filters-panel">
      <PageHeader
        compact
        :eyebrow="t('map.legend')"
        :title="t('map.filterTitle')"
        :description="t('map.filterHint')"
      />

      <div class="filters-grid">
        <label class="field">
          <span>{{ t('map.viewMode') }}</span>
          <Select
            v-model="viewMode"
            :options="[
              { label: t('map.transactionView'), value: 'transactions' },
              { label: t('map.overviewMode'), value: 'overview' },
            ]"
            option-label="label"
            option-value="value"
          />
        </label>

        <label class="field">
          <span>{{ t('map.propertyType') }}</span>
          <Select
            v-model="selectedType"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </label>

        <label class="field">
          <span>{{ t('map.regionFilter') }}</span>
          <Select
            v-model="selectedRegion"
            :options="regionOptions"
            option-label="label"
            option-value="value"
          />
        </label>

        <label class="field">
          <span>{{ t('map.yearFilter') }}</span>
          <Select
            v-model="selectedYear"
            :options="yearOptions"
            option-label="label"
            option-value="value"
          />
        </label>

        <label v-if="viewMode === 'transactions' && regionMunicipalities.length" class="field">
          <span>{{ t('map.municipalityFilter') }}</span>
          <Select
            v-model="selectedMunicipality"
            :options="municipalityOptions"
            option-label="label"
            option-value="value"
          />
        </label>
      </div>

      <div class="legend-strip">
        <button
          v-for="band in bandOptions"
          :key="band.value || 'all'"
          class="legend-chip"
          :class="{ active: selectedPriceBand === band.value }"
          @click="selectedPriceBand = band.value"
        >
          <span
            v-if="band.value"
            class="legend-dot"
            :style="{ backgroundColor: bandColor(band.value) }"
          ></span>
          <span class="legend-copy">
            <strong>{{ band.label }}</strong>
            <small> {{ band.range || t('map.allBandsHint') }} · {{ fmt(band.count) }} </small>
          </span>
        </button>

        <Button
          severity="secondary"
          outlined
          icon="pi pi-filter-slash"
          :label="t('map.clearFilter')"
          @click="clearFilters"
        />
      </div>
    </section>

    <div v-if="loading" class="card state-card">
      <LoadingSpinner :label="t('map.loading')" />
    </div>
    <div v-else-if="error" class="card state-card">
      <EmptyState icon="⚠️" :message="error" />
    </div>
    <div v-else-if="mapStateMessage" class="card state-card">
      <EmptyState icon="🗺️" :message="mapStateMessage" />
    </div>

    <section class="explorer-grid">
      <article class="card map-panel">
        <div ref="mapContainer" class="map-container"></div>
      </article>

      <aside class="card rail-panel">
        <PageHeader
          compact
          :eyebrow="
            viewMode === 'transactions' ? t('map.transactions') : t('map.topMunicipalities')
          "
          :title="viewMode === 'transactions' ? t('map.activityFeed') : t('map.topMunicipalities')"
          :description="viewMode === 'transactions' ? t('map.drawerHint') : t('map.overviewHint')"
        />

        <div v-if="activityFeed.length" class="rail-list">
          <button
            v-for="item in activityFeed"
            :key="item.id || item.slug"
            class="rail-card"
            @click="openDrawer(item, viewMode === 'transactions' ? 'transaction' : 'overview')"
          >
            <div class="rail-card-top">
              <strong>{{ item.municipality }}</strong>
              <Tag
                v-if="item.price_band"
                :value="t(`map.${item.price_band}`)"
                :severity="
                  item.price_band === 'high'
                    ? 'danger'
                    : item.price_band === 'mid'
                      ? 'warn'
                      : 'success'
                "
              />
            </div>
            <p>
              {{
                viewMode === 'transactions'
                  ? `${formatType(item.property_type)} · ${fmt(item.size_m2, 1)} m²`
                  : `${fmt(item.count)} ${t('map.transactions')}`
              }}
            </p>
            <div class="rail-card-foot">
              <strong>
                {{
                  viewMode === 'transactions'
                    ? fmtCurrency(item.price_eur)
                    : fmtCurrency(item.avg_price_per_m2)
                }}
              </strong>
              <small>
                {{
                  viewMode === 'transactions'
                    ? `${fmtCurrency(item.price_per_m2)}/m²`
                    : item.region || '—'
                }}
              </small>
            </div>
          </button>
        </div>
        <EmptyState v-else icon="📍" :message="t('common.noData')" />
      </aside>
    </section>

    <section class="card">
      <PageHeader
        compact
        :eyebrow="t('map.regionStats')"
        :title="t('map.regionSnapshot')"
        :description="t('map.regionSnapshotHint')"
      />

      <DataTable
        :value="regionStats.slice(0, 10)"
        size="small"
        striped-rows
        table-style="min-width: 100%"
      >
        <Column field="region" :header="t('map.region')" />
        <Column field="count" :header="t('map.count')">
          <template #body="{ data }">{{ fmt(data.count) }}</template>
        </Column>
        <Column field="avg_price" :header="t('map.avgPrice')">
          <template #body="{ data }">{{ fmtCurrency(data.avg_price) }}</template>
        </Column>
        <Column field="median_price" :header="t('map.medianPrice')">
          <template #body="{ data }">{{ fmtCurrency(data.median_price) }}</template>
        </Column>
        <Column field="avg_price_per_m2" header="€/m²">
          <template #body="{ data }">{{ fmtCurrency(data.avg_price_per_m2) }}</template>
        </Column>
      </DataTable>
    </section>

    <Drawer v-model:visible="drawerVisible" position="right" class="map-drawer">
      <template #header>
        <div class="drawer-header">
          <div>
            <span class="eyebrow">{{
              drawerMode === 'transaction' ? t('map.transactions') : t('map.topMunicipalities')
            }}</span>
            <h2>{{ selectedRecord?.municipality || t('common.noData') }}</h2>
          </div>
          <Tag
            v-if="selectedRecord?.price_band"
            :value="t(`map.${selectedRecord.price_band}`)"
            :severity="
              selectedRecord.price_band === 'high'
                ? 'danger'
                : selectedRecord.price_band === 'mid'
                  ? 'warn'
                  : 'success'
            "
          />
        </div>
      </template>

      <div v-if="selectedRecord" class="drawer-body">
        <div class="drawer-metrics">
          <MetricCard
            :label="t('map.price')"
            :value="
              fmtCurrency(
                drawerMode === 'transaction' ? selectedRecord.price_eur : selectedRecord.avg_price,
              )
            "
          />
          <MetricCard
            :label="t('dashboard.pricePerM2')"
            :value="
              fmtCurrency(
                drawerMode === 'transaction'
                  ? selectedRecord.price_per_m2
                  : selectedRecord.avg_price_per_m2,
              )
            "
          />
          <MetricCard
            :label="drawerMode === 'transaction' ? t('predict.size') : t('map.transactions')"
            :value="
              drawerMode === 'transaction'
                ? `${fmt(selectedRecord.size_m2, 1)} m²`
                : fmt(selectedRecord.count)
            "
          />
        </div>

        <section class="drawer-section">
          <h3>{{ t('map.detailTitle') }}</h3>
          <dl class="detail-grid">
            <template v-if="drawerMode === 'transaction'">
              <div>
                <dt>{{ t('predict.propertyType') }}</dt>
                <dd>{{ formatType(selectedRecord.property_type) }}</dd>
              </div>
              <div>
                <dt>{{ t('map.region') }}</dt>
                <dd>{{ selectedRecord.region || '—' }}</dd>
              </div>
              <div>
                <dt>{{ t('map.year') }}</dt>
                <dd>{{ selectedRecord.year || '—' }}</dd>
              </div>
              <div>
                <dt>{{ t('predict.yearBuilt') }}</dt>
                <dd>{{ selectedRecord.year_built || '—' }}</dd>
              </div>
              <div>
                <dt>{{ t('predict.rooms') }}</dt>
                <dd>{{ selectedRecord.rooms || '—' }}</dd>
              </div>
              <div>
                <dt>{{ t('predict.legaVStavbi') }}</dt>
                <dd>{{ selectedRecord.lega_v_stavbi || '—' }}</dd>
              </div>
            </template>
            <template v-else>
              <div>
                <dt>{{ t('map.region') }}</dt>
                <dd>{{ selectedRecord.region || '—' }}</dd>
              </div>
              <div>
                <dt>{{ t('map.transactions') }}</dt>
                <dd>{{ fmt(selectedRecord.count) }}</dd>
              </div>
              <div>
                <dt>{{ t('map.medianPrice') }}</dt>
                <dd>{{ fmtCurrency(selectedRecord.median_price) }}</dd>
              </div>
              <div>
                <dt>{{ t('dashboard.pricePerM2') }}</dt>
                <dd>{{ fmtCurrency(selectedRecord.avg_price_per_m2) }}</dd>
              </div>
            </template>
          </dl>
        </section>

        <section v-if="drawerMode === 'transaction'" class="drawer-section">
          <h3>{{ t('predict.buildingFlags') }}</h3>
          <div class="flag-grid">
            <span
              v-for="flag in [
                ['novogradnja', t('predict.novogradnja')],
                ['has_garaza', t('predict.hasGaraza')],
                ['has_klet', t('predict.hasKlet')],
                ['has_shramba', t('predict.hasShramba')],
                ['has_terasa', t('predict.hasTerasa')],
                ['stavba_je_dokoncana', t('predict.stavbaDokoncana')],
                ['ddv_vkljucen', t('predict.ddvVkljucen')],
              ]"
              :key="flag[0]"
              class="flag-chip"
              :class="{ active: selectedRecord[flag[0]] }"
            >
              {{ flag[1] }}
            </span>
          </div>
        </section>

        <div class="drawer-actions">
          <Button
            icon="pi pi-building"
            :label="t('map.openMunicipality')"
            @click="openMunicipality()"
          />
          <Button
            severity="secondary"
            outlined
            icon="pi pi-chart-line"
            :label="t('map.useForPrediction')"
            @click="useForPrediction()"
          />
          <a :href="comparisonUrl" target="_blank" rel="noreferrer" class="drawer-link">
            <Button
              severity="contrast"
              outlined
              icon="pi pi-external-link"
              :label="t('predict.compareOnPortal')"
            />
          </a>
        </div>
      </div>
    </Drawer>
  </div>
</template>

<style scoped>
  .map-page,
  .metric-band,
  .rail-list,
  .drawer-body,
  .drawer-metrics {
    display: grid;
    gap: 1rem;
  }

  .map-hero,
  .filters-panel,
  .map-panel,
  .rail-panel,
  .state-card {
    display: grid;
    gap: 1rem;
  }

  .metric-band {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .filters-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .legend-strip {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
    align-items: stretch;
  }

  .legend-chip {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.8rem 0.9rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    color: var(--text);
    text-align: left;
  }

  .legend-chip.active {
    border-color: rgb(59 130 246 / 34%);
    box-shadow: 0 18px 36px rgb(59 130 246 / 12%);
  }

  .legend-dot {
    width: 0.8rem;
    height: 0.8rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .legend-copy {
    display: grid;
    gap: 0.1rem;
  }

  .legend-copy strong {
    font-size: 0.9rem;
  }

  .legend-copy small {
    color: var(--text-muted);
  }

  .explorer-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.75fr);
    gap: 1rem;
  }

  .map-container {
    width: 100%;
    height: 640px;
    border-radius: 1.25rem;
    overflow: hidden;
  }

  .rail-card {
    display: grid;
    gap: 0.6rem;
    padding: 1rem;
    border-radius: 1.1rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    text-align: left;
  }

  .rail-card p,
  .rail-card small {
    margin: 0;
    color: var(--text-muted);
  }

  .rail-card-top,
  .rail-card-foot,
  .drawer-header,
  .drawer-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .drawer-header h2,
  .drawer-section h3 {
    margin: 0.3rem 0 0;
    font-family: var(--font-display);
  }

  .drawer-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .drawer-section {
    display: grid;
    gap: 0.8rem;
  }

  .detail-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
    margin: 0;
  }

  .detail-grid div {
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
  }

  .detail-grid dt {
    margin: 0 0 0.25rem;
    color: var(--text-soft);
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .detail-grid dd {
    margin: 0;
    font-weight: 700;
  }

  .flag-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
  }

  .flag-chip {
    padding: 0.55rem 0.8rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    color: var(--text-muted);
    font-weight: 700;
  }

  .flag-chip.active {
    border-color: rgb(37 99 235 / 30%);
    background: rgb(37 99 235 / 10%);
    color: var(--text);
  }

  .drawer-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .drawer-link {
    text-decoration: none;
  }

  :deep(.p-drawer) {
    width: min(34rem, 100vw);
    background: var(--surface-strong);
    color: var(--text);
  }

  :deep(.leaflet-popup-content-wrapper),
  :deep(.leaflet-popup-tip) {
    background: var(--surface-strong);
    color: var(--text);
  }

  @media (max-width: 1120px) {
    .explorer-grid,
    .filters-grid,
    .metric-band,
    .legend-strip,
    .drawer-metrics {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .map-container {
      height: 460px;
    }

    .detail-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
