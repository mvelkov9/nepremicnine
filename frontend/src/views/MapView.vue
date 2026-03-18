<script setup>
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { watchDebounced } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import Button from 'primevue/button'
  import Dialog from 'primevue/dialog'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import AppDataTable from '../components/AppDataTable.vue'
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
  let mapRequestController = null
  let detailRequestController = null
  let latestMapRequestId = 0

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

  const bandColors = {
    low: '#22c55e',
    mid: '#f59e0b',
    high: '#ef4444',
  }

  const overviewColor = '#3b82f6'

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

  const requestParams = computed(() => {
    const params = {}
    if (selectedType.value) params.property_type = selectedType.value
    if (selectedRegion.value) params.statistical_region = selectedRegion.value
    if (selectedYear.value) params.year = selectedYear.value
    if (selectedMunicipality.value) params.municipality = selectedMunicipality.value
    if (selectedPriceBand.value) params.price_band = selectedPriceBand.value
    return params
  })

  const routeQueryState = computed(() => {
    const query = {}
    if (selectedType.value) query.property_type = selectedType.value
    if (selectedRegion.value) query.region = selectedRegion.value
    if (selectedYear.value) query.year = selectedYear.value
    if (selectedPriceBand.value) query.price_band = selectedPriceBand.value
    if (selectedMunicipality.value) query.municipality = selectedMunicipality.value
    if (viewMode.value !== 'transactions') query.view = viewMode.value
    return query
  })

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

  const regionStatsColumns = computed(() => [
    { key: 'region', label: t('map.region'), sortable: true },
    { key: 'count', label: t('map.transactions'), sortable: true },
    { key: 'avg_price', label: t('map.avgPrice'), sortable: true },
    { key: 'median_price', label: t('map.medianPrice'), sortable: true },
    { key: 'avg_price_per_m2', label: t('map.avgPricePerM2'), sortable: true },
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
    return bandColors[key] || overviewColor
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

  function dominantBand(counts = {}) {
    return Object.entries(counts).sort((left, right) => right[1] - left[1])[0]?.[0] || 'mid'
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

    if (detailRequestController) {
      detailRequestController.abort()
      detailRequestController = null
    }

    if (mode === 'transaction' && item?.municipality && item?.property_type && item?.size_m2) {
      detailLoading.value = true
      detailRequestController = new AbortController()
      try {
        const { data } = await api.get('/api/stats/comparables', {
          signal: detailRequestController.signal,
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
      } catch (error) {
        if (error?.code === 'ERR_CANCELED') {
          return
        }
        detailComparables.value = []
      } finally {
        detailLoading.value = false
        detailRequestController = null
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

  async function fetchTransactions(signal) {
    const { data } = await api.get('/api/stats/map-transactions', {
      signal,
      params: requestParams.value,
    })
    mapMetaReason.value = data.meta?.reason || null
    mapLegend.value = data.meta?.legend || null
    transactions.value = data.transactions || []
  }

  async function fetchOverviewMarkers(signal) {
    const { data } = await api.get('/api/stats/map-overview', {
      signal,
      params: requestParams.value,
    })
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
    const requestId = ++latestMapRequestId

    if (mapRequestController) {
      mapRequestController.abort()
    }
    mapRequestController = new AbortController()

    loading.value = true
    error.value = ''
    mapMetaReason.value = null

    try {
      if (viewMode.value === 'transactions') {
        await fetchTransactions(mapRequestController.signal)
      } else {
        await fetchOverviewMarkers(mapRequestController.signal)
      }

      if (requestId !== latestMapRequestId) {
        return
      }

      await nextTick()
      map?.invalidateSize()
      renderMarkers()
    } catch (err) {
      if (err?.code === 'ERR_CANCELED') {
        return
      }
      error.value = getApiErrorMessage(err, t)
    } finally {
      if (requestId === latestMapRequestId) {
        loading.value = false
      }
      if (mapRequestController?.signal?.aborted || requestId === latestMapRequestId) {
        mapRequestController = null
      }
    }
  }

  async function syncRouteQuery() {
    const nextQuery = routeQueryState.value
    const currentQuery = {
      ...(route.query.property_type ? { property_type: String(route.query.property_type) } : {}),
      ...(route.query.region ? { region: String(route.query.region) } : {}),
      ...(route.query.year ? { year: String(route.query.year) } : {}),
      ...(route.query.price_band ? { price_band: String(route.query.price_band) } : {}),
      ...(route.query.municipality ? { municipality: String(route.query.municipality) } : {}),
      ...(route.query.view ? { view: String(route.query.view) } : {}),
    }

    if (JSON.stringify(currentQuery) === JSON.stringify(nextQuery)) {
      return
    }

    await router.replace({ query: nextQuery })
  }

  function clearFilters() {
    selectedType.value = ''
    selectedRegion.value = ''
    selectedMunicipality.value = ''
    selectedPriceBand.value = ''
    selectedYear.value = defaultYear.value ? String(defaultYear.value) : ''
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
    selectedMunicipality.value = route.query.municipality ? String(route.query.municipality) : ''
    viewMode.value = route.query.view === 'overview' ? 'overview' : 'transactions'
  }

  watch(selectedRegion, (nextRegion) => {
    if (!selectedMunicipality.value) return
    const stillVisible = allMunicipalities.value.some(
      (item) =>
        item.municipality === selectedMunicipality.value &&
        (!nextRegion || item.region === nextRegion),
    )
    if (!stillVisible) {
      selectedMunicipality.value = ''
    }
  })

  watchDebounced(
    [selectedType, selectedRegion, selectedYear, selectedMunicipality, selectedPriceBand, viewMode],
    async () => {
      if (!initialized.value) return
      await syncRouteQuery()
      await fetchData()
    },
    { debounce: 220, maxWait: 800 },
  )

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
    if (mapRequestController) {
      mapRequestController.abort()
      mapRequestController = null
    }
    if (detailRequestController) {
      detailRequestController.abort()
      detailRequestController = null
    }
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
            <small>{{ band.range || t('map.allBandsHint') }} · {{ fmt(band.count) }}</small>
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

      <AppDataTable
        :rows="regionStats"
        :columns="regionStatsColumns"
        row-key="region"
        :page-size="8"
        :empty-message="t('empty.noResults')"
      >
        <template #cell-count="{ row }">{{ fmt(row.count) }}</template>
        <template #cell-avg_price="{ row }">{{ fmtCurrency(row.avg_price) }}</template>
        <template #cell-median_price="{ row }">{{ fmtCurrency(row.median_price) }}</template>
        <template #cell-avg_price_per_m2="{ row }">{{ fmtCurrency(row.avg_price_per_m2) }}</template>
      </AppDataTable>
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
    grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.6fr);
    gap: 1rem;
  }

  .map-container {
    min-height: 620px;
    border-radius: 1.5rem;
    overflow: hidden;
  }

  .rail-card {
    display: grid;
    gap: 0.4rem;
    padding: 0.9rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    text-align: left;
    color: inherit;
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
    background: var(--surface-soft);
    min-width: 0;
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
    background: var(--surface-soft);
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
    border-color: rgb(34 197 94 / 28%);
    background: rgb(34 197 94 / 10%);
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
