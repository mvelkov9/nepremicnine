<script setup lang="ts">
  import { ref, onMounted, onUnmounted, computed, reactive, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Skeleton from 'primevue/skeleton'
  import AdminRunDetailPanel from '../components/admin/AdminRunDetailPanel.vue'
  import EmptyState from '../components/EmptyState.vue'
  import PageHeader from '../components/PageHeader.vue'
  import MetricCard from '../components/MetricCard.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import PrepareEnrichmentOptions from '../features/prepare/PrepareEnrichmentOptions.vue'
  import PrepareProgressPanel from '../features/prepare/PrepareProgressPanel.vue'
  import PrepareResultsWorkspace from '../features/prepare/PrepareResultsWorkspace.vue'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useWorkbenchStore } from '../stores/workbench'
  import api from '../composables/useApi'
  import { getApiErrorMessage } from '../utils/apiError'
  import { buildGursEnrichmentRows, summarizeGursEnrichment } from '../utils/enrichmentSummary'
  import { useFormat } from '../composables/useFormat'
  import { readQueryString, readQueryTab } from '../utils/routeQuery'
  import { formatNumber } from '../utils/format'
  import type {
    PrepareDetectedPair,
    PrepareEnrichmentOptionDefinition,
    PrepareEnrichmentState,
    PrepareEnrichmentTotals,
    PrepareJobStatus,
    PrepareMode,
    PreparePerYearRow,
    PrepareResultPayload,
    PrepareStepState,
    PrepareTimelineStep,
    PrepareTrainingDatasetRow,
  } from '../features/prepare/types'

  const { t } = useI18n()
  const { fmt } = useFormat()
  const dataStore = useDataStore()
  const modelStore = useModelStore()
  const workbench = useWorkbenchStore()
  const route = useRoute()
  const router = useRouter()

  const prepareWorkspaceTabs = ['configure', 'monitor', 'results'] as const

  const loading = ref(false)
  const bootstrapLoading = ref(true)
  const error = ref('')
  const result = ref<PrepareResultPayload | null>(null)
  const prepareStatus = ref<PrepareJobStatus | null>(null)
  const preparePollTimer = ref<ReturnType<typeof setTimeout> | null>(null)
  const preparePollInFlight = ref(false)
  const selectedPrepareRunId = ref(readQueryString(route.query.run) || '')
  let preparePollVersion = 0
  let activePrepareJobId = ''
  const enrichmentOptions = reactive<PrepareEnrichmentState>({
    enable_rn: true,
    enable_ev: true,
    enable_kn: true,
    enable_gji: true,
    enable_dtm: true,
    enable_emv: true,
    variant_label: '',
  })

  const ENRICHMENT_OPTIONS: PrepareEnrichmentOptionDefinition[] = [
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
  const etnMode = ref<PrepareMode>('bulk')
  const prepareWorkspaceTab = ref<(typeof prepareWorkspaceTabs)[number]>(
    readQueryTab(route.query.tab, prepareWorkspaceTabs, 'configure'),
  )
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
  const persistedEnrichmentOptions = computed<Partial<PrepareEnrichmentState>>(
    () =>
      (prepareStatus.value?.result?.enrichment_options as
        | Partial<PrepareEnrichmentState>
        | undefined) ||
      (selectedPrepareRun.value?.context?.enrichment_options as
        | Partial<PrepareEnrichmentState>
        | undefined) ||
      (result.value?.enrichment_options as Partial<PrepareEnrichmentState> | undefined) ||
      {},
  )
  const activeSpatialPhases = computed(() =>
    [
      {
        key: 'kn',
        label: t('prepare.stepSpatialKn'),
        show: persistedEnrichmentOptions.value.enable_kn ?? enrichmentOptions.enable_kn,
      },
      {
        key: 'gji',
        label: t('prepare.stepSpatialGji'),
        show: persistedEnrichmentOptions.value.enable_gji ?? enrichmentOptions.enable_gji,
      },
      {
        key: 'dtm',
        label: t('prepare.stepSpatialDtm'),
        show: persistedEnrichmentOptions.value.enable_dtm ?? enrichmentOptions.enable_dtm,
      },
      {
        key: 'emv',
        label: t('prepare.stepSpatialEmv'),
        show: persistedEnrichmentOptions.value.enable_emv ?? enrichmentOptions.enable_emv,
      },
    ].filter((phase) => Boolean(phase.show)),
  )
  const PREPARE_REQUEST_TIMEOUT_MS = 10 * 60 * 1000
  const detectedPairsFromApi = ref<PrepareDetectedPair[]>([])
  const detectedPairsLoading = ref(false)
  const detectedPairsLoaded = ref(false)
  const datasetsLoadingForSelection = ref(false)
  const datasetsLoadedForSelection = ref(false)
  const prepareRunsLoaded = ref(false)
  const prepareRunsLoading = ref(false)
  const trainingDatasetLoaded = ref(false)

  async function ensurePrepareRunsLoaded(force = false) {
    if (!force && (prepareRunsLoaded.value || prepareRunsLoading.value)) return

    prepareRunsLoading.value = true
    try {
      await workbench.fetchPrepareRuns(force)
      prepareRunsLoaded.value = true
    } catch {
      prepareRunsLoaded.value = false
    } finally {
      prepareRunsLoading.value = false
    }
  }

  async function ensureSelectedPrepareRunLoaded(force = false, jobId = selectedPrepareRunId.value) {
    if (!jobId) return
    await ensurePrepareRunsLoaded(force)
    if (
      workbench.prepareRuns.some((item) => item.id === jobId) &&
      selectedPrepareRun.value?.id !== jobId
    ) {
      await workbench.fetchPrepareRunDetail(jobId)
    }
  }

  async function ensureTrainingDatasetLoaded(force = false) {
    if (!force && trainingDatasetLoaded.value) return
    await dataStore.fetchTrainingDataset(force)
    trainingDatasetLoaded.value = true
  }

  function handlePrepareBackgroundError(cause: unknown) {
    if (!error.value) {
      error.value = getApiErrorMessage(cause, t)
    }
  }

  async function ensureDetectedPairsLoaded(force = false) {
    if (!force && (detectedPairsLoaded.value || detectedPairsLoading.value)) return

    detectedPairsLoading.value = true
    try {
      await fetchDetectedPairs()
      detectedPairsLoaded.value = true
    } finally {
      detectedPairsLoading.value = false
    }
  }

  async function loadActivePrepareTabData(force = false) {
    if (prepareWorkspaceTab.value === 'configure') {
      await ensureDetectedPairsLoaded(force)
    } else if (force || !detectedPairsLoaded.value) {
      void ensureDetectedPairsLoaded(force).catch(handlePrepareBackgroundError)
    }
  }

  async function initializePage() {
    error.value = ''
    bootstrapLoading.value = prepareWorkspaceTab.value === 'configure'
    try {
      void modelStore.fetchActiveTraining()
      await loadActivePrepareTabData()
      await syncExistingPrepareJob()
    } finally {
      bootstrapLoading.value = false
    }
  }

  onMounted(async () => {
    syncPrepareTabFromRoute(route.query)
    syncPrepareRunFromRoute(route.query)
    await initializePage()
  })

  watch(
    () => workbench.prepareRuns,
    (runs) => {
      if (!runs.length) return
      const hasRequestedRun = Boolean(readQueryString(route.query.run))

      const resolvedRunId = runs.some((item) => item.id === selectedPrepareRunId.value)
        ? selectedPrepareRunId.value
        : runs[0].id

      if (!resolvedRunId) return

      if (selectedPrepareRunId.value !== resolvedRunId) {
        selectedPrepareRunId.value = resolvedRunId
      }

      if (selectedPrepareRun.value?.id !== resolvedRunId) {
        if (hasRequestedRun) {
          void loadPrepareRunDetail(resolvedRunId)
        } else {
          void workbench.fetchPrepareRunDetail(resolvedRunId)
        }
      }
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

  watch(
    () => route.query.tab,
    () => {
      syncPrepareTabFromRoute(route.query)
    },
  )

  watch(
    () => route.query.run,
    () => {
      syncPrepareRunFromRoute(route.query)
      const requestedRunId = readQueryString(route.query.run)
      if (requestedRunId && (prepareRunsLoaded.value || workbench.prepareRuns.length)) {
        void ensureSelectedPrepareRunLoaded(false, requestedRunId)
      }
    },
  )

  watch(
    () => prepareWorkspaceTab.value,
    (tab) => {
      if (tab === 'configure') {
        void loadActivePrepareTabData()
      }
      if (tab === 'monitor') {
        void ensurePrepareRunsLoaded()
      }
      syncPrepareTabToRoute(tab)
    },
    { immediate: true },
  )

  watch(
    () => prepareStatus.value?.status,
    (status) => {
      if (status === 'completed' && result.value) {
        prepareWorkspaceTab.value = 'results'
        return
      }
      if (status && status !== 'completed' && status !== 'failed') {
        prepareWorkspaceTab.value = 'monitor'
      }
    },
  )

  watch(
    () => result.value,
    (nextResult) => {
      if (nextResult) {
        prepareWorkspaceTab.value = 'results'
      }
    },
  )

  // --- Dataset role & year helpers (mirrors v1 logic) ---

  interface PrepareDatasetCandidate {
    id?: number | string
    original_name?: string | null
    relative_path?: string | null
  }

  function parseEtnKppDataset(item: PrepareDatasetCandidate) {
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
  const deselectedYears = reactive(new Set<number>())

  // Selection model for DataTable v-model
  const selectedPairsModel = computed<PrepareDetectedPair[]>({
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
  const detectedPairs = computed<PrepareDetectedPair[]>(() => {
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

  function pairStatus(pair: PrepareDetectedPair) {
    if (pair.posli && pair.delistavb) return 'complete'
    if (pair.posli || pair.delistavb || pair.zemljisca) return 'ready'
    return 'incomplete'
  }

  function pairStatusLabel(pair: PrepareDetectedPair) {
    const status = pairStatus(pair)
    if (status === 'complete') return t('prepare.status_complete')
    if (status === 'ready') return t('prepare.status_ready')
    return t('prepare.status_incomplete')
  }

  function isSelected(year) {
    return !deselectedYears.has(year)
  }

  function selectedPairs(): PrepareDetectedPair[] {
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

  function updateEnrichmentOptions(next: PrepareEnrichmentState) {
    Object.assign(enrichmentOptions, next)
  }

  function isTerminalPrepareStatus(status) {
    return status === 'completed' || status === 'failed'
  }

  function syncPrepareTabFromRoute(query = route.query) {
    const nextTab = readQueryTab(query.tab, prepareWorkspaceTabs, 'configure')
    if (prepareWorkspaceTab.value !== nextTab) {
      prepareWorkspaceTab.value = nextTab
    }
  }

  function syncPrepareTabToRoute(tab: string) {
    const nextTab = readQueryTab(tab, prepareWorkspaceTabs, 'configure')
    const currentTab = readQueryTab(route.query.tab, prepareWorkspaceTabs, 'configure')
    if (currentTab === nextTab) return
    void router.replace({ query: { ...route.query, tab: nextTab } })
  }

  function syncPrepareRunFromRoute(query = route.query) {
    const nextRunId = readQueryString(query.run)
    if (!nextRunId || selectedPrepareRunId.value === nextRunId) return
    selectedPrepareRunId.value = nextRunId
    if (prepareWorkspaceTab.value !== 'monitor') {
      prepareWorkspaceTab.value = 'monitor'
    }
  }

  function syncPrepareRunToRoute(jobId: string) {
    const currentRunId = readQueryString(route.query.run) || ''
    if (currentRunId === jobId) return
    void router.replace({
      query: {
        ...route.query,
        ...(jobId ? { run: jobId } : {}),
      },
    })
  }

  async function loadPrepareRunDetail(jobId: string) {
    if (!jobId) return
    selectedPrepareRunId.value = jobId
    if (prepareWorkspaceTab.value !== 'monitor') {
      prepareWorkspaceTab.value = 'monitor'
    }
    syncPrepareRunToRoute(jobId)
    await workbench.fetchPrepareRunDetail(jobId)
  }

  function stopPreparePolling() {
    activePrepareJobId = ''
    if (preparePollTimer.value) {
      clearTimeout(preparePollTimer.value)
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
        await ensureTrainingDatasetLoaded(true)
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

  async function pollPrepareStatus(jobId: string) {
    if (preparePollInFlight.value) return prepareStatus.value
    preparePollInFlight.value = true
    const requestVersion = ++preparePollVersion
    try {
      const { data } = await api.get(`/api/data/prepare-etn-kpp-bulk/status/${jobId}`)
      await handlePrepareStatus(data)
      if (
        requestVersion === preparePollVersion &&
        activePrepareJobId === jobId &&
        data &&
        !isTerminalPrepareStatus(data.status)
      ) {
        schedulePreparePoll(jobId)
      }
      return data
    } catch (e) {
      loading.value = false
      stopPreparePolling()
      error.value = getPrepareErrorMessage(e)
      return null
    } finally {
      if (requestVersion === preparePollVersion) {
        preparePollInFlight.value = false
      }
    }
  }

  function schedulePreparePoll(jobId: string, delay = 1800) {
    if (preparePollTimer.value) {
      clearTimeout(preparePollTimer.value)
    }
    preparePollTimer.value = setTimeout(() => {
      void pollPrepareStatus(jobId)
    }, delay)
  }

  function startPreparePolling(jobId: string) {
    stopPreparePolling()
    activePrepareJobId = jobId
    schedulePreparePoll(jobId)
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

  async function startBulkPrepareJob(
    pairs: Array<{
      posli_csv_path: string
      delistavb_csv_path: string
      zemljisca_csv_path?: string
      year: string
      label: string
    }>,
  ) {
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const { data } = await api.post('/api/data/prepare-etn-kpp-bulk/start', {
        pairs,
        enrichment_options: buildEnrichmentOptionsPayload(),
      })
      await handlePrepareStatus(data)
      void ensurePrepareRunsLoaded(true)
      startPreparePolling(data.job_id)
    } catch (e) {
      const activeJob = e?.response?.status === 409 ? e?.response?.data?.detail : null
      if (activeJob?.job_id) {
        error.value = t('prepare.jobAlreadyRunning')
        await handlePrepareStatus(activeJob)
        void ensurePrepareRunsLoaded(true)
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
      await ensureTrainingDatasetLoaded(true)
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
      await ensureTrainingDatasetLoaded(true)
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
  const trainingDatasetRows = computed<PrepareTrainingDatasetRow[]>(() => {
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

  function getDatasetPaths(): Array<{ label: string; value: string }> {
    return datasets.value.map((d) => ({
      label: d.original_name,
      value: d.relative_path,
    }))
  }

  function openModelView() {
    router.push('/admin/model')
  }

  // Computed data for per_year DataTable
  const perYearRows = computed<PreparePerYearRow[]>(() => {
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
      String(persistedEnrichmentOptions.value.variant_label || '') ||
      enrichmentOptions.variant_label.trim() ||
      t('prepare.defaultVariantLabel'),
  )

  const enrichmentTotals = computed<PrepareEnrichmentTotals>(() =>
    summarizeGursEnrichment(enrichmentRows.value),
  )

  // Progress pipeline helpers

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

  function pipelineStepState(rank: number): PrepareStepState {
    const s = prepareStatus.value
    if (!s) return 'pending'
    if (s.status === 'failed') return rank <= (STAGE_RANK[s.stage ?? ''] ?? 0) ? 'error' : 'pending'
    const cur = STAGE_RANK[s.stage ?? ''] ?? 0
    if (rank < cur) return 'done'
    if (rank === cur) return s.status === 'completed' ? 'done' : 'active'
    return 'pending'
  }

  function spatialSubStepState(phase: string): PrepareStepState {
    const s = prepareStatus.value
    if (!s) return 'pending'
    if (s.stage !== 'spatial_enrichment_merged' && s.status !== 'completed') {
      return (STAGE_RANK[s.stage ?? ''] ?? 0 > 4) ? 'done' : 'pending'
    }
    if (s.status === 'completed') return 'done'
    const curRank = SPATIAL_PHASE_RANK[s.spatial_phase ?? ''] ?? 0
    const phaseRank = SPATIAL_PHASE_RANK[phase] ?? 0
    // spatial_phase not yet set; treat kn (rank 1) as active.
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
        return t('prepare.stageSpatialEnrichmentMerged', { rows: status?.rows ?? '...' })
      case 'completed':
        return t('prepare.stageCompleted')
      case 'error':
        return t('prepare.stageError')
      default:
        return t('prepare.stageInitializing')
    }
  })

  const prepareTimeline = computed<PrepareTimelineStep[]>(() => {
    const status = prepareStatus.value
    const isPairsStage = PAIR_STAGES.has(status?.stage ?? '')
    const pairStageLabel = status?.current_label ? String(status.current_label) : ''
    const pairProgress =
      status?.total_pairs != null
        ? t('prepare.stepPairsProgress', {
            done: status.pairs_completed ?? 0,
            total: status.total_pairs,
          })
        : ''

    return [
      {
        key: 'init',
        label: t('prepare.stepInit'),
        state: pipelineStepState(1),
      },
      {
        key: 'pairs',
        label: t('prepare.stepPairs'),
        state: pipelineStepState(2),
        meta: pairProgress || undefined,
        detail:
          isPairsStage && pairStageLabel
            ? t('prepare.stepPairsCurrent', { label: pairStageLabel })
            : undefined,
      },
      {
        key: 'merge',
        label: t('prepare.stepMerge'),
        state: pipelineStepState(3),
      },
      {
        key: 'spatial',
        label: t('prepare.stepSpatial'),
        state: pipelineStepState(4),
        meta:
          status?.rows && pipelineStepState(4) === 'active'
            ? t('data.previewRows', { count: fmt(status.rows) })
            : undefined,
        substeps:
          pipelineStepState(4) === 'pending'
            ? []
            : activeSpatialPhases.value.map((phase) => ({
                key: phase.key,
                label: phase.label,
                state: spatialSubStepState(phase.key),
              })),
      },
      {
        key: 'done',
        label: t('prepare.stepDone'),
        state: pipelineStepState(5),
      },
    ]
  })

  const detectedPairCount = computed(() => detectedPairs.value.length)
  const selectedPairCount = computed(() => selectedPairs().length)

  const prepareSummaryCards = computed(() => [
    {
      label: t('prepare.autoEtn'),
      value: formatNumber(selectedPairCount.value),
      meta: `${formatNumber(detectedPairCount.value)} ${t('prepare.year')}`,
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

    <Tabs v-model:value="prepareWorkspaceTab" class="prepare-stage-tabs">
      <TabList>
        <Tab value="configure">{{ t('prepare.stepInit') }}</Tab>
        <Tab value="monitor">{{ t('prepare.prepareProgress') }}</Tab>
        <Tab value="results">{{ t('prepare.stepDone') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="configure">
          <section class="prepare-workspace-grid prepare-workspace-grid--single">
            <div
              v-if="bootstrapLoading || (detectedPairsLoading && !detectedPairsLoaded)"
              class="prepare-workbench-panel prepare-workbench-panel--loading"
            >
              <div class="prepare-loading-shell" aria-busy="true">
                <div class="prepare-loading-tabs">
                  <Skeleton width="9rem" height="2.4rem" border-radius="999px" />
                  <Skeleton width="9rem" height="2.4rem" border-radius="999px" />
                  <Skeleton width="9rem" height="2.4rem" border-radius="999px" />
                </div>
                <Skeleton width="42%" height="1rem" />
                <Skeleton width="74%" height="0.95rem" />
                <Skeleton width="100%" height="10rem" border-radius="var(--radius-sm)" />
                <Skeleton width="100%" height="12rem" border-radius="var(--radius-sm)" />
                <div class="prepare-loading-action">
                  <Skeleton width="11rem" height="2.8rem" border-radius="999px" />
                </div>
              </div>
            </div>

            <div v-else class="prepare-workbench-panel">
              <Tabs v-model:value="etnMode">
                <TabList>
                  <Tab value="bulk">{{ t('prepare.autoEtn') }}</Tab>
                  <Tab value="single">{{ t('prepare.singleEtn') }}</Tab>
                  <Tab value="manual">{{ t('prepare.manualMapping') }}</Tab>
                </TabList>

                <TabPanels>
                  <!-- Bulk ETN -->
                  <TabPanel value="bulk">
                    <div class="prepare-tab-panel">
                      <div class="prepare-section-head">
                        <PageHeader
                          compact
                          :eyebrow="t('prepare.autoEtn')"
                          :title="t('prepare.autoEtn')"
                          :description="t('prepare.autoEtnDesc')"
                        />

                        <div v-if="detectedPairs.length" class="prepare-selection-summary">
                          <div class="prepare-selection-stat">
                            <span class="prepare-selection-label">{{ t('prepare.autoEtn') }}</span>
                            <strong
                              >{{ fmt(selectedPairCount) }} / {{ fmt(detectedPairCount) }}</strong
                            >
                          </div>
                          <p class="muted prepare-selection-note">
                            {{ allSelected ? t('prepare.deselectAll') : t('prepare.selectAll') }}
                          </p>
                        </div>
                      </div>

                      <div v-if="!detectedPairs.length" class="muted">
                        {{ t('prepare.noPairsDetected') }}
                      </div>

                      <div v-else>
                        <details class="prepare-fold" open>
                          <summary>{{ t('prepare.enrichmentOptions') }}</summary>
                          <PrepareEnrichmentOptions
                            :model-value="enrichmentOptions"
                            @update:model-value="updateEnrichmentOptions"
                            :title="t('prepare.enrichmentOptions')"
                            :description="t('prepare.enrichmentOptionsDesc')"
                            :options="ENRICHMENT_OPTIONS"
                            :variant-placeholder="t('prepare.variantLabelPlaceholder')"
                          />
                        </details>

                        <details class="prepare-fold" open>
                          <summary>{{ t('prepare.autoEtn') }}</summary>
                          <div class="prepare-selection-toolbar prepare-selection-toolbar--split">
                            <p class="prepare-selection-toolbar-note muted">
                              {{ fmt(selectedPairCount) }} / {{ fmt(detectedPairCount) }}
                            </p>
                            <Button
                              size="small"
                              severity="secondary"
                              text
                              :icon="allSelected ? 'pi pi-check-square' : 'pi pi-stop'"
                              :label="
                                allSelected ? t('prepare.deselectAll') : t('prepare.selectAll')
                              "
                              @click="allSelected ? deselectAll() : selectAll()"
                            />
                          </div>

                          <div class="prepare-table-shell">
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
                          </div>
                        </details>

                        <div class="prepare-action-row">
                          <Button
                            icon="pi pi-cog"
                            :loading="loading"
                            :disabled="loading || trainingLocked || !selectedPairs().length"
                            :label="loading ? t('common.loading') : t('prepare.prepareButton')"
                            @click="prepareEtnBulk"
                          />
                        </div>
                      </div>
                    </div>
                  </TabPanel>

                  <!-- Single ETN -->
                  <TabPanel value="single">
                    <div class="prepare-tab-panel">
                      <PageHeader
                        compact
                        :eyebrow="t('prepare.singleEtn')"
                        :title="t('prepare.singleEtn')"
                        :description="t('prepare.singleEtnDesc')"
                      />

                      <div class="prepare-form-grid">
                        <div>
                          <label class="form-label">{{ t('prepare.posliFile') }}</label>
                          <Select
                            v-model="singlePosli"
                            :options="[
                              { label: t('prepare.selectFile'), value: '' },
                              ...getDatasetPaths(),
                            ]"
                            option-label="label"
                            option-value="value"
                            :loading="datasetsLoadingForSelection"
                          />
                        </div>
                        <div>
                          <label class="form-label">{{ t('prepare.delistavbFile') }}</label>
                          <Select
                            v-model="singleDelistavb"
                            :options="[
                              { label: t('prepare.selectFile'), value: '' },
                              ...getDatasetPaths(),
                            ]"
                            option-label="label"
                            option-value="value"
                            :loading="datasetsLoadingForSelection"
                          />
                        </div>
                      </div>

                      <PrepareEnrichmentOptions
                        class="mt-4"
                        :model-value="enrichmentOptions"
                        @update:model-value="updateEnrichmentOptions"
                        :title="t('prepare.enrichmentOptions')"
                        :description="t('prepare.enrichmentOptionsDesc')"
                        :options="ENRICHMENT_OPTIONS"
                        :variant-placeholder="t('prepare.variantLabelPlaceholder')"
                      />

                      <Button
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
                    <div class="prepare-tab-panel">
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
                          :options="[
                            { label: t('prepare.selectFile'), value: '' },
                            ...getDatasetPaths(),
                          ]"
                          option-label="label"
                          option-value="value"
                          :loading="datasetsLoadingForSelection"
                        />
                      </div>

                      <div>
                        <label class="form-label">{{ t('prepare.columnMapping') }}</label>
                        <Textarea
                          v-model="columnMap"
                          class="prepare-code-textarea"
                          rows="8"
                          :placeholder="columnMapPlaceholder"
                          auto-resize
                        />
                      </div>

                      <Button
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
          </section>
        </TabPanel>

        <TabPanel value="monitor">
          <section class="prepare-monitor-grid">
            <aside class="prepare-side-stack">
              <div
                v-if="prepareRunsLoading && !prepareRunsLoaded"
                class="prepare-workbench-panel prepare-workbench-panel--loading"
                aria-busy="true"
              >
                <div class="prepare-loading-shell">
                  <Skeleton width="42%" height="1rem" />
                  <Skeleton width="70%" height="0.95rem" />
                  <Skeleton width="100%" height="10rem" border-radius="var(--radius-sm)" />
                </div>
              </div>
              <AdminRunDetailPanel
                v-else
                :eyebrow="t('nav.prepare')"
                :title="t('workbench.recentPrepareRuns')"
                :description="t('workbench.prepareRunDetailHint')"
                run-type="prepare"
                :runs="workbench.prepareRuns.slice(0, 8)"
                :selected-run-id="selectedPrepareRunId"
                :selected-run="selectedPrepareRun"
                :loading="workbench.prepareRunDetailLoading"
                :error="workbench.prepareRunDetailError || workbench.prepareRunsError"
                @select="loadPrepareRunDetail"
              />

              <div v-if="error" class="state-card state-card-stack" role="alert">
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

              <PrepareProgressPanel
                v-if="prepareProgressVisible"
                :eyebrow="t('prepare.prepareProgress')"
                :title="prepareStageLabel"
                :description="t('prepare.jobProgressDesc')"
                :status-label="prepareStatusLabel"
                :status-severity="prepareStatusSeverity"
                :progress="prepareProgress"
                :current-label="prepareStatus?.current_label"
                :timeline="prepareTimeline"
                :error="prepareStatus?.error"
                @retry="syncExistingPrepareJob"
              />
            </aside>

            <div class="card prepare-monitor-card">
              <PageHeader
                compact
                :eyebrow="t('prepare.prepareProgress')"
                :title="prepareStatusLabel"
                :description="prepareStageLabel"
              />
              <div class="kpi-grid">
                <MetricCard
                  v-for="item in prepareSummaryCards"
                  :key="item.label"
                  :label="item.label"
                  :value="item.value"
                  :meta="item.meta"
                  :tone="item.tone"
                />
              </div>
            </div>
          </section>
        </TabPanel>

        <TabPanel value="results">
          <PrepareResultsWorkspace
            v-if="result"
            :result="result"
            :selected-variant-label="selectedVariantLabel"
            :per-year-rows="perYearRows"
            :training-dataset-rows="trainingDatasetRows"
            :enrichment-rows="enrichmentRows"
            :enrichment-totals="enrichmentTotals"
            @open-model="openModelView"
          />
          <div v-else class="state-card state-card-stack" role="status">
            <EmptyState icon="pi pi-chart-line" :message="t('common.noData')" />
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
  .prepare-page {
    display: grid;
    gap: var(--space-section);
    --page-accent: var(--primary);
    --page-accent-2: var(--accent);
  }

  .prepare-stage-tabs {
    display: grid;
    gap: var(--space-section);
  }

  .prepare-stage-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 66%, var(--page-accent) 34%);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--surface-soft) 84%, var(--page-accent) 16%);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .prepare-stage-tabs :deep(.p-tabpanels) {
    padding-top: 0.2rem;
  }

  .prepare-workspace-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.95fr);
    gap: var(--space-section);
    align-items: start;
  }

  .prepare-workspace-grid--single {
    grid-template-columns: 1fr;
  }

  .prepare-monitor-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-section);
    align-items: start;
  }

  .prepare-main-stack,
  .prepare-side-stack {
    display: grid;
    gap: var(--space-section);
    min-width: 0;
  }

  .prepare-workbench-panel {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--page-accent-2) 14%, transparent),
        transparent 42%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 97%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .prepare-workbench-panel--loading {
    min-height: 30rem;
  }

  .prepare-loading-shell,
  .prepare-loading-tabs {
    display: grid;
    gap: 0.85rem;
  }

  .prepare-loading-tabs {
    grid-template-columns: repeat(3, minmax(0, max-content));
    align-items: center;
  }

  .prepare-loading-action {
    display: flex;
    justify-content: flex-end;
  }

  .prepare-monitor-card {
    order: -1;
    display: grid;
    gap: 1rem;
    padding: clamp(1.05rem, 1.45vw, 1.4rem);
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--page-accent) 28%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--page-accent-2) 16%, transparent),
        transparent 44%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .prepare-tab-panel {
    display: grid;
    gap: 1rem;
  }

  .prepare-section-head {
    display: grid;
    gap: 0.75rem;
  }

  .prepare-selection-summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.8rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 62%, var(--page-accent) 38%);
    border-radius: var(--radius-sm);
    background:
      linear-gradient(
        140deg,
        color-mix(in srgb, var(--page-accent) 12%, transparent),
        transparent 52%
      ),
      color-mix(in srgb, var(--surface-muted) 72%, var(--surface));
  }

  .prepare-selection-stat {
    display: grid;
    gap: 0.2rem;
  }

  .prepare-selection-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
  }

  .prepare-selection-stat strong {
    font-size: 1.15rem;
    line-height: 1.1;
  }

  .prepare-selection-note {
    margin: 0;
    text-align: right;
  }

  .prepare-selection-toolbar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .prepare-selection-toolbar--split {
    justify-content: space-between;
  }

  .prepare-selection-toolbar-note {
    margin: 0;
  }

  .prepare-fold {
    display: grid;
    gap: 0.8rem;
  }

  .prepare-fold > summary {
    list-style: none;
    cursor: pointer;
    user-select: none;
    padding: 0.75rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--page-accent) 40%);
    background:
      linear-gradient(
        128deg,
        color-mix(in srgb, var(--page-accent-2) 12%, transparent),
        transparent 56%
      ),
      var(--surface-subtle);
    color: var(--text-soft);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .prepare-fold > summary::-webkit-details-marker {
    display: none;
  }

  .prepare-fold[open] > summary {
    color: var(--text);
    border-color: color-mix(in srgb, var(--border) 52%, var(--page-accent) 48%);
  }

  .prepare-form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .prepare-form-surface {
    margin-top: 0.15rem;
  }

  .prepare-table-shell {
    overflow-x: auto;
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    border-radius: var(--radius-sm);
    background: var(--surface);
  }

  .prepare-table-shell :deep(.p-datatable) {
    min-width: 100%;
  }

  .prepare-action-row {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
  }

  .prepare-action-row :deep(.p-button) {
    min-width: 11rem;
  }

  .prepare-code-textarea {
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
    width: 100%;
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
  }

  @media (max-width: 1080px) {
    .prepare-workspace-grid {
      grid-template-columns: 1fr;
    }

    .prepare-monitor-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .prepare-workbench-panel {
      padding: 0.9rem;
    }

    .prepare-selection-summary,
    .prepare-selection-toolbar--split,
    .prepare-action-row {
      align-items: flex-start;
      flex-direction: column;
    }

    .prepare-selection-note {
      text-align: left;
    }

    .prepare-form-grid {
      grid-template-columns: 1fr;
    }

    .prepare-action-row :deep(.p-button) {
      width: 100%;
      min-width: 0;
    }

    .prepare-loading-tabs {
      grid-template-columns: 1fr;
    }

    .prepare-loading-action {
      justify-content: flex-start;
    }
  }
</style>
