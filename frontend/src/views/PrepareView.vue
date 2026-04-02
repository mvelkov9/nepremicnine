<script setup lang="ts">
  import { ref, onMounted, onUnmounted, computed, reactive, watch } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AdminRunDetailPanel from '../components/admin/AdminRunDetailPanel.vue'
  import PageHeader from '../components/PageHeader.vue'
  import MetricCard from '../components/MetricCard.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useWorkbenchStore } from '../stores/workbench'
  import api from '../composables/useApi'
  import { getApiErrorMessage } from '../utils/apiError'
  import { buildGursEnrichmentRows, summarizeGursEnrichment } from '../utils/enrichmentSummary'
  import { formatNumber } from '../utils/format'

  const { t } = useI18n()
  const dataStore = useDataStore()
  const modelStore = useModelStore()
  const workbench = useWorkbenchStore()
  const router = useRouter()

  const loading = ref(false)
  const error = ref('')
  const result = ref(null)
  const prepareStatus = ref(null)
  const preparePollTimer = ref<ReturnType<typeof setInterval> | null>(null)
  const selectedPrepareRunId = ref('')
  const enrichmentOptions = reactive({
    enable_rn: true,
    enable_ev: true,
    enable_kn: true,
    enable_gji: true,
    enable_dtm: true,
    enable_emv: true,
    variant_label: '',
  })

  interface PrepareJobStatus {
    job_id: string
    status: 'queued' | 'running' | 'completed' | 'failed'
    stage: string | null
    progress: number
    total_pairs?: number | null
    current_pair_index?: number | null
    current_label?: string | null
    pairs_completed?: number | null
    rows?: number | null
    spatial_phase?: string | null
    result?: Record<string, unknown> | null
    error?: string | null
  }

  interface EtnDatasetRef {
    id?: number
    original_name: string
    relative_path: string
  }

  interface EtnDetectedPair {
    year: number
    posli: EtnDatasetRef | null
    delistavb: EtnDatasetRef | null
    zemljisca: EtnDatasetRef | null
  }

  const ENRICHMENT_OPTIONS = [
    {
      key: 'enable_rn' as const,
      titleKey: 'prepare.enableRn',
      descKey: 'prepare.enableRnDesc',
      filesKey: 'prepare.enableRnFiles',
      icon: 'pi-map-marker',
    },
    {
      key: 'enable_ev' as const,
      titleKey: 'prepare.enableEv',
      descKey: 'prepare.enableEvDesc',
      filesKey: 'prepare.enableEvFiles',
      icon: 'pi-building',
    },
    {
      key: 'enable_kn' as const,
      titleKey: 'prepare.enableKn',
      descKey: 'prepare.enableKnDesc',
      filesKey: 'prepare.enableKnFiles',
      icon: 'pi-map',
    },
    {
      key: 'enable_gji' as const,
      titleKey: 'prepare.enableGji',
      descKey: 'prepare.enableGjiDesc',
      filesKey: 'prepare.enableGjiFiles',
      icon: 'pi-bolt',
    },
    {
      key: 'enable_dtm' as const,
      titleKey: 'prepare.enableDtm',
      descKey: 'prepare.enableDtmDesc',
      filesKey: 'prepare.enableDtmFiles',
      icon: 'pi-wave-pulse',
    },
    {
      key: 'enable_emv' as const,
      titleKey: 'prepare.enableEmv',
      descKey: 'prepare.enableEmvDesc',
      filesKey: 'prepare.enableEmvFiles',
      icon: 'pi-chart-bar',
    },
  ]

  // ETN pair mode
  const etnMode = ref('bulk') // 'bulk' | 'single' | 'manual'
  const singlePosli = ref('')
  const singleDelistavb = ref('')

  // Manual column mapping
  const manualCsvPath = ref('')
  const columnMap = ref('')
  const columnMapPlaceholder = `{
  "POGODBENA_CENA": "price_eur",
  "PRODANA_POVRSINA": "size_m2",
  "LETO_IZGRADNJE": "year_built",
  "NADSTROPJE": "floor",
  "OBCINA": "municipality",
  "VRSTA": "property_type"
}`

  const datasets = computed(() => dataStore.datasets || [])
  const trainingLocked = computed(() => modelStore.training)
  const selectedPrepareRun = computed(() => workbench.selectedPrepareRun)
  const PREPARE_REQUEST_TIMEOUT_MS = 10 * 60 * 1000
  const detectedPairsFromApi = ref<EtnDetectedPair[]>([])
  const datasetsLoadingForSelection = ref(false)
  const datasetsLoadedForSelection = ref(false)

  onMounted(async () => {
    await Promise.all([
      fetchDetectedPairs(),
      dataStore.fetchTrainingDataset(),
      modelStore.fetchActiveTraining(),
      workbench.fetchPrepareRuns(),
    ])
    await syncExistingPrepareJob()
  })

  watch(
    () => workbench.prepareRuns,
    (runs) => {
      if (!runs.length || selectedPrepareRunId.value) return
      selectedPrepareRunId.value = runs[0].id
      void loadPrepareRunDetail(runs[0].id)
    },
    { immediate: true },
  )

  onUnmounted(() => {
    stopPreparePolling()
  })

  watch(etnMode, (mode) => {
    if (mode !== 'bulk') {
      void ensureSelectionDatasetsLoaded()
    }
  })

  // --- Dataset role & year helpers (mirrors v1 logic) ---

  function parseEtnKppDataset(item) {
    const candidates = [item.original_name || '', item.relative_path || '']

    for (const candidate of candidates) {
      const text = String(candidate).toUpperCase()
      const yearMatch = text.match(/ETN(?:_SLO)?_(20\d{2})_KPP(?:_|\.|$)/)
      if (!yearMatch) continue

      if (/_KPP_POSLI(?:_|\.|$)/.test(text)) {
        return { role: 'posli', year: Number(yearMatch[1]) }
      }

      if (/_KPP_DELISTAVB(?:_|\.|$)/.test(text)) {
        return { role: 'delistavb', year: Number(yearMatch[1]) }
      }

      if (/_KPP_ZEMLJISCA(?:_|\.|$)/.test(text) || /_KPP_ZEMLJISC(?:_|\.|$)/.test(text)) {
        return { role: 'zemljisca', year: Number(yearMatch[1]) }
      }

      // Only a real ETN KPP archive can stand in for all roles.
      if (/ETN(?:_SLO)?_(20\d{2})_KPP\.ZIP$/.test(text)) {
        return { role: 'bundle', year: Number(yearMatch[1]) }
      }

      return { role: 'other', year: null }
    }

    return { role: 'other', year: null }
  }

  // Track which years are selected (all selected by default)
  const deselectedYears = reactive(new Set())

  // Selection model for DataTable v-model
  const selectedPairsModel = computed({
    get() {
      return detectedPairs.value.filter((p) => !deselectedYears.has(p.year))
    },
    set(val) {
      const selectedYears = new Set(val.map((p) => p.year))
      deselectedYears.clear()
      for (const p of detectedPairs.value) {
        if (!selectedYears.has(p.year)) {
          deselectedYears.add(p.year)
        }
      }
    },
  })

  // Reactive computed: auto-detects ETN pairs grouped by year
  const detectedPairs = computed(() => {
    if (detectedPairsFromApi.value.length) {
      return detectedPairsFromApi.value
    }

    const byYear = new Map()
    const items = datasets.value || []
    for (const item of items) {
      const { role, year } = parseEtnKppDataset(item)
      if (!year) continue
      if (!byYear.has(year))
        byYear.set(year, { year, posli: null, delistavb: null, zemljisca: null })
      const row = byYear.get(year)
      if (role === 'bundle') {
        // ETN bundle ZIP: fills all roles (backend extracts CSVs from ZIP on demand)
        if (!row.posli || Number(item.id || 0) > Number(row.posli.id || 0)) row.posli = item
        if (!row.delistavb || Number(item.id || 0) > Number(row.delistavb.id || 0))
          row.delistavb = item
        if (!row.zemljisca || Number(item.id || 0) > Number(row.zemljisca.id || 0))
          row.zemljisca = item
      } else if (
        role === 'posli' &&
        (!row.posli || Number(item.id || 0) > Number(row.posli.id || 0))
      ) {
        row.posli = item
      } else if (
        role === 'delistavb' &&
        (!row.delistavb || Number(item.id || 0) > Number(row.delistavb.id || 0))
      ) {
        row.delistavb = item
      } else if (
        role === 'zemljisca' &&
        (!row.zemljisca || Number(item.id || 0) > Number(row.zemljisca.id || 0))
      ) {
        row.zemljisca = item
      }
    }
    return Array.from(byYear.values())
      .filter((r) => r.posli && r.delistavb)
      .sort((a, b) => a.year - b.year)
  })

  async function fetchDetectedPairs() {
    try {
      const { data } = await api.get('/api/data/prepare-etn-kpp-pairs')
      const pairs = Array.isArray(data?.pairs) ? data.pairs : []
      detectedPairsFromApi.value = pairs
    } catch {
      // Fallback for older backends that do not expose the optimized pairs endpoint.
      await dataStore.fetchDatasets(false, true, { perPage: 200 })
    }
  }

  async function ensureSelectionDatasetsLoaded() {
    if (datasetsLoadedForSelection.value || datasetsLoadingForSelection.value) return

    datasetsLoadingForSelection.value = true
    try {
      await dataStore.fetchDatasets(false, true, { perPage: 200 })
      datasetsLoadedForSelection.value = true
    } finally {
      datasetsLoadingForSelection.value = false
    }
  }

  function pairStatus(pair) {
    if (pair.posli && pair.delistavb) return 'complete'
    if (pair.posli || pair.delistavb || pair.zemljisca) return 'ready'
    return 'incomplete'
  }

  function pairStatusLabel(pair) {
    const status = pairStatus(pair)
    if (status === 'complete') return t('prepare.status_complete')
    if (status === 'ready') return t('prepare.status_ready')
    return t('prepare.status_incomplete')
  }

  function isSelected(year) {
    return !deselectedYears.has(year)
  }

  function selectedPairs() {
    return detectedPairs.value.filter((p) => isSelected(p.year))
  }

  function getPrepareErrorMessage(apiError) {
    const detail = apiError?.response?.data?.detail

    if (typeof detail === 'string' && detail.startsWith('Cannot read CSV:')) {
      const file = detail.split('/').pop() || detail
      return t('prepare.cannotReadCsv', { file })
    }

    if (detail === 'No valid ETN pairs produced training data.') {
      return t('prepare.noValidPairs')
    }

    if (detail === 'No valid rows after filtering ETN data.') {
      return t('prepare.noRowsAfterFiltering')
    }

    return getApiErrorMessage(apiError, t)
  }

  function postPrepare(url, payload) {
    return api.post(url, payload, { timeout: PREPARE_REQUEST_TIMEOUT_MS })
  }

  function buildEnrichmentOptionsPayload() {
    return {
      enable_rn: enrichmentOptions.enable_rn,
      enable_ev: enrichmentOptions.enable_ev,
      enable_kn: enrichmentOptions.enable_kn,
      enable_gji: enrichmentOptions.enable_gji,
      enable_dtm: enrichmentOptions.enable_dtm,
      enable_emv: enrichmentOptions.enable_emv,
      variant_label: enrichmentOptions.variant_label.trim() || undefined,
    }
  }

  function isTerminalPrepareStatus(status) {
    return status === 'completed' || status === 'failed'
  }

  async function loadPrepareRunDetail(jobId: string) {
    selectedPrepareRunId.value = jobId
    await workbench.fetchPrepareRunDetail(jobId)
  }

  function stopPreparePolling() {
    if (preparePollTimer.value) {
      clearInterval(preparePollTimer.value)
      preparePollTimer.value = null
    }
  }

  async function handlePrepareStatus(data: PrepareJobStatus | null) {
    prepareStatus.value = data
    loading.value = !!data && !isTerminalPrepareStatus(data.status)

    if (!data) return

    if (data.status === 'completed') {
      result.value = data.result || null
      if (!result.value?.training_dataset) {
        await dataStore.fetchTrainingDataset()
      }
      stopPreparePolling()
      loading.value = false
      error.value = ''
      return
    }

    if (data.status === 'failed') {
      stopPreparePolling()
      loading.value = false
      error.value = data.error || t('prepare.jobFailed')
    }
  }

  async function pollPrepareStatus(jobId) {
    try {
      const { data } = await api.get(`/api/data/prepare-etn-kpp-bulk/status/${jobId}`)
      await handlePrepareStatus(data)
      return data
    } catch (e) {
      loading.value = false
      stopPreparePolling()
      error.value = getPrepareErrorMessage(e)
      return null
    }
  }

  function startPreparePolling(jobId) {
    stopPreparePolling()
    preparePollTimer.value = setInterval(() => {
      void pollPrepareStatus(jobId)
    }, 1800)
  }

  async function syncExistingPrepareJob() {
    try {
      const { data } = await api.get('/api/data/prepare-etn-kpp-bulk/active')
      await handlePrepareStatus(data)
      if (data?.job_id && !isTerminalPrepareStatus(data.status)) {
        startPreparePolling(data.job_id)
      }
    } catch {
      prepareStatus.value = null
    }
  }

  async function startBulkPrepareJob(pairs) {
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const { data } = await api.post('/api/data/prepare-etn-kpp-bulk/start', {
        pairs,
        enrichment_options: buildEnrichmentOptionsPayload(),
      })
      await handlePrepareStatus(data)
      startPreparePolling(data.job_id)
    } catch (e) {
      const activeJob = e?.response?.status === 409 ? e?.response?.data?.detail : null
      if (activeJob?.job_id) {
        error.value = t('prepare.jobAlreadyRunning')
        await handlePrepareStatus(activeJob)
        startPreparePolling(activeJob.job_id)
        return
      }

      loading.value = false
      error.value = getPrepareErrorMessage(e)
    }
  }

  async function prepareEtnBulk() {
    const selected = selectedPairs()
    if (!selected.length) {
      error.value = t('prepare.noPairs')
      return
    }

    const pairs = selected.map((p) => ({
      posli_csv_path: p.posli.relative_path,
      delistavb_csv_path: p.delistavb.relative_path,
      ...(p.zemljisca ? { zemljisca_csv_path: p.zemljisca.relative_path } : {}),
      year: String(p.year),
      label: String(p.year),
    }))

    await startBulkPrepareJob(pairs)
  }

  async function prepareEtnSingle() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const { data } = await postPrepare('/api/data/prepare-etn-kpp', {
        posli_csv_path: singlePosli.value,
        delistavb_csv_path: singleDelistavb.value,
        enrichment_options: buildEnrichmentOptionsPayload(),
      })
      result.value = data
      await dataStore.fetchTrainingDataset()
    } catch (e) {
      error.value = getPrepareErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function prepareManual() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const map = JSON.parse(columnMap.value)
      const { data } = await postPrepare('/api/data/prepare-train', {
        source_csv_path: manualCsvPath.value,
        column_map: map,
      })
      result.value = data
      await dataStore.fetchTrainingDataset()
    } catch (e) {
      if (e instanceof SyntaxError) {
        error.value = t('prepare.invalidJson')
      } else {
        error.value = getPrepareErrorMessage(e)
      }
    } finally {
      loading.value = false
    }
  }

  function selectAll() {
    deselectedYears.clear()
  }

  function deselectAll() {
    for (const p of detectedPairs.value) {
      deselectedYears.add(p.year)
    }
  }

  const allSelected = computed(() => detectedPairs.value.every((p) => !deselectedYears.has(p.year)))

  // Computed data for training_dataset DataTable
  const trainingDatasetRows = computed(() => {
    if (!result.value?.training_dataset) return []
    const td = result.value.training_dataset
    const row = {
      path: td.relative_path || td.path || '-',
      rows: td.rows || 0,
      columns: td.columns?.length || td.num_columns || 0,
      years: result.value.per_year ? Object.keys(result.value.per_year).sort().join(', ') : '-',
    }
    return [row]
  })

  function getDatasetPaths() {
    return datasets.value.map((d) => ({
      label: d.original_name,
      value: d.relative_path,
    }))
  }

  function getReportDetail(report) {
    return (
      report.reason ||
      report.used_size_column ||
      report.used_property_type_column ||
      t('common.noData')
    )
  }

  function openModelView() {
    router.push('/admin/model')
  }

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  // Computed data for per_year DataTable
  const perYearRows = computed(() => {
    if (!result.value?.per_year) return []
    return Object.entries(result.value.per_year).map(([year, rows]) => ({
      year,
      rows,
    }))
  })

  const enrichmentRows = computed(() =>
    buildGursEnrichmentRows(result.value?.reports, result.value?.enrichment_summary),
  )

  const selectedVariantLabel = computed(
    () =>
      result.value?.enrichment_options?.variant_label ||
      enrichmentOptions.variant_label.trim() ||
      t('prepare.defaultVariantLabel'),
  )

  const enrichmentTotals = computed(() => summarizeGursEnrichment(enrichmentRows.value))

  function enrichmentRunLabel(label) {
    return label === 'single' ? t('prepare.currentRun') : String(label)
  }

  function enrichmentSeverity(available, matched) {
    if (matched) return 'success'
    if (available) return 'warn'
    return 'contrast'
  }

  function enrichmentSourcesLabel(row) {
    if (row.matchedSources.length) return row.matchedSources.join(', ')
    if (row.sources.length) {
      return t('prepare.detectedOnlySources', { sources: row.sources.join(', ') })
    }
    return t('common.noData')
  }

  // ── Progress pipeline helpers ─────────────────────────────────────────────

  const PAIR_STAGES = new Set([
    'loading_pair',
    'building_rows',
    'enriching_buildings',
    'enriching_land',
    'finalizing_pair',
  ])
  const STAGE_RANK: Record<string, number> = {
    queued: 0,
    initializing: 1,
    loading_sources: 1,
    loading_pair: 2,
    building_rows: 2,
    enriching_buildings: 2,
    enriching_land: 2,
    finalizing_pair: 2,
    merging_outputs: 3,
    spatial_enrichment_merged: 4,
    completed: 5,
    error: 6,
  }
  const SPATIAL_PHASE_RANK: Record<string, number> = { kn: 1, gji: 2, dtm: 3, emv: 4 }

  type StepState = 'pending' | 'active' | 'done' | 'error'

  function pipelineStepState(rank: number): StepState {
    const s = prepareStatus.value
    if (!s) return 'pending'
    if (s.status === 'failed') return rank <= (STAGE_RANK[s.stage ?? ''] ?? 0) ? 'error' : 'pending'
    const cur = STAGE_RANK[s.stage ?? ''] ?? 0
    if (rank < cur) return 'done'
    if (rank === cur) return s.status === 'completed' ? 'done' : 'active'
    return 'pending'
  }

  function spatialSubStepState(phase: string): StepState {
    const s = prepareStatus.value
    if (!s) return 'pending'
    if (s.stage !== 'spatial_enrichment_merged' && s.status !== 'completed') {
      return (STAGE_RANK[s.stage ?? ''] ?? 0 > 4) ? 'done' : 'pending'
    }
    if (s.status === 'completed') return 'done'
    const curRank = SPATIAL_PHASE_RANK[s.spatial_phase ?? ''] ?? 0
    const phaseRank = SPATIAL_PHASE_RANK[phase] ?? 0
    // spatial_phase not yet set — treat kn (rank 1) as active
    if (curRank === 0) return phaseRank === 1 ? 'active' : 'pending'
    if (phaseRank < curRank) return 'done'
    if (phaseRank === curRank) return 'active'
    return 'pending'
  }

  // Track max progress seen so parallel pairs never cause the bar to jump backwards.
  const maxProgressSeen = ref(0)

  watch(
    [loading, () => prepareStatus.value?.progress ?? 0],
    ([isLoading, raw]) => {
      if (!isLoading) {
        maxProgressSeen.value = 0
        return
      }
      if (raw > maxProgressSeen.value) {
        maxProgressSeen.value = raw
      }
    },
    { immediate: true },
  )

  const prepareProgress = computed(() =>
    loading.value ? maxProgressSeen.value : (prepareStatus.value?.progress ?? 0),
  )

  const prepareProgressVisible = computed(
    () => !!prepareStatus.value && (loading.value || prepareStatus.value?.status === 'failed'),
  )

  const prepareStatusSeverity = computed(() => {
    const status = prepareStatus.value?.status
    if (status === 'completed') return 'success'
    if (status === 'failed') return 'danger'
    if (status === 'queued') return 'warn'
    return 'info'
  })

  const prepareStatusLabel = computed(() => {
    const status = prepareStatus.value?.status
    if (status === 'queued') return t('prepare.jobQueued')
    if (status === 'failed') return t('prepare.jobFailedShort')
    if (status === 'completed') return t('prepare.jobCompleted')
    return t('prepare.jobRunning')
  })

  const prepareStageLabel = computed(() => {
    const status = prepareStatus.value
    if (!status) return ''
    const label = status.current_label ? String(status.current_label) : t('prepare.unknownYear')

    switch (status.stage) {
      case 'queued':
        return t('prepare.stageQueued')
      case 'initializing':
        return t('prepare.stageInitializing')
      case 'loading_sources':
        return t('prepare.stageLoadingSources')
      case 'loading_pair':
        return t('prepare.stageLoadingPair', { label })
      case 'building_rows':
        return t('prepare.stageBuildingRows', { label })
      case 'enriching_buildings':
        return t('prepare.stageEnrichingBuildings', { label })
      case 'enriching_land':
        return t('prepare.stageEnrichingLand', { label })
      case 'finalizing_pair':
        return t('prepare.stageFinalizingPair', { label })
      case 'merging_outputs':
        return t('prepare.stageMergingOutputs')
      case 'spatial_enrichment_merged':
        return t('prepare.stageSpatialEnrichmentMerged', { rows: status?.rows ?? '…' })
      case 'completed':
        return t('prepare.stageCompleted')
      case 'error':
        return t('prepare.stageError')
      default:
        return t('prepare.stageInitializing')
    }
  })

  const prepareSummaryCards = computed(() => [
    {
      label: t('prepare.autoEtn'),
      value: formatNumber(selectedPairs().length),
      meta: `${formatNumber(detectedPairs.value.length)} ${t('prepare.year')}`,
    },
    {
      label: t('prepare.enrichmentOptions'),
      value: formatNumber(
        Object.values(enrichmentOptions).filter((value) => typeof value === 'boolean' && value)
          .length,
      ),
      meta: t('prepare.enrichmentOptionsDesc'),
    },
    {
      label: t('model.training'),
      value: trainingLocked.value ? t('model.training') : t('model.trainButton'),
      meta: trainingLocked.value ? t('prepare.trainingLockedHint') : t('prepare.readyForModel'),
      tone: (trainingLocked.value ? 'warning' : 'success') as 'success' | 'warning',
    },
    {
      label: t('data.rows'),
      value: formatNumber(
        prepareStatus.value?.rows || result.value?.rows || result.value?.total_rows || 0,
      ),
      meta: prepareStageLabel.value || t('common.noData'),
    },
  ])
</script>

<template>
  <div class="prepare-page">
    <AdminWorkspaceHero
      :eyebrow="t('nav.prepare')"
      :title="t('prepare.title')"
      :description="trainingLocked ? t('prepare.trainingLockedHint') : t('layout.page.prepare')"
      :metrics="prepareSummaryCards"
      :links="adminWorkspaceLinks"
      :status="prepareStatus ? prepareStatusLabel : ''"
      :status-severity="prepareStatusSeverity"
    />

    <AdminRunDetailPanel
      :eyebrow="t('nav.prepare')"
      :title="t('workbench.recentPrepareRuns')"
      :description="t('workbench.prepareRunDetailHint')"
      :runs="workbench.prepareRuns.slice(0, 8)"
      :selected-run="selectedPrepareRun"
      @select="loadPrepareRunDetail"
    />

    <!-- Mode tabs -->
    <div class="card prepare-workbench">
      <Tabs v-model:value="etnMode">
        <TabList>
          <Tab value="bulk">{{ t('prepare.autoEtn') }}</Tab>
          <Tab value="single">{{ t('prepare.singleEtn') }}</Tab>
          <Tab value="manual">{{ t('prepare.manualMapping') }}</Tab>
        </TabList>

        <TabPanels>
          <!-- Bulk ETN -->
          <TabPanel value="bulk">
            <div class="card inner-card">
              <PageHeader
                compact
                :eyebrow="t('prepare.autoEtn')"
                :title="t('prepare.autoEtn')"
                :description="t('prepare.autoEtnDesc')"
              />

              <div v-if="!detectedPairs.length" class="muted">
                {{ t('prepare.noPairsDetected') }}
              </div>

              <div v-else>
                <div class="enrichment-config-card mb-4">
                  <div class="enrichment-config-head">
                    <h3>{{ t('prepare.enrichmentOptions') }}</h3>
                    <p class="muted">{{ t('prepare.enrichmentOptionsDesc') }}</p>
                  </div>

                  <div class="enrichment-cards">
                    <label
                      v-for="opt in ENRICHMENT_OPTIONS"
                      :key="opt.key"
                      class="enrichment-card"
                      :class="{ 'enrichment-card--active': enrichmentOptions[opt.key] }"
                    >
                      <div class="enrichment-card-header">
                        <div class="enrichment-card-title">
                          <i :class="`pi ${opt.icon}`" />
                          <span>{{ t(opt.titleKey) }}</span>
                        </div>
                        <ToggleSwitch v-model="enrichmentOptions[opt.key]" />
                      </div>
                      <p class="enrichment-card-desc">{{ t(opt.descKey) }}</p>
                      <div class="enrichment-card-files">
                        <span class="files-label">{{ t('prepare.enrichmentFilesLabel') }}:</span>
                        <code>{{ t(opt.filesKey) }}</code>
                      </div>
                    </label>
                  </div>

                  <div class="variant-field mt-3">
                    <label class="form-label">{{ t('prepare.variantLabel') }}</label>
                    <InputText
                      v-model="enrichmentOptions.variant_label"
                      :placeholder="t('prepare.variantLabelPlaceholder')"
                    />
                  </div>
                </div>

                <div class="selection-toolbar">
                  <Button
                    size="small"
                    severity="secondary"
                    text
                    :icon="allSelected ? 'pi pi-check-square' : 'pi pi-stop'"
                    :label="allSelected ? t('prepare.deselectAll') : t('prepare.selectAll')"
                    @click="allSelected ? deselectAll() : selectAll()"
                  />
                </div>

                <DataTable
                  v-model:selection="selectedPairsModel"
                  :value="detectedPairs"
                  data-key="year"
                  striped-rows
                  size="small"
                >
                  <Column selection-mode="multiple" header-style="width: 3rem" />
                  <Column :header="t('prepare.year')">
                    <template #body="{ data: pair }">
                      <Tag :value="String(pair.year)" severity="info" />
                    </template>
                  </Column>
                  <Column :header="t('prepare.posliFile')">
                    <template #body="{ data: pair }">
                      {{ pair.posli.original_name }}
                    </template>
                  </Column>
                  <Column :header="t('prepare.delistavbFile')">
                    <template #body="{ data: pair }">
                      {{ pair.delistavb.original_name }}
                    </template>
                  </Column>
                  <Column :header="t('prepare.pairStatus')">
                    <template #body="{ data: pair }">
                      <Tag
                        :value="pairStatusLabel(pair)"
                        :severity="
                          pairStatus(pair) === 'complete'
                            ? 'success'
                            : pairStatus(pair) === 'ready'
                              ? 'info'
                              : 'warn'
                        "
                      />
                    </template>
                  </Column>
                </DataTable>

                <Button
                  class="mt-4"
                  icon="pi pi-cog"
                  :loading="loading"
                  :disabled="loading || trainingLocked || !selectedPairs().length"
                  :label="loading ? t('common.loading') : t('prepare.prepareButton')"
                  @click="prepareEtnBulk"
                />
              </div>
            </div>
          </TabPanel>

          <!-- Single ETN -->
          <TabPanel value="single">
            <div class="card inner-card">
              <PageHeader
                compact
                :eyebrow="t('prepare.singleEtn')"
                :title="t('prepare.singleEtn')"
                :description="t('prepare.singleEtnDesc')"
              />

              <div class="form-grid">
                <div>
                  <label class="form-label">{{ t('prepare.posliFile') }}</label>
                  <Select
                    v-model="singlePosli"
                    :options="[{ label: t('prepare.selectFile'), value: '' }, ...getDatasetPaths()]"
                    option-label="label"
                    option-value="value"
                    :loading="datasetsLoadingForSelection"
                  />
                </div>
                <div>
                  <label class="form-label">{{ t('prepare.delistavbFile') }}</label>
                  <Select
                    v-model="singleDelistavb"
                    :options="[{ label: t('prepare.selectFile'), value: '' }, ...getDatasetPaths()]"
                    option-label="label"
                    option-value="value"
                    :loading="datasetsLoadingForSelection"
                  />
                </div>
              </div>

              <div class="enrichment-config-card mt-4">
                <div class="enrichment-config-head">
                  <h3>{{ t('prepare.enrichmentOptions') }}</h3>
                  <p class="muted">{{ t('prepare.enrichmentOptionsDesc') }}</p>
                </div>

                <div class="enrichment-cards">
                  <label
                    v-for="opt in ENRICHMENT_OPTIONS"
                    :key="opt.key"
                    class="enrichment-card"
                    :class="{ 'enrichment-card--active': enrichmentOptions[opt.key] }"
                  >
                    <div class="enrichment-card-header">
                      <div class="enrichment-card-title">
                        <i :class="`pi ${opt.icon}`" />
                        <span>{{ t(opt.titleKey) }}</span>
                      </div>
                      <ToggleSwitch v-model="enrichmentOptions[opt.key]" />
                    </div>
                    <p class="enrichment-card-desc">{{ t(opt.descKey) }}</p>
                    <div class="enrichment-card-files">
                      <span class="files-label">{{ t('prepare.enrichmentFilesLabel') }}:</span>
                      <code>{{ t(opt.filesKey) }}</code>
                    </div>
                  </label>
                </div>

                <div class="variant-field mt-3">
                  <label class="form-label">{{ t('prepare.variantLabel') }}</label>
                  <InputText
                    v-model="enrichmentOptions.variant_label"
                    :placeholder="t('prepare.variantLabelPlaceholder')"
                  />
                </div>
              </div>

              <Button
                class="mt-4"
                icon="pi pi-cog"
                :loading="loading"
                :disabled="loading || trainingLocked || !singlePosli || !singleDelistavb"
                :label="loading ? t('common.loading') : t('prepare.prepareButton')"
                @click="prepareEtnSingle"
              />
            </div>
          </TabPanel>

          <!-- Manual mapping -->
          <TabPanel value="manual">
            <div class="card inner-card">
              <PageHeader
                compact
                :eyebrow="t('prepare.manualMapping')"
                :title="t('prepare.manualMapping')"
                :description="t('prepare.manualDesc')"
              />

              <div class="mb-4">
                <label class="form-label">{{ t('prepare.sourceFile') }}</label>
                <Select
                  v-model="manualCsvPath"
                  :options="[{ label: t('prepare.selectFile'), value: '' }, ...getDatasetPaths()]"
                  option-label="label"
                  option-value="value"
                  :loading="datasetsLoadingForSelection"
                />
              </div>

              <div>
                <label class="form-label">{{ t('prepare.columnMapping') }}</label>
                <Textarea
                  v-model="columnMap"
                  class="code-textarea"
                  rows="8"
                  :placeholder="columnMapPlaceholder"
                  auto-resize
                />
              </div>

              <Button
                class="mt-4"
                icon="pi pi-cog"
                :loading="loading"
                :disabled="loading || trainingLocked || !manualCsvPath || !columnMap"
                :label="loading ? t('common.loading') : t('prepare.prepareButton')"
                @click="prepareManual"
              />
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>

    <!-- Error -->
    <p v-if="error" class="error-text mt-4">{{ error }}</p>

    <div v-if="prepareProgressVisible" class="card progress-card">
      <PageHeader
        compact
        :eyebrow="t('prepare.prepareProgress')"
        :title="prepareStageLabel"
        :description="t('prepare.jobProgressDesc')"
      >
        <template #actions>
          <Tag :severity="prepareStatusSeverity" :value="prepareStatusLabel" />
        </template>
      </PageHeader>

      <div class="progress-header-row">
        <span class="progress-pct">{{ prepareProgress }}%</span>
        <span class="progress-stage-label">{{ prepareStageLabel }}</span>
      </div>
      <ProgressBar :value="prepareProgress" :show-value="false" class="mb-4" />

      <!-- Step pipeline -->
      <div class="prepare-pipeline">
        <!-- Init -->
        <div class="pipeline-step" :class="`pipeline-step--${pipelineStepState(1)}`">
          <span class="step-dot" />
          <div class="step-body">
            <span class="step-name">{{ t('prepare.stepInit') }}</span>
          </div>
        </div>

        <!-- Pairs -->
        <div class="pipeline-step" :class="`pipeline-step--${pipelineStepState(2)}`">
          <span class="step-dot" />
          <div class="step-body">
            <span class="step-name">{{ t('prepare.stepPairs') }}</span>
            <span v-if="prepareStatus?.total_pairs" class="step-meta">
              {{
                t('prepare.stepPairsProgress', {
                  done: prepareStatus.pairs_completed ?? 0,
                  total: prepareStatus.total_pairs,
                })
              }}
            </span>
            <span
              v-if="PAIR_STAGES.has(prepareStatus?.stage ?? '') && prepareStatus?.current_label"
              class="step-detail"
            >
              {{ t('prepare.stepPairsCurrent', { label: prepareStatus.current_label }) }}
              — {{ prepareStageLabel }}
            </span>
          </div>
        </div>

        <!-- Merge -->
        <div class="pipeline-step" :class="`pipeline-step--${pipelineStepState(3)}`">
          <span class="step-dot" />
          <div class="step-body">
            <span class="step-name">{{ t('prepare.stepMerge') }}</span>
          </div>
        </div>

        <!-- Spatial enrichment -->
        <div class="pipeline-step" :class="`pipeline-step--${pipelineStepState(4)}`">
          <span class="step-dot" />
          <div class="step-body">
            <span class="step-name">{{ t('prepare.stepSpatial') }}</span>
            <span v-if="prepareStatus?.rows && pipelineStepState(4) === 'active'" class="step-meta">
              {{ fmt(prepareStatus.rows) }} vrstic
            </span>
            <!-- Spatial sub-steps — only show phases that were enabled for this job -->
            <div v-if="pipelineStepState(4) !== 'pending'" class="spatial-substeps">
              <div
                v-for="phase in [
                  {
                    key: 'kn',
                    label: t('prepare.stepSpatialKn'),
                    show: enrichmentOptions.enable_kn,
                  },
                  {
                    key: 'gji',
                    label: t('prepare.stepSpatialGji'),
                    show: enrichmentOptions.enable_gji,
                  },
                  {
                    key: 'dtm',
                    label: t('prepare.stepSpatialDtm'),
                    show: enrichmentOptions.enable_dtm,
                  },
                  {
                    key: 'emv',
                    label: t('prepare.stepSpatialEmv'),
                    show: enrichmentOptions.enable_emv,
                  },
                ].filter((p) => p.show)"
                :key="phase.key"
                class="spatial-sub"
                :class="`spatial-sub--${spatialSubStepState(phase.key)}`"
              >
                <span class="sub-dot" />
                <span class="sub-name">{{ phase.label }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Done -->
        <div class="pipeline-step" :class="`pipeline-step--${pipelineStepState(5)}`">
          <span class="step-dot" />
          <div class="step-body">
            <span class="step-name">{{ t('prepare.stepDone') }}</span>
          </div>
        </div>
      </div>

      <p v-if="prepareStatus?.error" class="error-text mt-3">{{ prepareStatus.error }}</p>
    </div>

    <!-- Result -->
    <div v-if="result" class="card result-card mt-6">
      <PageHeader compact :eyebrow="t('prepare.result')" :title="t('prepare.readyForModel')" />

      <div class="result-metrics">
        <MetricCard
          :label="t('prepare.outputRows')"
          :value="fmt(result.rows || result.total_rows || 0)"
          tone="success"
        />
        <MetricCard
          v-if="result.columns"
          :label="t('prepare.outputColumns')"
          :value="fmt(result.columns?.length || 0)"
        />
        <MetricCard
          v-if="result.per_year"
          :label="t('prepare.yearsCovered')"
          :value="fmt(Object.keys(result.per_year).length)"
        />
        <MetricCard :label="t('prepare.variantLabel')" :value="selectedVariantLabel" />
      </div>

      <div v-if="result.per_year" class="mt-4">
        <DataTable :value="perYearRows" striped-rows size="small">
          <Column :header="t('prepare.year')">
            <template #body="{ data: row }">
              <Tag :value="String(row.year)" severity="info" />
            </template>
          </Column>
          <Column :header="t('data.rows')">
            <template #body="{ data: row }">
              {{ fmt(row.rows) }}
            </template>
          </Column>
        </DataTable>
      </div>

      <div v-if="result.reports?.length" class="mt-4">
        <DataTable :value="result.reports" striped-rows size="small">
          <Column :header="t('prepare.year')">
            <template #body="{ data: report }">
              <Tag :value="String(report.label)" severity="info" />
            </template>
          </Column>
          <Column :header="t('prepare.reportStatus')">
            <template #body="{ data: report }">
              <Tag
                :value="report.status"
                :severity="report.status === 'ok' ? 'success' : 'danger'"
              />
            </template>
          </Column>
          <Column :header="t('data.rows')">
            <template #body="{ data: report }">
              {{ fmt(report.rows || 0) }}
            </template>
          </Column>
          <Column :header="t('prepare.reportDetail')">
            <template #body="{ data: report }">
              <span class="muted">{{ getReportDetail(report) }}</span>
            </template>
          </Column>
        </DataTable>
      </div>

      <div v-if="enrichmentRows.length" class="card inner-card mt-4">
        <PageHeader
          compact
          :eyebrow="t('prepare.result')"
          :title="t('prepare.gursEnrichment')"
          :description="t('prepare.gursEnrichmentDesc')"
        />

        <div class="result-metrics">
          <MetricCard
            :label="t('prepare.exactAddressMatches')"
            :value="fmt(enrichmentTotals.rnExactAddress)"
          />
          <MetricCard
            :label="t('prepare.regionIdsRecovered')"
            :value="fmt(enrichmentTotals.rnRegionId)"
          />
          <MetricCard
            :label="t('prepare.evBuildingMatches')"
            :value="fmt(enrichmentTotals.evBuildingMatch)"
          />
          <MetricCard
            :label="t('prepare.evParcelMatches')"
            :value="fmt(enrichmentTotals.evParcelMatch)"
          />
          <MetricCard
            :label="t('prepare.knPolygonMatches')"
            :value="fmt(enrichmentTotals.knPolygonMatch)"
          />
          <MetricCard
            :label="t('prepare.gjiVodovodMatches')"
            :value="fmt(enrichmentTotals.gjiVodovodNearby)"
          />
          <MetricCard
            :label="t('prepare.gjiKanalizacijaMatches')"
            :value="fmt(enrichmentTotals.gjiKanalizacijaNearby)"
          />
          <MetricCard
            :label="t('prepare.emvZoneMatches')"
            :value="fmt(enrichmentTotals.emvZoneMatch)"
          />
        </div>

        <DataTable :value="enrichmentRows" striped-rows size="small">
          <Column :header="t('prepare.year')">
            <template #body="{ data: row }">
              <Tag :value="enrichmentRunLabel(row.label)" severity="info" />
            </template>
          </Column>
          <Column :header="t('prepare.sourceCoverage')">
            <template #body="{ data: row }">
              <div class="coverage-tags">
                <Tag
                  :value="t('prepare.rnRegister')"
                  :severity="
                    enrichmentSeverity(
                      row.rnAvailable,
                      row.rnExactAddress > 0 || row.rnRegionId > 0,
                    )
                  "
                />
                <Tag
                  :value="t('prepare.evBuildings')"
                  :severity="enrichmentSeverity(row.evBuildingAvailable, row.evBuildingMatch > 0)"
                />
                <Tag
                  :value="t('prepare.evParcels')"
                  :severity="enrichmentSeverity(row.evParcelAvailable, row.evParcelMatch > 0)"
                />
                <Tag
                  :value="t('prepare.knPolygons')"
                  :severity="enrichmentSeverity(row.knAvailable, row.knPolygonMatch > 0)"
                />
                <Tag
                  :value="t('prepare.gjiInfrastructure')"
                  :severity="
                    enrichmentSeverity(
                      row.gjiAvailable,
                      row.gjiVodovodNearby > 0 || row.gjiKanalizacijaNearby > 0,
                    )
                  "
                />
                <Tag
                  :value="t('prepare.emvZones')"
                  :severity="
                    enrichmentSeverity(
                      row.emvAvailable || row.emvSpatialEnabled,
                      row.emvZoneMatch > 0,
                    )
                  "
                />
              </div>
            </template>
          </Column>
          <Column field="rnExactAddress" :header="t('prepare.exactAddressMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.rnExactAddress) }}
            </template>
          </Column>
          <Column field="rnRegionId" :header="t('prepare.regionIdsRecovered')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.rnRegionId) }}
            </template>
          </Column>
          <Column field="evBuildingMatch" :header="t('prepare.evBuildingMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.evBuildingMatch) }}
            </template>
          </Column>
          <Column field="evParcelMatch" :header="t('prepare.evParcelMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.evParcelMatch) }}
            </template>
          </Column>
          <Column field="knPolygonMatch" :header="t('prepare.knPolygonMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.knPolygonMatch) }}
            </template>
          </Column>
          <Column field="gjiVodovodNearby" :header="t('prepare.gjiVodovodMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.gjiVodovodNearby) }}
            </template>
          </Column>
          <Column
            field="gjiKanalizacijaNearby"
            :header="t('prepare.gjiKanalizacijaMatches')"
            sortable
          >
            <template #body="{ data: row }">
              {{ fmt(row.gjiKanalizacijaNearby) }}
            </template>
          </Column>
          <Column field="emvZoneMatch" :header="t('prepare.emvZoneMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.emvZoneMatch) }}
            </template>
          </Column>
          <Column :header="t('prepare.enrichmentSources')">
            <template #body="{ data: row }">
              <span class="muted source-cell">{{ enrichmentSourcesLabel(row) }}</span>
            </template>
          </Column>
        </DataTable>
      </div>

      <div v-if="result.training_dataset" class="card inner-card mt-4 ready-card">
        <PageHeader compact :eyebrow="t('prepare.result')" :title="t('prepare.readyForModel')" />

        <DataTable :value="trainingDatasetRows" striped-rows size="small" class="mb-3">
          <Column :header="t('prepare.datasetPath')" field="path" />
          <Column :header="t('data.rows')">
            <template #body="{ data: row }">
              {{ fmt(row.rows) }}
            </template>
          </Column>
          <Column :header="t('data.columns')">
            <template #body="{ data: row }">
              {{ fmt(row.columns) }}
            </template>
          </Column>
          <Column :header="t('prepare.yearsCovered')">
            <template #body="{ data: row }">
              {{ row.years }}
            </template>
          </Column>
        </DataTable>

        <Button icon="pi pi-arrow-right" :label="t('prepare.openModel')" @click="openModelView" />
      </div>
    </div>
  </div>
</template>

<style scoped>
  .prepare-page {
    display: grid;
    gap: 1rem;
  }

  .prepare-hero,
  .prepare-workbench,
  .progress-card,
  .result-card {
    display: grid;
    gap: 1rem;
  }

  .inner-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm, 8px);
    padding: 1rem 1.25rem;
    display: grid;
    gap: 1rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .selection-toolbar,
  .coverage-tags,
  .result-metrics {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  /* ── Enrichment option cards ──────────────────────────────────────────── */

  .enrichment-config-card {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 1rem;
    background: color-mix(in srgb, var(--surface-muted) 78%, white);
  }

  .enrichment-config-head {
    display: grid;
    gap: 0.35rem;
  }

  .enrichment-config-head h3 {
    margin: 0;
    font-size: 1rem;
  }

  .enrichment-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 0.75rem;
  }

  .enrichment-card {
    display: grid;
    gap: 0.5rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--surface);
    cursor: pointer;
    transition:
      border-color 0.15s,
      background 0.15s;
  }

  .enrichment-card--active {
    border-color: color-mix(in srgb, var(--primary) 45%, var(--border));
    background: color-mix(in srgb, var(--primary) 5%, var(--surface));
  }

  .enrichment-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .enrichment-card-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    font-size: 0.875rem;
  }

  .enrichment-card-title .pi {
    font-size: 1rem;
    color: var(--primary);
    opacity: 0.8;
  }

  .enrichment-card--active .enrichment-card-title .pi {
    opacity: 1;
  }

  .enrichment-card-desc {
    margin: 0;
    font-size: 0.78rem;
    line-height: 1.45;
    color: var(--text-muted);
  }

  .enrichment-card-files {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
    font-size: 0.75rem;
  }

  .enrichment-card-files .files-label {
    color: var(--text-muted);
    white-space: nowrap;
  }

  .enrichment-card-files code {
    font-size: 0.73rem;
    color: var(--text-muted);
    background: var(--surface-muted);
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
    word-break: break-all;
  }

  .variant-field {
    max-width: 24rem;
  }

  .result-metrics {
    align-items: stretch;
  }

  .result-metrics :deep(.metric-card) {
    flex: 1 1 220px;
  }

  /* ── Prepare pipeline ─────────────────────────────────────────────────── */

  .prepare-pipeline {
    display: grid;
    gap: 0;
    padding: 0.25rem 0;
  }

  .pipeline-step {
    display: flex;
    gap: 0.85rem;
    padding: 0.6rem 0;
    position: relative;
  }

  .pipeline-step:not(:last-child)::before {
    content: '';
    position: absolute;
    left: 0.6rem;
    top: 1.55rem;
    bottom: -0.4rem;
    width: 2px;
    background: var(--border);
  }

  .pipeline-step--done:not(:last-child)::before {
    background: var(--success);
  }

  .pipeline-step--active:not(:last-child)::before {
    background: color-mix(in srgb, var(--primary) 40%, var(--border));
  }

  .step-dot {
    width: 1.2rem;
    height: 1.2rem;
    border-radius: 50%;
    border: 2px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
    margin-top: 0.1rem;
    position: relative;
    z-index: 1;
  }

  .pipeline-step--done .step-dot {
    background: var(--success);
    border-color: var(--success);
  }

  .pipeline-step--done .step-dot::after {
    content: '';
    position: absolute;
    inset: 3px;
    background: white;
    clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
  }

  .pipeline-step--active .step-dot {
    border-color: var(--primary);
    background: var(--primary);
    animation: pulse-dot 1.4s ease-in-out infinite;
  }

  .pipeline-step--error .step-dot {
    background: var(--danger);
    border-color: var(--danger);
  }

  @keyframes pulse-dot {
    0%,
    100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--primary) 40%, transparent);
    }
    50% {
      box-shadow: 0 0 0 5px transparent;
    }
  }

  .step-body {
    display: grid;
    gap: 0.15rem;
    padding-top: 0.05rem;
  }

  .step-name {
    font-weight: 600;
    font-size: 0.875rem;
  }

  .pipeline-step--pending .step-name {
    color: var(--text-muted);
  }

  .step-meta {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .step-detail {
    font-size: 0.8rem;
    color: var(--primary);
  }

  /* Spatial sub-steps */
  .spatial-substeps {
    display: grid;
    gap: 0.35rem;
    margin-top: 0.4rem;
    padding-left: 0.1rem;
  }

  .spatial-sub {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.8rem;
  }

  .sub-dot {
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 50%;
    border: 2px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }

  .spatial-sub--done .sub-dot {
    background: var(--success);
    border-color: var(--success);
  }

  .spatial-sub--active .sub-dot {
    background: var(--primary);
    border-color: var(--primary);
    animation: pulse-dot 1.4s ease-in-out infinite;
  }

  .spatial-sub--pending .sub-name {
    color: var(--text-muted);
  }

  .spatial-sub--active .sub-name {
    color: var(--primary);
    font-weight: 600;
  }

  .code-textarea {
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
    width: 100%;
  }

  .result-card {
    border-left: 4px solid var(--success);
  }

  .coverage-tags {
    align-items: center;
  }

  .source-cell {
    display: inline-block;
    max-width: 28rem;
    white-space: normal;
    word-break: break-word;
  }

  .ready-card {
    border-color: color-mix(in srgb, var(--success) 32%, var(--border));
  }

  .progress-card {
    border-left: 4px solid var(--info);
  }

  .progress-header-row {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 0.4rem;
  }

  .progress-pct {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
    color: var(--primary);
    min-width: 4.5rem;
  }

  .progress-stage-label {
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  @media (max-width: 720px) {
    .form-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
