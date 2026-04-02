<script setup lang="ts">
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  /* PrimeVue components (Button, Column, DataTable, Dialog, Select, Tag) are auto-imported */
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { toLocationQuery } from '../constants/workbench'
  import api from '../composables/useApi'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { municipalitySlug } from '../utils/municipality'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  interface MapFilterParams {
    property_type?: string
    statistical_region?: string
    year?: string
    municipality?: string
    price_band?: string
  }

  interface BandOption {
    label: string
    value: string
    count: number
    range?: string
  }

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const workbench = useWorkbenchStore()

  const mapContainer = ref(null)
  let map = null
  let markersLayer = null

  const initialized = ref(false)
  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref('')
  const mapMetaReason = ref(null)
  const mapLegend = ref(null)
  const selectedType = ref('')
  const selectedRegion = ref('')
  const selectedYear = ref('')
  const selectedMunicipality = ref('')
  const selectedPriceBand = ref('')
  const viewMode = ref('transactions')
  const mapZoom = ref(8)

  const municipalities = ref([])
  const allMunicipalities = ref([])
  const propertyTypes = ref([])
  const regionStats = ref([])
  const transactions = ref([])
  const availableYears = ref([])
  const detailComparables = ref([])

  const detailVisible = ref(false)
  const detailMode = ref('transaction')
  const selectedRecord = ref(null)
  let syncingRoute = false
  let writingRoute = false

  const overviewColor = '#3b82f6'

  function semanticColor(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    return value || fallback
  }

  const defaultYear = computed(() => {
    if (!availableYears.value.length) return ''
    const currentYear = new Date().getFullYear()
    return (
      availableYears.value.find((year) => Number(year) < currentYear) ||
      availableYears.value[0] ||
      ''
    )
  })

  const municipalityOptions = computed(() => {
    const rows = selectedRegion.value
      ? allMunicipalities.value.filter((item) => item.region === selectedRegion.value)
      : allMunicipalities.value
    return [{ label: t('map.allMunicipalities'), value: '' }].concat(
      rows.map((item) => ({ label: item.municipality, value: item.municipality })),
    )
  })

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
      ? transactions.value.slice(0, 12)
      : municipalities.value.slice(0, 12),
  )

  const clusteredTransactions = computed(() =>
    clusterTransactions(transactions.value, mapZoom.value),
  )

  const bandOptions = computed<BandOption[]>(() => [
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

  const activeFilterChips = computed(() => {
    const chips: Array<{ key: string; label: string; tone?: string }> = []

    chips.push({
      key: 'view',
      label: viewMode.value === 'transactions' ? t('map.transactionView') : t('map.overviewMode'),
    })

    if (selectedType.value) {
      chips.push({ key: 'type', label: formatType(selectedType.value) })
    }

    if (selectedRegion.value) {
      chips.push({ key: 'region', label: selectedRegion.value })
    }

    if (selectedYear.value) {
      chips.push({ key: 'year', label: selectedYear.value })
    }

    if (selectedMunicipality.value) {
      chips.push({ key: 'municipality', label: selectedMunicipality.value })
    }

    if (selectedPriceBand.value) {
      chips.push({
        key: 'band',
        label:
          bandOptions.value.find((band) => band.value === selectedPriceBand.value)?.label || '',
        tone: selectedPriceBand.value,
      })
    }

    return chips
  })

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

  const comparisonUrl = computed(() => {
    if (!selectedRecord.value) return 'https://www.nepremicnine.net/oglasi-prodaja/'
    return buildNepremicnineSearchUrl({
      municipality: selectedRecord.value.municipality,
      statisticalRegion: selectedRecord.value.region,
      propertyType:
        detailMode.value === 'transaction'
          ? selectedRecord.value.property_type
          : selectedType.value || 'stanovanje',
    })
  })
  const detailDialogTitle = computed(() => {
    if (!selectedRecord.value) return t('common.noData')
    if (detailMode.value === 'transaction' && selectedRecord.value.property_type) {
      return `${selectedRecord.value.municipality} · ${formatType(selectedRecord.value.property_type)}`
    }
    return selectedRecord.value.municipality || t('common.noData')
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
    const bandColors = {
      low: semanticColor('--success', '#22c55e'),
      mid: semanticColor('--warning', '#f59e0b'),
      high: semanticColor('--danger', '#ef4444'),
    }

    return bandColors[key] || semanticColor('--primary', overviewColor)
  }

  function bandRangeLabel(key) {
    const thresholds = mapLegend.value?.thresholds
    if (!thresholds) return ''
    if (key === 'low') return `≤ ${fmtCurrency(thresholds.low_max)}`
    if (key === 'mid') {
      return `${fmtCurrency(thresholds.low_max)} - ${fmtCurrency(thresholds.mid_max)}`
    }
    return `≥ ${fmtCurrency(thresholds.mid_max)}`
  }

  function markerRadius(count) {
    if (!count) return 8
    return Math.max(8, Math.min(26, 7 + Math.log10(count + 1) * 10))
  }

  function dominantBand(counts: Record<string, number> = {}) {
    return (
      Object.entries(counts).sort((left, right) => Number(right[1]) - Number(left[1]))[0]?.[0] ||
      'mid'
    )
  }

  function clusterTransactions(items, zoom) {
    if (zoom >= 12 || items.length <= 1200) return items

    const cellSize = zoom <= 7 ? 0.25 : zoom <= 9 ? 0.12 : 0.05
    const buckets = new Map()

    for (const item of items) {
      const key = `${Math.round(item.lat / cellSize)}:${Math.round(item.lon / cellSize)}`
      const bucket = buckets.get(key) || {
        id: `cluster-${key}`,
        lat: 0,
        lon: 0,
        count: 0,
        clusterCount: 0,
        sample: item,
        priceSum: 0,
        pricePerM2Sum: 0,
        pricePerM2Count: 0,
        municipality: item.municipality,
        region: item.region,
        price_band_counts: {},
      }

      bucket.lat += item.lat
      bucket.lon += item.lon
      bucket.clusterCount += 1
      bucket.count += 1
      bucket.priceSum += Number(item.price_eur || 0)
      if (item.price_per_m2 != null) {
        bucket.pricePerM2Sum += Number(item.price_per_m2)
        bucket.pricePerM2Count += 1
      }
      if (item.price_band) {
        bucket.price_band_counts[item.price_band] =
          (bucket.price_band_counts[item.price_band] || 0) + 1
      }
      buckets.set(key, bucket)
    }

    return Array.from(buckets.values()).map((bucket) => {
      if (bucket.clusterCount === 1) {
        return bucket.sample
      }
      return {
        id: bucket.id,
        lat: Number((bucket.lat / bucket.clusterCount).toFixed(6)),
        lon: Number((bucket.lon / bucket.clusterCount).toFixed(6)),
        municipality: bucket.municipality,
        region: bucket.region,
        clusterCount: bucket.clusterCount,
        avg_price: bucket.clusterCount ? bucket.priceSum / bucket.clusterCount : null,
        avg_price_per_m2: bucket.pricePerM2Count
          ? bucket.pricePerM2Sum / bucket.pricePerM2Count
          : null,
        price_band: dominantBand(bucket.price_band_counts),
      }
    })
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
    mapZoom.value = map.getZoom()
    map.on('zoomend', () => {
      mapZoom.value = map?.getZoom() || 8
      renderMarkers()
    })
  }

  function focusMapItem(item, zoomOverride = null) {
    if (!map || !item?.lat || !item?.lon) return
    map.flyTo([item.lat, item.lon], zoomOverride || (viewMode.value === 'transactions' ? 11 : 9), {
      duration: 0.45,
    })
  }

  async function openDetails(item, mode = 'transaction') {
    if (mode === 'transaction' && item.clusterCount > 1) {
      focusMapItem(item, Math.min((map?.getZoom() || 8) + 2, 12))
      return
    }

    selectedRecord.value = item
    detailMode.value = mode
    detailVisible.value = true
    detailComparables.value = []
    focusMapItem(item)

    if (mode === 'transaction' && item?.municipality && item?.property_type && item?.size_m2) {
      detailLoading.value = true
      try {
        const { data } = await api.get('/api/stats/comparables', {
          params: {
            municipality: item.municipality,
            property_type: item.property_type,
            size_m2: item.size_m2,
            year_built: item.year_built || undefined,
            price_eur: item.price_eur || undefined,
            limit: 4,
          },
        })
        detailComparables.value = data.items || []
      } catch {
        detailComparables.value = []
      } finally {
        detailLoading.value = false
      }
    }
  }

  function renderTransactionMarkers() {
    if (!markersLayer) return
    markersLayer.clearLayers()

    for (const item of clusteredTransactions.value) {
      const radius = markerRadius(item.clusterCount || 1)
      const marker = L.circleMarker([item.lat, item.lon], {
        radius,
        fillColor: bandColor(item.price_band),
        color: '#0f172a',
        weight: item.clusterCount > 1 ? 1.2 : 0.9,
        opacity: 0.95,
        fillOpacity: item.clusterCount > 1 ? 0.68 : 0.82,
      })

      if (item.clusterCount > 1) {
        marker.bindTooltip(`${fmt(item.clusterCount)} ${t('map.transactions')}`)
      }

      marker.on('click', () => openDetails(item, 'transaction'))
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

      marker.on('click', () => openDetails(item, 'overview'))
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
    const params: MapFilterParams = {}
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
    const params: MapFilterParams = {}
    if (selectedType.value) params.property_type = selectedType.value
    if (selectedRegion.value) params.statistical_region = selectedRegion.value
    if (selectedYear.value) params.year = selectedYear.value
    if (selectedMunicipality.value) params.municipality = selectedMunicipality.value
    if (selectedPriceBand.value) params.price_band = selectedPriceBand.value

    const { data } = await api.get('/api/stats/map-overview', { params })
    mapMetaReason.value = data.meta?.reason || null
    mapLegend.value = data.meta?.legend || null
    municipalities.value = data.municipalities || []
  }

  async function loadReferenceData() {
    const [overviewRes, regionsRes, municipalitiesRes, trendRes] = await Promise.all([
      api.get('/api/stats/overview'),
      api.get('/api/stats/regions'),
      api.get('/api/regions/municipalities'),
      api.get('/api/stats/trend'),
    ])

    propertyTypes.value = overviewRes.data.property_types || []
    regionStats.value = regionsRes.data || []
    allMunicipalities.value = municipalitiesRes.data || []
    availableYears.value = (trendRes.data || [])
      .map((item) => item.year)
      .sort((left, right) => Number(right) - Number(left))

    if (!selectedYear.value && defaultYear.value) {
      selectedYear.value = String(defaultYear.value)
    }
  }

  async function fetchData() {
    loading.value = true
    error.value = ''
    mapMetaReason.value = null

    try {
      if (viewMode.value === 'transactions') {
        await fetchTransactions()
      } else {
        await fetchOverviewMarkers()
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
    selectedMunicipality.value = ''
    selectedPriceBand.value = ''
    selectedYear.value = defaultYear.value ? String(defaultYear.value) : ''
  }

  function currentQuerySubset() {
    const subset: Record<string, string> = {}
    const keys = ['property_type', 'region', 'year', 'price_band', 'municipality', 'view']
    for (const key of keys) {
      const value = route.query[key]
      if (typeof value === 'string' && value) subset[key] = value
    }
    return subset
  }

  function nextQuerySubset() {
    const subset: Record<string, string> = {}
    if (selectedType.value) subset.property_type = selectedType.value
    if (selectedRegion.value) subset.region = selectedRegion.value
    if (selectedYear.value) subset.year = selectedYear.value
    if (selectedPriceBand.value) subset.price_band = selectedPriceBand.value
    if (selectedMunicipality.value) subset.municipality = selectedMunicipality.value
    if (viewMode.value === 'overview') subset.view = viewMode.value
    return subset
  }

  function syncRouteQuery() {
    const nextSubset = nextQuerySubset()
    const currentSubset = currentQuerySubset()
    if (JSON.stringify(nextSubset) === JSON.stringify(currentSubset)) return

    const nextQuery = { ...route.query }
    for (const key of ['property_type', 'region', 'year', 'price_band', 'municipality', 'view']) {
      delete nextQuery[key]
    }
    for (const [key, value] of Object.entries(nextSubset)) nextQuery[key] = value
    writingRoute = true
    void router.replace({ query: nextQuery })
  }

  function viewerRouteQuery(overrides: Record<string, string | undefined> = {}) {
    return toLocationQuery({
      property_type: selectedType.value || undefined,
      region: selectedRegion.value || undefined,
      year: selectedYear.value || undefined,
      municipality: selectedMunicipality.value || undefined,
      ...overrides,
    })
  }

  function openMunicipality(name = selectedRecord.value?.municipality) {
    if (!name) return
    router.push({
      path: `/obcine/${municipalitySlug(name)}`,
      query: viewerRouteQuery(),
    })
  }

  async function watchSelectedContext() {
    const label = selectedRecord.value?.municipality || selectedMunicipality.value
    if (!label) return
    await workbench.addWatchlistItem({
      entity_type:
        selectedRecord.value?.region && !selectedRecord.value?.property_type
          ? 'region'
          : 'municipality',
      entity_key:
        selectedRecord.value?.region && !selectedRecord.value?.property_type
          ? selectedRecord.value.region
          : municipalitySlug(label),
      display_label:
        selectedRecord.value?.region && !selectedRecord.value?.property_type
          ? selectedRecord.value.region
          : label,
      metadata: {
        link:
          selectedRecord.value?.region && !selectedRecord.value?.property_type
            ? `/regije?tab=drilldown&region=${encodeURIComponent(selectedRecord.value.region)}`
            : `/obcine/${municipalitySlug(label)}`,
      },
    })
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
        naselje: item?.naselje || '',
        property_type: item?.property_type || selectedType.value || 'stanovanje',
        size_m2: item?.size_m2 || '',
        year_built: item?.year_built || '',
        price_eur: item?.price_eur || '',
      },
    })
  }

  function openMarketExplorer() {
    router.push({
      name: 'market',
      query: viewerRouteQuery({
        tab: viewMode.value === 'transactions' ? 'transactions' : 'overview',
      }),
    })
  }

  function openAnalysis(item = selectedRecord.value) {
    router.push({
      name: 'analysis',
      query: {
        municipality:
          item?.municipality ||
          selectedMunicipality.value ||
          topMunicipality.value?.municipality ||
          '',
        naselje: item?.naselje || '',
        property_type: item?.property_type || selectedType.value || 'stanovanje',
        size_m2: item?.size_m2 || '',
        year_built: item?.year_built || '',
        floor: item?.floor ?? '',
        asking_price: item?.price_eur || item?.avg_price || '',
      },
    })
  }

  function applyRouteQuery() {
    syncingRoute = true
    selectedType.value = route.query.property_type ? String(route.query.property_type) : ''
    selectedRegion.value = route.query.region ? String(route.query.region) : ''
    selectedYear.value = route.query.year ? String(route.query.year) : ''
    selectedPriceBand.value = route.query.price_band ? String(route.query.price_band) : ''
    selectedMunicipality.value = route.query.municipality ? String(route.query.municipality) : ''
    viewMode.value = route.query.view === 'overview' ? 'overview' : 'transactions'
    syncingRoute = false
  }

  watch(
    [selectedType, selectedRegion, selectedYear, selectedMunicipality, selectedPriceBand, viewMode],
    () => {
      if (syncingRoute) return
      syncRouteQuery()
      if (initialized.value) fetchData()
    },
  )

  watch(
    () => route.query,
    () => {
      if (writingRoute) {
        writingRoute = false
        return
      }
      applyRouteQuery()
      if (initialized.value) void fetchData()
    },
  )

  watch(selectedRegion, (region) => {
    if (!region || !selectedMunicipality.value) return
    const valid = allMunicipalities.value.some(
      (item) => item.region === region && item.municipality === selectedMunicipality.value,
    )
    if (!valid) selectedMunicipality.value = ''
  })

  onMounted(async () => {
    applyRouteQuery()
    initMap()
    try {
      await loadReferenceData()
      initialized.value = true
      await fetchData()
    } catch (err) {
      error.value = getApiErrorMessage(err, t)
    }
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
          <SavedWorkspaceMenu
            page="map"
            :state="{ page: 'map', filters: viewerRouteQuery({ view: viewMode }) }"
          />
          <Button
            severity="secondary"
            outlined
            icon="pi pi-table"
            :label="t('market.viewMarket')"
            @click="openMarketExplorer"
          />
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
          <Button
            severity="secondary"
            text
            icon="pi pi-bookmark"
            :label="t('workbench.watch')"
            @click="watchSelectedContext"
          />
        </template>
      </PageHeader>

      <div class="metric-band">
        <MetricCard :label="t('map.totalTransactions')" :value="fmt(totalCount)" />
        <MetricCard :label="t('map.avgPrice')" :value="fmtCurrency(avgPrice)" />
        <MetricCard :label="t('map.municipalities')" :value="fmt(municipalities.length)" />
        <MetricCard :label="t('map.regions')" :value="fmt(regionStats.length)" />
      </div>

      <div v-if="activeFilterChips.length" class="active-filter-ribbon">
        <span
          v-for="chip in activeFilterChips"
          :key="chip.key"
          class="active-filter-chip"
          :class="chip.tone ? `tone-${chip.tone}` : ''"
        >
          {{ chip.label }}
        </span>
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

        <label class="field">
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
        <Button
          v-for="band in bandOptions"
          :key="band.value || 'all'"
          class="legend-chip"
          :severity="selectedPriceBand === band.value ? undefined : 'secondary'"
          :outlined="selectedPriceBand !== band.value"
          @click="selectedPriceBand = band.value"
        >
          <span
            v-if="band.value"
            class="legend-dot"
            :style="{ backgroundColor: bandColor(band.value) }"
          ></span>
          <span class="legend-copy">
            <strong>{{ band.label }}</strong>
            <small>{{ band.range || t('map.allBandsHint') }} · {{ fmt(band.count) }}</small>
          </span>
        </Button>

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
          <Button
            v-for="item in activityFeed"
            :key="item.id || item.slug"
            class="rail-card"
            severity="secondary"
            outlined
            @click="openDetails(item, viewMode === 'transactions' ? 'transaction' : 'overview')"
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
          </Button>
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
        :value="regionStats"
        paginator
        :rows="8"
        size="small"
        striped-rows
        responsive-layout="scroll"
        table-style="min-width: 100%"
      >
        <Column field="region" :header="t('map.region')" sortable />
        <Column field="count" :header="t('map.count')" sortable>
          <template #body="{ data }">{{ fmt(data.count) }}</template>
        </Column>
        <Column field="avg_price" :header="t('map.avgPrice')" sortable>
          <template #body="{ data }">{{ fmtCurrency(data.avg_price) }}</template>
        </Column>
        <Column field="median_price" :header="t('map.medianPrice')" sortable>
          <template #body="{ data }">{{ fmtCurrency(data.median_price) }}</template>
        </Column>
        <Column field="avg_price_per_m2" header="€/m²" sortable>
          <template #body="{ data }">{{ fmtCurrency(data.avg_price_per_m2) }}</template>
        </Column>
      </DataTable>
    </section>

    <Dialog
      v-model:visible="detailVisible"
      modal
      maximizable
      class="map-detail-dialog"
      :header="detailDialogTitle"
      :style="{ width: 'min(98vw, 1280px)' }"
      :breakpoints="{ '1280px': '96vw', '768px': '100vw' }"
    >
      <div v-if="selectedRecord" class="detail-dialog">
        <div class="detail-summary">
          <div>
            <span class="eyebrow">{{
              detailMode === 'transaction' ? t('map.transactions') : t('map.topMunicipalities')
            }}</span>
            <h2>{{ selectedRecord.municipality }}</h2>
            <p class="muted">{{ selectedRecord.region || '—' }}</p>
          </div>
          <Tag
            v-if="selectedRecord.price_band"
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

        <div class="detail-metrics">
          <MetricCard
            :label="t('map.price')"
            :value="
              fmtCurrency(
                detailMode === 'transaction' ? selectedRecord.price_eur : selectedRecord.avg_price,
              )
            "
          />
          <MetricCard
            :label="t('dashboard.pricePerM2')"
            :value="
              fmtCurrency(
                detailMode === 'transaction'
                  ? selectedRecord.price_per_m2
                  : selectedRecord.avg_price_per_m2,
              )
            "
          />
          <MetricCard
            :label="detailMode === 'transaction' ? t('predict.size') : t('map.transactions')"
            :value="
              detailMode === 'transaction'
                ? `${fmt(selectedRecord.size_m2, 1)} m²`
                : fmt(selectedRecord.count)
            "
          />
          <MetricCard
            :label="t('map.year')"
            :value="
              detailMode === 'transaction'
                ? selectedRecord.year || selectedRecord.source_label || '—'
                : selectedRecord.latest_year || defaultYear || '—'
            "
          />
        </div>

        <div class="detail-grid">
          <section class="detail-section detail-section-main">
            <h3>{{ t('map.detailTitle') }}</h3>
            <dl class="detail-list">
              <div v-if="detailMode === 'transaction'">
                <dt>{{ t('predict.propertyType') }}</dt>
                <dd>{{ formatType(selectedRecord.property_type) }}</dd>
              </div>
              <div>
                <dt>{{ t('map.region') }}</dt>
                <dd>{{ selectedRecord.region || '—' }}</dd>
              </div>
              <div v-if="detailMode === 'transaction'">
                <dt>{{ t('predict.yearBuilt') }}</dt>
                <dd>{{ selectedRecord.year_built || '—' }}</dd>
              </div>
              <div v-if="detailMode === 'transaction'">
                <dt>{{ t('predict.rooms') }}</dt>
                <dd>{{ selectedRecord.rooms || '—' }}</dd>
              </div>
              <div v-if="detailMode === 'transaction'">
                <dt>{{ t('predict.floor') }}</dt>
                <dd>{{ selectedRecord.floor ?? '—' }}</dd>
              </div>
              <div v-if="detailMode === 'transaction'">
                <dt>{{ t('predict.legaVStavbi') }}</dt>
                <dd>{{ selectedRecord.lega_v_stavbi || '—' }}</dd>
              </div>
              <div v-if="detailMode === 'transaction'">
                <dt>{{ t('map.sourceYear') }}</dt>
                <dd>{{ selectedRecord.source_label || selectedRecord.year || '—' }}</dd>
              </div>
              <div v-if="detailMode === 'overview'">
                <dt>{{ t('map.medianPrice') }}</dt>
                <dd>{{ fmtCurrency(selectedRecord.median_price) }}</dd>
              </div>
            </dl>
          </section>

          <section v-if="detailMode === 'transaction'" class="detail-section detail-section-flags">
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

          <section class="detail-section detail-section-comparables">
            <h3>{{ t('predict.comparablesTitle') }}</h3>
            <LoadingSpinner v-if="detailLoading" :label="t('common.loading')" />
            <div v-else-if="detailComparables.length" class="comparables-list">
              <article
                v-for="item in detailComparables"
                :key="`${item.slug}-${item.price_eur}-${item.size_m2}`"
                class="comparable-card"
              >
                <div class="comparable-top">
                  <strong>{{ item.municipality }}</strong>
                  <span>{{ item.year || '—' }}</span>
                </div>
                <p>
                  {{ formatType(item.property_type) }} · {{ fmt(item.size_m2, 1) }} m² ·
                  {{ fmtCurrency(item.price_per_m2) }}/m²
                </p>
                <div class="comparable-bottom">
                  <strong>{{ fmtCurrency(item.price_eur) }}</strong>
                  <small>{{ t('predict.similarityLabel') }} {{ item.similarity_score }}</small>
                </div>
              </article>
            </div>
            <EmptyState
              v-else
              icon="📊"
              :message="
                detailMode === 'transaction'
                  ? t('predict.noComparables')
                  : t('map.municipalitySummaryHint')
              "
            />
          </section>
        </div>

        <section class="detail-actions-panel">
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
          <Button
            severity="secondary"
            outlined
            icon="pi pi-search"
            :label="t('nav.analysis')"
            @click="openAnalysis()"
          />
          <a :href="comparisonUrl" target="_blank" rel="noreferrer" class="detail-link">
            <Button
              severity="contrast"
              outlined
              icon="pi pi-external-link"
              :label="t('predict.compareOnPortal')"
            />
          </a>
        </section>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
  .map-page,
  .metric-band,
  .rail-list,
  .detail-dialog,
  .detail-metrics {
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

  .active-filter-ribbon {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .active-filter-chip {
    display: inline-flex;
    align-items: center;
    min-height: 2.2rem;
    padding: 0.35rem 0.8rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--primary) 18%, var(--border));
    background: color-mix(in srgb, var(--primary-overlay) 62%, var(--surface-soft));
    color: var(--text);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .active-filter-chip.tone-low {
    border-color: color-mix(in srgb, var(--success) 26%, transparent);
    background: color-mix(in srgb, var(--success) 12%, var(--surface-soft));
  }

  .active-filter-chip.tone-mid {
    border-color: color-mix(in srgb, var(--warning) 32%, transparent);
    background: color-mix(in srgb, var(--warning) 12%, var(--surface-soft));
  }

  .active-filter-chip.tone-high {
    border-color: color-mix(in srgb, var(--danger) 26%, transparent);
    background: color-mix(in srgb, var(--danger) 10%, var(--surface-soft));
  }

  .filters-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .legend-strip {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
    align-items: stretch;
  }

  :deep(.legend-chip.p-button) {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.8rem 0.9rem;
    border-radius: 1rem;
    text-align: left;
    white-space: normal;
    height: auto;
  }

  :deep(.legend-chip.p-button:not(.p-button-outlined)) {
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    box-shadow: 0 18px 36px color-mix(in srgb, var(--primary) 12%, transparent);
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
    grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.6fr);
    gap: 1rem;
  }

  .map-container {
    min-height: 620px;
    border-radius: 1.5rem;
    overflow: hidden;
  }

  :deep(.rail-card.p-button) {
    display: grid;
    gap: 0.4rem;
    padding: 0.9rem;
    border-radius: 1rem;
    text-align: left;
    white-space: normal;
    height: auto;
    background: linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft));
    transition:
      transform 0.18s ease,
      border-color 0.18s ease,
      box-shadow 0.18s ease;
  }

  :deep(.rail-card.p-button:hover) {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 26%, transparent);
    box-shadow: 0 18px 30px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .rail-card-top,
  .rail-card-foot,
  .detail-summary,
  .detail-actions,
  .comparable-top,
  .comparable-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .detail-summary {
    align-items: flex-start;
  }

  .detail-metrics {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .detail-grid {
    display: grid;
    grid-template-columns: minmax(0, 0.95fr) minmax(0, 1fr) minmax(320px, 1.1fr);
    gap: 1rem;
    align-items: start;
  }

  .detail-section {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 1.25rem;
    background: linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft));
    min-width: 0;
  }

  .detail-section-main {
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--primary-overlay) 78%, transparent),
      var(--surface-soft)
    );
  }

  .detail-section-comparables {
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--warning-overlay) 72%, transparent),
      var(--surface-soft)
    );
  }

  .detail-section h3 {
    margin: 0;
  }

  .detail-list {
    display: grid;
    gap: 0.75rem;
    margin: 0;
  }

  .detail-list div {
    display: grid;
    gap: 0.2rem;
  }

  .detail-list dt {
    color: var(--text-muted);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .detail-list dd {
    margin: 0;
    font-weight: 600;
  }

  .flag-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.65rem;
  }

  .detail-actions-panel {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 1.25rem;
    background: linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft));
  }

  .flag-chip {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.6rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-muted);
    color: var(--text-muted);
    font-weight: 700;
  }

  .flag-chip.active {
    color: var(--text);
    border-color: color-mix(in srgb, var(--success) 28%, transparent);
    background: color-mix(in srgb, var(--success) 10%, transparent);
  }

  .comparables-list {
    display: grid;
    gap: 0.75rem;
  }

  .comparable-card {
    display: grid;
    gap: 0.45rem;
    padding: 0.9rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: var(--surface-muted);
  }

  .detail-link {
    text-decoration: none;
    display: block;
  }

  .detail-actions-panel :deep(.p-button) {
    width: 100%;
    justify-content: center;
  }

  .map-detail-dialog :deep(.p-dialog-header) {
    align-items: flex-start;
    padding: 1.15rem 1.35rem;
    border-bottom: 1px solid color-mix(in srgb, white 10%, transparent);
    background:
      linear-gradient(135deg, var(--surface-dark), var(--surface-dark-alt)),
      linear-gradient(135deg, var(--primary-overlay), transparent);
    color: var(--primary-contrast);
  }

  .map-detail-dialog :deep(.p-dialog-title),
  .map-detail-dialog :deep(.p-dialog-header-icon) {
    color: inherit;
  }

  .map-detail-dialog :deep(.p-dialog-content) {
    padding: 1.25rem 1.35rem 1.35rem;
  }

  .detail-summary h2 {
    margin: 0.2rem 0 0;
    font-size: 1.45rem;
  }

  .detail-summary .muted {
    margin: 0.25rem 0 0;
  }

  .comparables-list,
  .detail-list {
    min-width: 0;
  }

  @media (max-width: 1100px) {
    .legend-strip,
    .filters-grid,
    .explorer-grid,
    .detail-grid,
    .detail-actions-panel,
    .detail-metrics,
    .metric-band {
      grid-template-columns: 1fr;
    }

    .map-container {
      min-height: 460px;
    }
  }
</style>
