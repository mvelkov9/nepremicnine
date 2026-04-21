<script setup lang="ts">
  import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useDebounceFn } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  /* PrimeVue components (Button, Column, DataTable, Dialog, Select, Tag) are auto-imported */
  import L from 'leaflet'
  import 'leaflet/dist/leaflet.css'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MapDetailDialog from '../components/map/MapDetailDialog.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import MapWorkspaceRail from '../features/map/MapWorkspaceRail.vue'
  import { toLocationQuery } from '../constants/workbench'
  import api from '../composables/useApi'
  import { useFilterOptions } from '../composables/useFilterOptions'
  import { useReferenceDataStore } from '../stores/referenceData'
  import { useWorkbenchStore } from '../stores/workbench'
  import { useFormat } from '../composables/useFormat'
  import { getApiErrorMessage } from '../utils/apiError'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { municipalitySlug } from '../utils/municipality'
  import type { TransactionRecord } from '../types/api'

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

  interface MapLegendThresholds {
    low_max?: number | null
    mid_max?: number | null
  }

  interface MapLegendPayload {
    thresholds?: MapLegendThresholds | null
    counts?: Record<string, number> | null
  }

  interface MapActionState {
    canUse: boolean
    reason: string
  }

  interface MapSelectableRecordBase {
    municipality: string
    region?: string | null
    naselje?: string | null
    lat?: number | null
    lon?: number | null
    property_type?: string | null
    size_m2?: number | null
    price_eur?: number | null
    year?: string | null
    source_label?: string | null
    year_built?: number | null
    rooms?: number | null
    floor?: number | null
    lega_v_stavbi?: string | null
    clusterCount?: number
  }

  interface MapTransactionRecord
    extends Omit<TransactionRecord, 'slug' | 'naselje'>, MapSelectableRecordBase {
    slug?: string
    avg_price?: number | null
    avg_price_per_m2?: number | null
    price_band?: string | null
  }

  interface MapMunicipalityRecord extends MapSelectableRecordBase {
    count: number
    avg_price?: number | null
    avg_price_per_m2?: number | null
    median_price?: number | null
    latest_year?: string | null
    price_band?: string | null
    slug?: string
  }

  interface MapRegionStatRecord {
    region: string
    count: number
    avg_price?: number | null
    median_price?: number | null
    avg_price_per_m2?: number | null
  }

  type MapSelectableRecord = MapTransactionRecord | MapMunicipalityRecord

  const { t } = useI18n()
  const { fmt, fmtCurrency, formatType } = useFormat()
  const route = useRoute()
  const router = useRouter()
  const referenceData = useReferenceDataStore()
  const workbench = useWorkbenchStore()

  const mapContainer = ref<HTMLElement | null>(null)
  let map: L.Map | null = null
  let markersLayer: L.LayerGroup | null = null

  const initialized = ref(false)
  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref('')
  const detailError = ref('')
  const mapMetaReason = ref<string | null>(null)
  const mapLegend = ref<MapLegendPayload | null>(null)
  const selectedType = ref('')
  const selectedRegion = ref('')
  const selectedYear = ref('')
  const selectedMunicipality = ref('')
  const selectedPriceBand = ref('')
  const viewMode = ref<'transactions' | 'overview'>('transactions')
  const mapTab = ref<'workspace' | 'regions'>('workspace')
  const mapZoom = ref(8)

  const municipalities = ref<MapMunicipalityRecord[]>([])
  const regionStats = ref<MapRegionStatRecord[]>([])
  const transactions = ref<MapTransactionRecord[]>([])
  const detailComparables = ref<TransactionRecord[]>([])

  const detailVisible = ref(false)
  const detailMode = ref<'transaction' | 'overview'>('transaction')
  const selectedRecord = ref<MapSelectableRecord | null>(null)
  let syncingRoute = false
  let writingRoute = false
  let activeMapRequestController: AbortController | null = null
  let activeDetailRequestController: AbortController | null = null
  let mapRequestToken = 0
  let detailRequestToken = 0
  const validPriceBands = new Set(['low', 'mid', 'high'])

  function semanticColor(name: string, fallback: string) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    return value || fallback
  }

  const overviewColor = computed(() =>
    semanticColor('--chart-1', semanticColor('--primary', '#3b82f6')),
  )
  const markerStrokeColor = computed(() => semanticColor('--map-marker-stroke', '#20354d'))

  const defaultYear = computed(() => {
    if (!referenceData.years.length) return ''
    const currentYear = new Date().getFullYear()
    return (
      referenceData.years.find((year) => Number(year) < currentYear) || referenceData.years[0] || ''
    )
  })

  const { propertyTypeOptions, regionOptions, municipalityOptions, yearOptions } = useFilterOptions(
    {
      region: selectedRegion,
      labels: {
        allPropertyTypes: 'map.allTypes',
        allRegions: 'map.allRegions',
      },
    },
  )

  const totalCount = computed(() =>
    viewMode.value === 'transactions'
      ? transactions.value.length
      : municipalities.value.reduce((sum, item) => sum + item.count, 0),
  )
  const visibleMunicipalityCount = computed(() => {
    if (viewMode.value === 'overview') return municipalities.value.length

    return new Set(
      transactions.value
        .map((item) => item.municipality)
        .filter((value): value is string => typeof value === 'string' && value.trim().length > 0),
    ).size
  })

  const avgPrice = computed(() => {
    const values =
      viewMode.value === 'transactions'
        ? transactions.value.map((item) => item.price_eur).filter(Boolean)
        : municipalities.value.map((item) => item.avg_price).filter(Boolean)
    if (!values.length) return null
    return values.reduce((sum, value) => sum + value, 0) / values.length
  })

  const clusteredTransactions = computed(() =>
    clusterTransactions(transactions.value, mapZoom.value),
  )

  const heroRecord = computed(() => {
    if (viewMode.value === 'transactions') {
      return (
        transactions.value.find((item) => isActionableTransactionRecord(item)) ||
        transactions.value[0] ||
        null
      )
    }
    return municipalities.value[0] || null
  })

  const heroActionState = computed(() => getMapActionState(heroRecord.value, viewMode.value))
  const selectedActionState = computed(() =>
    getMapActionState(selectedRecord.value, detailMode.value),
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
  const selectedFilterCount = computed(
    () =>
      [
        selectedType.value,
        selectedRegion.value,
        selectedYear.value,
        selectedMunicipality.value,
        selectedPriceBand.value,
      ].filter(Boolean).length,
  )
  const selectedFilterTag = computed(() =>
    selectedFilterCount.value > 0
      ? t('dashboard.activeFilterCount', { count: selectedFilterCount.value })
      : t('dashboard.noActiveFilters'),
  )

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
      return `${selectedRecord.value.municipality} | ${formatType(selectedRecord.value.property_type)}`
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

  function bandColor(key) {
    const bandColors = {
      low: semanticColor('--chart-3', semanticColor('--success', '#22c55e')),
      mid: semanticColor('--chart-4', semanticColor('--warning', '#f59e0b')),
      high: semanticColor('--chart-5', semanticColor('--danger', '#ef4444')),
    }

    return bandColors[key] || overviewColor.value
  }

  function bandRangeLabel(key) {
    const thresholds = mapLegend.value?.thresholds
    if (!thresholds) return ''
    if (key === 'low') return `<= ${fmtCurrency(thresholds.low_max)}`
    if (key === 'mid') {
      return `${fmtCurrency(thresholds.low_max)} - ${fmtCurrency(thresholds.mid_max)}`
    }
    return `>= ${fmtCurrency(thresholds.mid_max)}`
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

  function isCancelledRequest(error: unknown) {
    const candidate = error as { code?: string; name?: string }
    return candidate?.code === 'ERR_CANCELED' || candidate?.name === 'CanceledError'
  }

  function hasText(value: unknown) {
    return typeof value === 'string'
      ? value.trim().length > 0
      : String(value ?? '').trim().length > 0
  }

  function toNumber(value: unknown) {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value)
      return Number.isFinite(parsed) ? parsed : null
    }
    return null
  }

  function getMunicipalityReference(name: string) {
    return referenceData.municipalities.find((item) => item.municipality === name) || null
  }

  function isRecordObject(value: unknown): value is Record<string, unknown> {
    return !!value && typeof value === 'object'
  }

  function isActionableTransactionRecord(record: unknown): record is MapTransactionRecord {
    if (!isRecordObject(record)) return false
    return Boolean(
      record &&
      hasText(record.municipality) &&
      hasText(record.property_type) &&
      toNumber(record.size_m2) != null,
    )
  }

  function getMapActionState(
    record: MapSelectableRecord | null,
    mode: 'transaction' | 'transactions' | 'overview',
  ): MapActionState {
    if (!record) {
      return {
        canUse: false,
        reason: t('common.noData'),
      }
    }

    if (mode === 'overview') {
      return {
        canUse: false,
        reason: t('map.municipalitySummaryHint'),
      }
    }

    const missing: string[] = []
    if (!hasText(record.municipality)) missing.push(t('map.municipalityFilter'))
    if (!hasText(record.property_type)) missing.push(t('predict.propertyType'))
    if (toNumber(record.size_m2) == null) missing.push(t('predict.size'))

    if (!missing.length) {
      return { canUse: true, reason: '' }
    }

    return {
      canUse: false,
      reason: t('map.drawerHint'),
    }
  }

  function normalizeSelectionState() {
    if (!referenceData.loaded) return false

    const previousSyncing = syncingRoute
    syncingRoute = true
    let changed = false

    try {
      if (selectedType.value && !referenceData.propertyTypes.includes(selectedType.value)) {
        selectedType.value = ''
        changed = true
      }

      if (selectedYear.value && !referenceData.years.includes(selectedYear.value)) {
        selectedYear.value = defaultYear.value ? String(defaultYear.value) : ''
        changed = true
      }

      if (selectedPriceBand.value && !validPriceBands.has(selectedPriceBand.value)) {
        selectedPriceBand.value = ''
        changed = true
      }

      const municipalityRef = selectedMunicipality.value
        ? getMunicipalityReference(selectedMunicipality.value)
        : null

      if (selectedRegion.value && !referenceData.regions.includes(selectedRegion.value)) {
        selectedRegion.value = municipalityRef?.region || ''
        changed = true
      }

      if (municipalityRef?.region && selectedRegion.value !== municipalityRef.region) {
        selectedRegion.value = municipalityRef.region
        changed = true
      }

      if (selectedMunicipality.value && !municipalityRef) {
        selectedMunicipality.value = ''
        changed = true
      }

      if (selectedRegion.value && selectedMunicipality.value) {
        const matchesRegion = referenceData.municipalities.some(
          (item) =>
            item.region === selectedRegion.value &&
            item.municipality === selectedMunicipality.value,
        )
        if (!matchesRegion) {
          selectedMunicipality.value = ''
          changed = true
        }
      }

      if (!selectedRegion.value && municipalityRef?.region) {
        selectedRegion.value = municipalityRef.region
        changed = true
      }
    } finally {
      syncingRoute = previousSyncing
    }

    return changed
  }

  function buildScenarioQuery(item: MapSelectableRecord | null = heroRecord.value) {
    const municipality = item?.municipality || selectedMunicipality.value || ''
    const propertyType = item?.property_type || selectedType.value || ''

    return toLocationQuery({
      municipality,
      naselje: item?.naselje || '',
      property_type: propertyType || undefined,
      size_m2: item?.size_m2 || '',
      year_built: item?.year_built || '',
      floor: item?.floor ?? '',
      price_eur: item?.price_eur || item?.avg_price || '',
      asking_price: item?.price_eur || item?.avg_price || '',
      price_band: item?.price_band || selectedPriceBand.value || undefined,
      region: item?.region || selectedRegion.value || undefined,
    })
  }

  function clusterTransactions(
    items: MapTransactionRecord[],
    zoom: number,
  ): MapTransactionRecord[] {
    if (zoom >= 12 || items.length <= 1200) return items

    const cellSize = zoom <= 7 ? 0.25 : zoom <= 9 ? 0.12 : 0.05
    const buckets = new Map<
      string,
      {
        id: string
        lat: number
        lon: number
        count: number
        clusterCount: number
        sample: MapTransactionRecord
        priceSum: number
        pricePerM2Sum: number
        pricePerM2Count: number
        municipality?: string | null
        region?: string | null
        price_band_counts: Record<string, number>
      }
    >()

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

  function focusMapItem(item: MapSelectableRecord | null, zoomOverride: number | null = null) {
    if (!map || !item?.lat || !item?.lon) return
    map.flyTo([item.lat, item.lon], zoomOverride || (viewMode.value === 'transactions' ? 11 : 9), {
      duration: 0.45,
    })
  }

  async function openDetails(
    item: MapSelectableRecord,
    mode: 'transaction' | 'overview' = 'transaction',
  ) {
    if (mode === 'transaction' && item.clusterCount > 1) {
      focusMapItem(item, Math.min((map?.getZoom() || 8) + 2, 12))
      return
    }

    detailRequestToken += 1
    const requestToken = detailRequestToken
    activeDetailRequestController?.abort()
    activeDetailRequestController = null
    selectedRecord.value = item
    detailMode.value = mode
    detailVisible.value = true
    detailError.value = ''
    detailLoading.value = false
    detailComparables.value = []
    focusMapItem(item)

    if (mode === 'transaction' && item?.municipality && item?.property_type && item?.size_m2) {
      detailLoading.value = true
      const controller = new AbortController()
      activeDetailRequestController = controller
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
          signal: controller.signal,
        })

        if (requestToken !== detailRequestToken || controller.signal.aborted) return

        detailComparables.value = data.items || []
      } catch (err) {
        if (requestToken !== detailRequestToken || controller.signal.aborted) return
        detailComparables.value = []
        detailError.value = getApiErrorMessage(err, t)
      } finally {
        if (activeDetailRequestController === controller) {
          activeDetailRequestController = null
        }
        if (requestToken === detailRequestToken) {
          detailLoading.value = false
        }
      }
    }
  }

  function renderTransactionMarkers() {
    if (!markersLayer) return
    markersLayer.clearLayers()

    for (const item of clusteredTransactions.value) {
      if (item.lat == null || item.lon == null) continue
      const radius = markerRadius(item.clusterCount || 1)
      const marker = L.circleMarker([item.lat, item.lon], {
        radius,
        fillColor: bandColor(item.price_band),
        color: markerStrokeColor.value,
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
      if (item.lat == null || item.lon == null) continue
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: markerRadius(item.count),
        fillColor: bandColor(item.price_band) || overviewColor.value,
        color: markerStrokeColor.value,
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

  function resetDetailState() {
    detailRequestToken += 1
    activeDetailRequestController?.abort()
    activeDetailRequestController = null
    detailVisible.value = false
    detailLoading.value = false
    detailError.value = ''
    selectedRecord.value = null
    detailComparables.value = []
  }

  watch(detailVisible, (visible, previous) => {
    if (!visible && previous) {
      detailRequestToken += 1
      activeDetailRequestController?.abort()
      activeDetailRequestController = null
      detailLoading.value = false
      detailError.value = ''
      detailComparables.value = []
    }
  })

  function clearMapResults(mode: 'transactions' | 'overview' | 'all' = 'all') {
    if (mode === 'all' || mode === 'transactions') {
      transactions.value = []
    }
    if (mode === 'all' || mode === 'overview') {
      municipalities.value = []
    }
    if (mode === 'all') {
      regionStats.value = []
    }

    mapLegend.value = null
    mapMetaReason.value = null
    markersLayer?.clearLayers()
    resetDetailState()
  }

  async function fetchTransactions(signal?: AbortSignal) {
    const params: MapFilterParams = {}
    if (selectedType.value) params.property_type = selectedType.value
    if (selectedRegion.value) params.statistical_region = selectedRegion.value
    if (selectedYear.value) params.year = selectedYear.value
    if (selectedMunicipality.value) params.municipality = selectedMunicipality.value
    if (selectedPriceBand.value) params.price_band = selectedPriceBand.value

    const { data } = await api.get('/api/stats/map-transactions', { params, signal })
    mapMetaReason.value = data.meta?.reason || null
    mapLegend.value = data.meta?.legend || null
    transactions.value = data.transactions || []
  }

  async function fetchOverviewMarkers(signal?: AbortSignal) {
    const params: MapFilterParams = {}
    if (selectedType.value) params.property_type = selectedType.value
    if (selectedRegion.value) params.statistical_region = selectedRegion.value
    if (selectedYear.value) params.year = selectedYear.value
    if (selectedMunicipality.value) params.municipality = selectedMunicipality.value
    if (selectedPriceBand.value) params.price_band = selectedPriceBand.value

    const { data } = await api.get('/api/stats/map-overview', { params, signal })
    mapMetaReason.value = data.meta?.reason || null
    mapLegend.value = data.meta?.legend || null
    municipalities.value = data.municipalities || []
  }

  async function loadReferenceData() {
    const [regionsRes] = await Promise.allSettled([
      api.get('/api/stats/regions'),
      referenceData.ensureLoaded(),
    ])

    regionStats.value = regionsRes.status === 'fulfilled' ? regionsRes.value.data || [] : []

    if (!selectedYear.value && defaultYear.value) {
      selectedYear.value = String(defaultYear.value)
    }

    if (normalizeSelectionState()) {
      syncRouteQuery()
    }
  }

  async function initializePage() {
    applyRouteQuery()
    if (!map) initMap()
    error.value = ''

    try {
      await loadReferenceData()
      normalizeSelectionState()
      initialized.value = true
      await fetchData()
    } catch (err) {
      clearMapResults('all')
      error.value = getApiErrorMessage(err, t)
    }
  }

  async function fetchData() {
    const requestToken = ++mapRequestToken
    activeMapRequestController?.abort()
    const controller = new AbortController()
    activeMapRequestController = controller
    loading.value = true
    error.value = ''
    mapMetaReason.value = null

    try {
      if (viewMode.value === 'transactions') {
        await fetchTransactions(controller.signal)
      } else {
        await fetchOverviewMarkers(controller.signal)
      }

      if (controller.signal.aborted || requestToken !== mapRequestToken) return

      await nextTick()
      map?.invalidateSize()
      renderMarkers()
    } catch (err) {
      if (controller.signal.aborted || isCancelledRequest(err)) return
      clearMapResults(viewMode.value)
      error.value = getApiErrorMessage(err, t)
    } finally {
      if (activeMapRequestController === controller) activeMapRequestController = null
      if (requestToken === mapRequestToken) loading.value = false
    }
  }

  const debouncedFetchData = useDebounceFn(() => {
    void fetchData()
  }, 220)

  function clearFilters() {
    selectedType.value = ''
    selectedRegion.value = ''
    selectedMunicipality.value = ''
    selectedPriceBand.value = ''
    selectedYear.value = defaultYear.value ? String(defaultYear.value) : ''
    if (referenceData.loaded) {
      syncRouteQuery()
    }
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
      price_band: selectedPriceBand.value || undefined,
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

  function useForPrediction(item: MapSelectableRecord | null = selectedRecord.value) {
    router.push({
      name: 'prediction',
      query: buildScenarioQuery(item),
    })
  }

  function useHeroPrediction() {
    useForPrediction(heroRecord.value || selectedRecord.value)
  }

  function openMarketExplorer() {
    router.push({
      name: 'market',
      query: viewerRouteQuery({
        tab: viewMode.value === 'transactions' ? 'transactions' : 'overview',
      }),
    })
  }

  function openAnalysis(item: MapSelectableRecord | null = selectedRecord.value) {
    router.push({
      name: 'analysis',
      query: buildScenarioQuery(item),
    })
  }

  function openHeroAnalysis() {
    openAnalysis(heroRecord.value || selectedRecord.value)
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
      if (initialized.value) debouncedFetchData()
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
      const normalized = referenceData.loaded ? normalizeSelectionState() : false
      if (normalized) syncRouteQuery()
      if (initialized.value) debouncedFetchData()
    },
  )

  watch(selectedRegion, (region) => {
    if (syncingRoute || !selectedMunicipality.value) return
    const municipalityRef = getMunicipalityReference(selectedMunicipality.value)
    if (!region) {
      if (municipalityRef?.region) {
        selectedRegion.value = municipalityRef.region
      } else {
        selectedMunicipality.value = ''
      }
      return
    }
    const valid = referenceData.municipalities.some(
      (item) => item.region === region && item.municipality === selectedMunicipality.value,
    )
    if (!valid) selectedMunicipality.value = ''
  })

  watch(selectedMunicipality, (municipality) => {
    if (syncingRoute || !municipality) return
    const match = getMunicipalityReference(municipality)
    if (match?.region && selectedRegion.value !== match.region) {
      selectedRegion.value = match.region
    }
  })

  onMounted(() => {
    void initializePage()
  })

  onBeforeUnmount(() => {
    activeMapRequestController?.abort()
    if (map) {
      map.remove()
      map = null
    }
  })
</script>

<template>
  <div class="map-page">
    <section class="hero-shell map-hero">
      <PageHeader
        :eyebrow="t('map.title')"
        :title="t('map.explorerTitle')"
        :description="t('map.explorerBody')"
      >
        <template #actions>
          <SavedWorkspaceMenu
            page="map"
            :state="{ page: 'map', tab: mapTab, filters: viewerRouteQuery({ view: viewMode }) }"
          />
          <Button
            icon="pi pi-chart-line"
            :label="t('map.useFiltersForPrediction')"
            :disabled="!heroActionState.canUse"
            :title="heroActionState.reason || undefined"
            @click="useHeroPrediction"
          />
        </template>
      </PageHeader>

      <div class="metric-band">
        <MetricCard :label="t('map.totalTransactions')" :value="fmt(totalCount)" />
        <MetricCard :label="t('map.avgPrice')" :value="fmtCurrency(avgPrice)" />
        <MetricCard :label="t('map.municipalities')" :value="fmt(visibleMunicipalityCount)" />
        <MetricCard :label="t('map.regions')" :value="fmt(referenceData.regions.length)" />
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

    <Tabs v-model:value="mapTab" class="map-tabs">
      <TabList>
        <Tab value="workspace">{{ t('common.overview') }}</Tab>
        <Tab value="regions">{{ t('map.regionSnapshot') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="workspace">
          <section class="map-workbench map-tab-content">
            <article class="card map-panel">
              <div class="map-panel-header">
                <div>
                  <span class="eyebrow">{{
                    viewMode === 'transactions' ? t('map.transactionView') : t('map.overviewMode')
                  }}</span>
                  <h3>
                    {{
                      viewMode === 'transactions'
                        ? t('map.activityFeed')
                        : t('map.topMunicipalities')
                    }}
                  </h3>
                  <p>
                    {{ viewMode === 'transactions' ? t('map.drawerHint') : t('map.overviewHint') }}
                  </p>
                </div>
                <Tag
                  :severity="selectedFilterCount > 0 ? 'contrast' : 'secondary'"
                  :value="selectedFilterTag"
                />
              </div>

              <div class="map-shell">
                <div
                  ref="mapContainer"
                  class="map-container"
                  role="region"
                  :aria-label="t('map.title')"
                ></div>
                <div v-if="loading || error || mapStateMessage" class="map-overlay">
                  <div v-if="loading" class="card state-card state-card-overlay" aria-busy="true">
                    <LoadingSpinner :label="t('map.loading')" />
                  </div>
                  <div
                    v-else-if="error"
                    class="card state-card state-card-overlay state-card-stack"
                    role="alert"
                  >
                    <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
                    <div class="state-card-actions">
                      <Button
                        size="small"
                        severity="secondary"
                        outlined
                        icon="pi pi-refresh"
                        :label="t('common.retry')"
                        @click="initializePage"
                      />
                    </div>
                  </div>
                  <div v-else-if="mapStateMessage" class="card state-card state-card-overlay">
                    <EmptyState icon="pi pi-info-circle" :message="mapStateMessage" />
                  </div>
                </div>
              </div>
            </article>

            <MapWorkspaceRail
              v-model:view-mode="viewMode"
              v-model:selected-type="selectedType"
              v-model:selected-region="selectedRegion"
              v-model:selected-year="selectedYear"
              v-model:selected-municipality="selectedMunicipality"
              v-model:selected-price-band="selectedPriceBand"
              :selected-filter-count="selectedFilterCount"
              :selected-filter-tag="selectedFilterTag"
              :property-type-options="propertyTypeOptions"
              :region-options="regionOptions"
              :year-options="yearOptions"
              :municipality-options="municipalityOptions"
              :band-options="bandOptions"
              :hero-action-can-use="heroActionState.canUse"
              :hero-action-reason="heroActionState.reason"
              @clear-filters="clearFilters"
              @open-market="openMarketExplorer"
              @open-analysis="openHeroAnalysis"
            />
          </section>
        </TabPanel>

        <TabPanel value="regions">
          <section class="map-tab-content">
            <SectionPanel :eyebrow="t('map.regionStats')" :title="t('map.regionSnapshot')" compact>
              <p class="section-note">{{ t('map.regionSnapshotHint') }}</p>
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
            </SectionPanel>
          </section>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <MapDetailDialog
      v-model:visible="detailVisible"
      :record="selectedRecord"
      :detail-mode="detailMode"
      :detail-loading="detailLoading"
      :detail-error="detailError"
      :comparables="detailComparables"
      :default-year="defaultYear"
      :comparison-url="comparisonUrl"
      :dialog-title="detailDialogTitle"
      :can-open-municipality="Boolean(selectedRecord?.municipality)"
      :municipality-disabled-reason="selectedRecord?.municipality ? '' : t('common.noData')"
      :can-use-for-prediction="selectedActionState.canUse"
      :prediction-disabled-reason="selectedActionState.reason"
      :can-open-analysis="selectedActionState.canUse"
      :analysis-disabled-reason="selectedActionState.reason"
      @open-municipality="openMunicipality()"
      @use-for-prediction="useForPrediction(selectedRecord || heroRecord)"
      @open-analysis="openAnalysis(selectedRecord || heroRecord)"
    />
  </div>
</template>

<style scoped>
  .map-page,
  .metric-band {
    display: grid;
    gap: 1rem;
  }

  .map-tabs,
  .map-tab-content {
    display: grid;
    gap: 1rem;
  }

  .map-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 18%);
    border-radius: var(--radius-lg);
    background: color-mix(in srgb, var(--surface-strong) 92%, var(--primary-overlay) 8%);
    box-shadow: 0 10px 22px color-mix(in srgb, var(--shadow-color) 8%, transparent);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .map-tabs :deep(.p-tabpanels) {
    padding-top: 0.15rem;
  }

  .map-page {
    gap: var(--space-section);
    animation: map-in 420ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .map-hero,
  .map-panel,
  .state-card {
    display: grid;
    gap: 1rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
    transition:
      border-color 170ms ease,
      box-shadow 170ms ease,
      transform 170ms ease;
  }

  .map-hero:hover,
  .map-panel:hover,
  .state-card:hover {
    border-color: color-mix(in srgb, var(--border) 58%, var(--primary) 42%);
    box-shadow: 0 20px 42px color-mix(in srgb, var(--shadow-color) 14%, transparent);
    transform: translateY(-1px);
  }

  .map-hero,
  .map-panel,
  .state-card,
  .card {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 88%, transparent),
        transparent 38%
      ),
      var(--surface-panel);
  }

  .map-hero {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 76%, transparent),
        var(--surface-soft)
      ),
      var(--surface-soft);
  }

  .metric-band {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .map-workbench {
    display: grid;
    grid-template-columns: minmax(0, 1.9fr) minmax(320px, 0.82fr);
    gap: 1rem;
    align-items: start;
  }

  .map-workbench :deep(.map-workspace-rail) {
    position: sticky;
    top: 5.75rem;
  }

  .map-panel {
    gap: 0.95rem;
  }

  .map-panel-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .map-panel-header h3 {
    margin: 0.2rem 0 0;
    font-size: clamp(1.08rem, 1.3vw, 1.28rem);
  }

  .map-panel-header p {
    margin: 0.25rem 0 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
  }

  .map-shell {
    position: relative;
    min-height: clamp(680px, 78vh, 920px);
    border-radius: var(--radius-lg);
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-panel) 94%, transparent),
        var(--surface-panel)
      ),
      var(--surface-panel);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
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
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 84%,
      var(--primary) 16%
    );
    color: var(--text);
    font-size: var(--text-sm);
    font-weight: 700;
    box-shadow: inset 0 1px 0 var(--glass-highlight);
    transition:
      border-color 140ms ease,
      transform 140ms ease,
      box-shadow 140ms ease;
  }

  .active-filter-chip:hover {
    transform: translateY(-1px);
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      0 10px 20px color-mix(in srgb, var(--shadow-color) 10%, transparent);
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

  .section-note {
    margin: -0.25rem 0 0;
    color: var(--text-muted);
    font-size: var(--text-sm);
  }

  .map-container {
    min-height: inherit;
    border-radius: inherit;
    overflow: hidden;
  }

  .map-overlay {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 1rem;
    pointer-events: none;
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--surface-panel) 18%, transparent),
      color-mix(in srgb, var(--surface-panel) 36%, transparent)
    );
  }

  .state-card-overlay {
    width: min(100%, 420px);
    pointer-events: auto;
    box-shadow: var(--shadow-lg);
  }
  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }
  .state-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
    justify-content: center;
  }

  @keyframes map-in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 1220px) {
    .map-workbench {
      grid-template-columns: 1fr;
    }

    .map-workbench :deep(.map-workspace-rail) {
      position: static;
    }
  }

  @media (max-width: 1100px) {
    .map-shell,
    .map-container {
      min-height: 520px;
    }

    .map-panel-header {
      flex-direction: column;
    }
  }

  @media (max-width: 720px) {
    .map-shell,
    .map-container {
      min-height: 440px;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .map-page {
      animation: none;
    }

    .map-hero,
    .map-panel,
    .state-card,
    .active-filter-chip {
      transition: none;
    }

    .map-hero:hover,
    .map-panel:hover,
    .state-card:hover,
    .active-filter-chip:hover {
      transform: none;
    }
  }
</style>
