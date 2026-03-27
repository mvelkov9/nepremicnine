<script setup lang="ts">
  import { ref, onMounted, onUnmounted, computed, reactive } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import PageHeader from '../components/PageHeader.vue'
  import MetricCard from '../components/MetricCard.vue'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import api from '../composables/useApi'
  import { getApiErrorMessage } from '../utils/apiError'
  import { buildGursEnrichmentRows, summarizeGursEnrichment } from '../utils/enrichmentSummary'
  import { formatNumber } from '../utils/format'

  const { t } = useI18n()
  const dataStore = useDataStore()
  const modelStore = useModelStore()
  const router = useRouter()

  const loading = ref(false)
  const error = ref('')
  const result = ref(null)
  const prepareStatus = ref(null)
  const preparePollTimer = ref<ReturnType<typeof setInterval> | null>(null)
  const enrichmentOptions = reactive({
    enable_rn: true,
    enable_ev: true,
    enable_kn: true,
    enable_gji: true,
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
    result?: Record<string, unknown> | null
    error?: string | null
  }

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
  const PREPARE_REQUEST_TIMEOUT_MS = 10 * 60 * 1000

  onMounted(async () => {
    await Promise.all([
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
      modelStore.fetchActiveTraining(),
    ])
    await syncExistingPrepareJob()
  })

  onUnmounted(() => {
    stopPreparePolling()
  })

  // --- Dataset role & year helpers (mirrors v1 logic) ---

  function parseEtnKppDataset(item) {
    const candidates = [item.original_name || '', item.relative_path || '']

    for (const candidate of candidates) {
      const text = String(candidate).toUpperCase()
      const yearMatch = text.match(/ETN_SLO_(20\d{2})_KPP_/)
      if (!yearMatch) continue

      if (text.includes('_KPP_POSLI_')) {
        return { role: 'posli', year: Number(yearMatch[1]) }
      }

      if (text.includes('_KPP_DELISTAVB_')) {
        return { role: 'delistavb', year: Number(yearMatch[1]) }
      }

      if (text.includes('_KPP_ZEMLJISCA_') || text.includes('_KPP_ZEMLJISC_')) {
        return { role: 'zemljisca', year: Number(yearMatch[1]) }
      }
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
    const byYear = new Map()
    const items = datasets.value || []
    for (const item of items) {
      const { role, year } = parseEtnKppDataset(item)
      if (!year || (role !== 'posli' && role !== 'delistavb' && role !== 'zemljisca')) continue
      if (!byYear.has(year))
        byYear.set(year, { year, posli: null, delistavb: null, zemljisca: null })
      const row = byYear.get(year)
      // Keep latest upload per role (highest id)
      if (role === 'posli' && (!row.posli || item.id > row.posli.id)) row.posli = item
      if (role === 'delistavb' && (!row.delistavb || item.id > row.delistavb.id))
        row.delistavb = item
      if (role === 'zemljisca' && (!row.zemljisca || item.id > row.zemljisca.id))
        row.zemljisca = item
    }
    return Array.from(byYear.values())
      .filter((r) => r.posli && r.delistavb)
      .sort((a, b) => a.year - b.year)
  })

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
      enable_emv: enrichmentOptions.enable_emv,
      variant_label: enrichmentOptions.variant_label.trim() || undefined,
    }
  }

  function isTerminalPrepareStatus(status) {
    return status === 'completed' || status === 'failed'
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
      case 'completed':
        return t('prepare.stageCompleted')
      case 'error':
        return t('prepare.stageError')
      default:
        return t('prepare.stageInitializing')
    }
  })

  const prepareProgressCards = computed(() => {
    const status = prepareStatus.value
    if (!status) return []

    return [
      {
        label: t('prepare.currentYear'),
        value: status.current_label || t('prepare.unknownYear'),
        meta:
          status.current_pair_index && status.total_pairs
            ? t('prepare.currentPairMeta', {
                current: status.current_pair_index,
                total: status.total_pairs,
              })
            : t('common.noData'),
      },
      {
        label: t('prepare.pairsCompleted'),
        value: fmt(status.pairs_completed || 0),
        meta: status.total_pairs
          ? t('prepare.totalPairsMeta', { total: status.total_pairs })
          : t('common.noData'),
      },
      {
        label: t('prepare.prepareProgress'),
        value: `${status.progress || 0}%`,
        meta: prepareStageLabel.value,
      },
    ]
  })
</script>

<template>
  <div class="prepare-page">
    <section class="card admin-hero prepare-hero">
      <PageHeader
        :eyebrow="t('nav.prepare')"
        :title="t('prepare.title')"
        :description="trainingLocked ? t('prepare.trainingLockedHint') : t('layout.page.prepare')"
      />
    </section>

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

                  <div class="toggle-grid">
                    <label class="toggle-chip">
                      <ToggleSwitch v-model="enrichmentOptions.enable_rn" />
                      <span>{{ t('prepare.enableRn') }}</span>
                    </label>
                    <label class="toggle-chip">
                      <ToggleSwitch v-model="enrichmentOptions.enable_ev" />
                      <span>{{ t('prepare.enableEv') }}</span>
                    </label>
                    <label class="toggle-chip">
                      <ToggleSwitch v-model="enrichmentOptions.enable_kn" />
                      <span>{{ t('prepare.enableKn') }}</span>
                    </label>
                    <label class="toggle-chip">
                      <ToggleSwitch v-model="enrichmentOptions.enable_gji" />
                      <span>{{ t('prepare.enableGji') }}</span>
                    </label>
                    <label class="toggle-chip">
                      <ToggleSwitch v-model="enrichmentOptions.enable_emv" />
                      <span>{{ t('prepare.enableEmv') }}</span>
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
                  />
                </div>
                <div>
                  <label class="form-label">{{ t('prepare.delistavbFile') }}</label>
                  <Select
                    v-model="singleDelistavb"
                    :options="[{ label: t('prepare.selectFile'), value: '' }, ...getDatasetPaths()]"
                    option-label="label"
                    option-value="value"
                  />
                </div>
              </div>

              <div class="enrichment-config-card mt-4">
                <div class="enrichment-config-head">
                  <h3>{{ t('prepare.enrichmentOptions') }}</h3>
                  <p class="muted">{{ t('prepare.enrichmentOptionsDesc') }}</p>
                </div>

                <div class="toggle-grid">
                  <label class="toggle-chip">
                    <ToggleSwitch v-model="enrichmentOptions.enable_rn" />
                    <span>{{ t('prepare.enableRn') }}</span>
                  </label>
                  <label class="toggle-chip">
                    <ToggleSwitch v-model="enrichmentOptions.enable_ev" />
                    <span>{{ t('prepare.enableEv') }}</span>
                  </label>
                  <label class="toggle-chip">
                    <ToggleSwitch v-model="enrichmentOptions.enable_kn" />
                    <span>{{ t('prepare.enableKn') }}</span>
                  </label>
                  <label class="toggle-chip">
                    <ToggleSwitch v-model="enrichmentOptions.enable_gji" />
                    <span>{{ t('prepare.enableGji') }}</span>
                  </label>
                  <label class="toggle-chip">
                    <ToggleSwitch v-model="enrichmentOptions.enable_emv" />
                    <span>{{ t('prepare.enableEmv') }}</span>
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

      <ProgressBar :value="prepareStatus?.progress || 0" :show-value="false" />

      <div class="result-metrics compact-metrics">
        <MetricCard
          v-for="card in prepareProgressCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
          :meta="card.meta"
        />
      </div>

      <p v-if="prepareStatus?.error" class="error-text">{{ prepareStatus.error }}</p>
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

  .toggle-grid {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .toggle-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.65rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface-muted);
  }

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

  .variant-field {
    max-width: 24rem;
  }

  .result-metrics {
    align-items: stretch;
  }

  .result-metrics :deep(.metric-card) {
    flex: 1 1 220px;
  }

  .compact-metrics :deep(.metric-card) {
    min-width: 12rem;
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

  @media (max-width: 720px) {
    .form-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
