<script setup lang="ts">
  const NONE = '_none' as const

  definePageMeta({ middleware: ['admin'] })

  const { t } = useI18n()
  const dataStore = useDataStore()
  const modelStore = useModelStore()
  const api = useApi()

  // --- State ---

  const loading = ref(false)
  const error = ref('')
  const result = ref<PrepareResult | null>(null)

  // Dataset path options for Select
  // ETN mode
  type EtnMode = 'bulk' | 'single' | 'manual'
  const etnModes: EtnMode[] = ['bulk', 'single', 'manual']
  const etnMode = ref<EtnMode>('bulk')

  // Single-pair form
  const singlePosli = ref(NONE)
  const singleDelistavb = ref(NONE)

  // Manual mapping form
  const manualCsvPath = ref(NONE)
  const columnMap = ref('')
  const columnMapPlaceholder = `{
  "POGODBENA_CENA": "price_eur",
  "PRODANA_POVRSINA": "size_m2",
  "LETO_IZGRADNJE": "year_built",
  "NADSTROPJE": "floor",
  "OBCINA": "municipality",
  "VRSTA": "property_type"
}`

  // --- Types ---

  interface DatasetItem {
    id: number
    original_name: string
    relative_path: string
    row_count: number | null
    source_type: string
    uploaded_at: string
  }

  interface DetectedPair {
    year: number
    posli: DatasetItem | null
    delistavb: DatasetItem | null
    zemljisca: DatasetItem | null
  }

  interface PrepareReport {
    label: string
    status: string
    rows?: number
    reason?: string
    used_size_column?: string
    used_property_type_column?: string
  }

  interface PrepareResult {
    rows?: number
    total_rows?: number
    columns?: string[]
    per_year?: Record<string, number>
    reports?: PrepareReport[]
    training_dataset?: {
      relative_path: string
      rows: number
    }
  }

  // --- Computed ---

  const datasets = computed(() => (dataStore.datasets ?? []) as DatasetItem[])
  const trainingLocked = computed(() => modelStore.training)

  // Track deselected years
  const deselectedYears = reactive(new Set<number>())

  const detectedPairs = computed<DetectedPair[]>(() => {
    const byYear = new Map<number, DetectedPair>()
    for (const item of datasets.value) {
      const role = datasetRole(item)
      const year = datasetYear(item)
      if (!year || (role !== 'posli' && role !== 'delistavb' && role !== 'zemljisca')) continue
      if (!byYear.has(year)) {
        byYear.set(year, { year, posli: null, delistavb: null, zemljisca: null })
      }
      const row = byYear.get(year)!
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

  const selectedPairsList = computed(() =>
    detectedPairs.value.filter((p) => !deselectedYears.has(p.year)),
  )

  const selectedPairCount = computed(() => selectedPairsList.value.length)

  const allSelected = computed(
    () =>
      detectedPairs.value.length > 0 &&
      detectedPairs.value.every((p) => !deselectedYears.has(p.year)),
  )

  const prepareHighlights = computed(() => [
    {
      label: t('prepare.autoEtn'),
      value: fmt(detectedPairs.value.length),
      meta: t('prepare.noPairsDetected'),
    },
    {
      label: t('prepare.yearsCovered'),
      value: fmt(selectedPairCount.value),
      meta: t('prepare.year'),
    },
    {
      label: t('data.datasets'),
      value: fmt(datasets.value.length),
      meta: t('data.datasetLibrary'),
    },
    {
      label: t('model.trainingStatus'),
      value: trainingLocked.value ? t('model.training') : t('model.modelReady'),
      meta: trainingLocked.value ? t('prepare.trainingLockedHint') : t('prepare.openModel'),
    },
  ])

  // Mode tabs
  const tabItems = computed(() => [
    { label: t('prepare.autoEtn'), slot: 'bulk' as const },
    { label: t('prepare.singleEtn'), slot: 'single' as const },
    { label: t('prepare.manualMapping'), slot: 'manual' as const },
  ])

  // Pair table columns
  const pairColumns = computed(() => [
    { accessorKey: 'selected', header: '', enableSorting: false },
    { accessorKey: 'year', header: t('prepare.year') },
    { accessorKey: 'posli', header: t('prepare.posliFile'), enableSorting: false },
    { accessorKey: 'delistavb', header: t('prepare.delistavbFile'), enableSorting: false },
  ])

  // Per-year result columns
  const perYearColumns = computed(() => [
    { accessorKey: 'year', header: t('prepare.year') },
    { accessorKey: 'rows', header: t('data.rows') },
  ])

  // Report table columns
  const reportColumns = computed(() => [
    { accessorKey: 'label', header: t('prepare.year') },
    { accessorKey: 'status', header: t('prepare.reportStatus') },
    { accessorKey: 'rows', header: t('data.rows') },
    { accessorKey: 'detail', header: t('prepare.reportDetail'), enableSorting: false },
  ])

  const datasetPathOptions = computed(() => [
    { label: t('prepare.selectFile'), value: NONE },
    ...datasets.value.map((d) => ({
      label: d.original_name,
      value: d.relative_path,
    })),
  ])

  // Per-year result rows for UTable
  const perYearRows = computed(() => {
    if (!result.value?.per_year) return []
    return Object.entries(result.value.per_year).map(([year, rows]) => ({
      year,
      rows,
    }))
  })

  // --- Helpers ---

  function datasetRole(item: DatasetItem): string {
    const text = `${item.original_name || ''} ${item.relative_path || ''}`.toLowerCase()
    if (text.includes('posli') || text.includes('posle')) return 'posli'
    if (text.includes('delistavb') || text.includes('deli_stavb')) return 'delistavb'
    if (text.includes('zemljisca') || text.includes('zemljisc')) return 'zemljisca'
    return 'other'
  }

  function datasetYear(item: DatasetItem): number | null {
    const match = `${item.original_name || ''} ${item.relative_path || ''}`.match(/(20\d{2})/)
    return match ? Number(match[1]) : null
  }

  function isSelected(year: number): boolean {
    return !deselectedYears.has(year)
  }

  function togglePair(pair: DetectedPair): void {
    if (deselectedYears.has(pair.year)) {
      deselectedYears.delete(pair.year)
    } else {
      deselectedYears.add(pair.year)
    }
  }

  function toggleAll(checked: boolean): void {
    if (checked) {
      deselectedYears.clear()
    } else {
      for (const p of detectedPairs.value) {
        deselectedYears.add(p.year)
      }
    }
  }

  function getReportDetail(report: PrepareReport): string {
    return (
      report.reason ||
      report.used_size_column ||
      report.used_property_type_column ||
      t('common.noData')
    )
  }

  function fmt(value: number, decimals = 0): string {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function getPrepareErrorMessage(apiError: any): string {
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

  // --- Actions ---

  async function prepareEtnBulk(): Promise<void> {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const selected = selectedPairsList.value
      if (!selected.length) {
        error.value = t('prepare.noPairs')
        return
      }

      const pairs = selected.map((p) => ({
        posli_csv_path: p.posli!.relative_path,
        delistavb_csv_path: p.delistavb!.relative_path,
        ...(p.zemljisca ? { zemljisca_csv_path: p.zemljisca.relative_path } : {}),
        year: String(p.year),
        label: String(p.year),
      }))

      const { data } = await api.post<PrepareResult>('/api/data/prepare-etn-kpp-bulk', { pairs })
      result.value = data
      await dataStore.fetchTrainingDataset()
    } catch (e) {
      error.value = getPrepareErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function prepareEtnSingle(): Promise<void> {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const { data } = await api.post<PrepareResult>('/api/data/prepare-etn-kpp', {
        posli_csv_path: singlePosli.value,
        delistavb_csv_path: singleDelistavb.value,
      })
      result.value = data
      await dataStore.fetchTrainingDataset()
    } catch (e) {
      error.value = getPrepareErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function prepareManual(): Promise<void> {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const map = JSON.parse(columnMap.value)
      const { data } = await api.post<PrepareResult>('/api/data/prepare-train', {
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

  function openModelView(): void {
    navigateTo('/admin/model')
  }

  function setEtnMode(payload: string | number): void {
    const nextMode =
      typeof payload === 'number'
        ? etnModes[payload]
        : etnModes.find((mode) => mode === payload)

    if (nextMode) {
      etnMode.value = nextMode
    }
  }

  // --- Init ---

  useLazyAsyncData('admin-priprava', () =>
    Promise.all([
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
      modelStore.fetchActiveTraining(),
    ]),
  )
</script>

<template>
  <div class="prepare-page">
    <!-- Hero -->
    <section class="card">
      <div class="section-head">
        <div>
          <p class="eyebrow">{{ t('nav.prepare') }}</p>
          <h1>{{ t('prepare.title') }}</h1>
          <p class="muted">
            {{ trainingLocked ? t('prepare.trainingLockedHint') : t('layout.page.prepare') }}
          </p>
        </div>
        <div class="hero-actions">
          <NuxtLink to="/admin/podatki">
            <UButton
              icon="i-lucide-database"
              variant="outline"
              color="neutral"
              :label="t('data.datasets')"
            />
          </NuxtLink>
          <NuxtLink to="/admin/model">
            <UButton icon="i-lucide-bolt" :label="t('prepare.openModel')" />
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- Highlights -->
    <section class="highlights-grid">
      <KpiCard
        v-for="card in prepareHighlights"
        :key="card.label"
        :label="card.label"
        :value="card.value"
        :meta="card.meta"
      />
    </section>

    <!-- Mode tabs -->
    <UTabs
      :items="tabItems"
      @update:model-value="setEtnMode"
    >
      <!-- Bulk ETN -->
      <template #bulk>
        <section class="card tab-panel">
          <div class="section-head compact">
            <div>
              <p class="eyebrow subtle">{{ t('prepare.autoEtn') }}</p>
              <h2>{{ t('prepare.autoEtn') }}</h2>
              <p class="muted">{{ t('prepare.autoEtnDesc') }}</p>
            </div>
          </div>

          <div v-if="!detectedPairs.length" class="muted">
            {{ t('prepare.noPairsDetected') }}
          </div>

          <template v-else>
            <!-- Selection summary -->
            <div class="selection-summary">
              <article class="selection-card">
                <span class="selection-label">{{ t('prepare.yearsCovered') }}</span>
                <strong>{{ fmt(selectedPairCount) }}</strong>
                <small class="muted">{{ t('prepare.year') }}</small>
              </article>
              <article class="selection-card">
                <span class="selection-label">{{ t('prepare.autoEtn') }}</span>
                <strong>{{ fmt(detectedPairs.length) }}</strong>
                <small class="muted"
                  >{{ t('prepare.posliFile') }} / {{ t('prepare.delistavbFile') }}</small
                >
              </article>
            </div>

            <!-- Pair table -->
            <div class="table-wrap">
              <UTable :columns="pairColumns" :data="detectedPairs">
                <template #selected-cell="{ row }">
                  <UCheckbox
                    :model-value="isSelected(row.original.year)"
                    @update:model-value="togglePair(row.original)"
                  />
                </template>
                <template #selected-header>
                  <UCheckbox
                    :model-value="allSelected"
                    @update:model-value="toggleAll($event as boolean)"
                  />
                </template>
                <template #year-cell="{ row }">
                  <UBadge :label="String(row.original.year)" color="info" variant="soft" />
                </template>
                <template #posli-cell="{ row }">
                  {{ row.original.posli?.original_name ?? '—' }}
                </template>
                <template #delistavb-cell="{ row }">
                  {{ row.original.delistavb?.original_name ?? '—' }}
                </template>
              </UTable>
            </div>

            <div class="actions-row">
              <UButton
                icon="i-lucide-cog"
                :loading="loading"
                :disabled="loading || trainingLocked || !selectedPairsList.length"
                :label="loading ? t('common.loading') : t('prepare.prepareButton')"
                @click="prepareEtnBulk"
              />
            </div>
          </template>
        </section>
      </template>

      <!-- Single ETN -->
      <template #single>
        <section class="card tab-panel">
          <div class="section-head compact">
            <div>
              <p class="eyebrow subtle">{{ t('prepare.singleEtn') }}</p>
              <h2>{{ t('prepare.singleEtn') }}</h2>
              <p class="muted">{{ t('prepare.singleEtnDesc') }}</p>
            </div>
          </div>

          <div class="form-grid">
            <label class="field">
              <span class="form-label">{{ t('prepare.posliFile') }}</span>
              <USelectMenu v-model="singlePosli" :items="datasetPathOptions" value-key="value" />
            </label>
            <label class="field">
              <span class="form-label">{{ t('prepare.delistavbFile') }}</span>
              <USelectMenu
                v-model="singleDelistavb"
                :items="datasetPathOptions"
                value-key="value"
              />
            </label>
          </div>

          <div class="actions-row">
            <UButton
              icon="i-lucide-cog"
              :loading="loading"
              :disabled="
                loading ||
                trainingLocked ||
                !singlePosli ||
                singlePosli === NONE ||
                !singleDelistavb ||
                singleDelistavb === NONE
              "
              :label="loading ? t('common.loading') : t('prepare.prepareButton')"
              @click="prepareEtnSingle"
            />
          </div>
        </section>
      </template>

      <!-- Manual mapping -->
      <template #manual>
        <section class="card tab-panel">
          <div class="section-head compact">
            <div>
              <p class="eyebrow subtle">{{ t('prepare.manualMapping') }}</p>
              <h2>{{ t('prepare.manualMapping') }}</h2>
              <p class="muted">{{ t('prepare.manualDesc') }}</p>
            </div>
          </div>

          <label class="field">
            <span class="form-label">{{ t('prepare.sourceFile') }}</span>
            <USelectMenu v-model="manualCsvPath" :items="datasetPathOptions" value-key="value" />
          </label>

          <label class="field" style="margin-top: 1rem">
            <span class="form-label">{{ t('prepare.columnMapping') }}</span>
            <UTextarea
              v-model="columnMap"
              :rows="8"
              :placeholder="columnMapPlaceholder"
              class="font-mono text-sm"
            />
          </label>

          <div class="actions-row">
            <UButton
              icon="i-lucide-cog"
              :loading="loading"
              :disabled="
                loading || trainingLocked || !manualCsvPath || manualCsvPath === NONE || !columnMap
              "
              :label="loading ? t('common.loading') : t('prepare.prepareButton')"
              @click="prepareManual"
            />
          </div>
        </section>
      </template>
    </UTabs>

    <!-- Error -->
    <UAlert
      v-if="error"
      :description="error"
      color="error"
      variant="soft"
      icon="i-lucide-alert-circle"
    />

    <!-- Result -->
    <section v-if="result" class="card result-card">
      <div class="section-head compact">
        <div>
          <p class="eyebrow subtle">{{ t('prepare.result') }}</p>
          <h2>{{ t('prepare.result') }}</h2>
        </div>
      </div>

      <!-- KPI summary -->
      <div class="kpi-grid">
        <KpiCard
          :label="t('prepare.outputRows')"
          :value="fmt(result.rows || result.total_rows || 0)"
        />
        <KpiCard
          v-if="result.columns"
          :label="t('prepare.outputColumns')"
          :value="fmt(result.columns?.length || 0)"
        />
        <KpiCard
          v-if="result.per_year"
          :label="t('prepare.yearsCovered')"
          :value="fmt(Object.keys(result.per_year).length)"
        />
      </div>

      <!-- Per-year breakdown -->
      <div v-if="result.per_year" class="table-wrap">
        <UTable :columns="perYearColumns" :data="perYearRows">
          <template #year-cell="{ row }">
            <UBadge :label="String(row.original.year)" color="info" variant="soft" />
          </template>
          <template #rows-cell="{ row }">
            {{ fmt(row.original.rows) }}
          </template>
        </UTable>
      </div>

      <!-- Reports -->
      <div v-if="result.reports?.length" class="table-wrap">
        <UTable :columns="reportColumns" :data="result.reports">
          <template #label-cell="{ row }">
            <UBadge :label="row.original.label" color="info" variant="soft" />
          </template>
          <template #status-cell="{ row }">
            <UBadge
              :label="row.original.status"
              :color="row.original.status === 'ok' ? 'success' : 'error'"
              variant="soft"
            />
          </template>
          <template #rows-cell="{ row }">
            {{ fmt(row.original.rows || 0) }}
          </template>
          <template #detail-cell="{ row }">
            <span class="muted">{{ getReportDetail(row.original) }}</span>
          </template>
        </UTable>
      </div>

      <!-- Training dataset ready -->
      <div v-if="result.training_dataset" class="ready-card">
        <p class="eyebrow subtle">{{ t('prepare.readyForModel') }}</p>
        <strong>{{ result.training_dataset.relative_path }}</strong>
        <p class="muted">{{ fmt(result.training_dataset.rows) }} {{ t('data.rows') }}</p>
        <div class="actions-row">
          <UButton
            icon="i-lucide-arrow-right"
            :label="t('prepare.openModel')"
            @click="openModelView"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
  .prepare-page {
    display: grid;
    gap: 1rem;
  }

  .card {
    padding: 1.25rem;
    border-radius: 1.5rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
    display: grid;
    gap: 1rem;
  }

  .tab-panel {
    margin-top: 1rem;
  }

  .section-head h1 {
    font-size: clamp(1.5rem, 2vw, 2rem);
  }

  /* Highlights */
  .highlights-grid {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .kpi-card {
    display: grid;
    gap: 0.25rem;
    padding: 0.95rem 1rem;
    border-radius: 1.35rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 16px 26px rgb(15 23 42 / 6%);
  }

  .kpi-label {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .kpi-value {
    font-size: 1.25rem;
    font-weight: 700;
    font-family: var(--font-display);
  }

  .kpi-grid {
    display: grid;
    gap: 0.85rem;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  }

  /* Selection summary cards */
  .selection-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .selection-card {
    display: grid;
    gap: 0.25rem;
    padding: 0.95rem 1rem;
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

  .selection-label {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .selection-card strong {
    font-size: 1.1rem;
  }

  /* Forms */
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .field {
    display: grid;
    gap: 0.35rem;
  }

  .form-label {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--text-muted);
  }

  .form-input {
    width: 100%;
    padding: 0.7rem 0.85rem;
    border-radius: 0.85rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    color: var(--text);
    font-size: 0.9rem;
    transition: border-color 180ms ease;
  }

  .form-input:focus {
    outline: none;
    border-color: var(--primary);
  }

  .code-textarea {
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
    resize: vertical;
  }

  .actions-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 0.5rem;
  }

  /* Result card */
  .result-card {
    border-left: 4px solid var(--color-success-500, var(--success));
  }

  .ready-card {
    display: grid;
    gap: 0.35rem;
    padding: 1rem;
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

  /* Responsive */
  @media (max-width: 720px) {
    .highlights-grid,
    .selection-summary,
    .form-grid {
      grid-template-columns: 1fr;
    }

    .section-head {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
