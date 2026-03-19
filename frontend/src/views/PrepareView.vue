<script setup lang="ts">
  import { ref, onMounted, computed, reactive } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import PageHeader from '../components/PageHeader.vue'
  import MetricCard from '../components/MetricCard.vue'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import api from '../composables/useApi'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatNumber } from '../utils/format'

  const { t } = useI18n()
  const dataStore = useDataStore()
  const modelStore = useModelStore()
  const router = useRouter()

  const loading = ref(false)
  const error = ref('')
  const result = ref(null)

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

  onMounted(async () => {
    await Promise.all([
      dataStore.fetchDatasets(),
      dataStore.fetchTrainingDataset(),
      modelStore.fetchActiveTraining(),
    ])
  })

  // --- Dataset role & year helpers (mirrors v1 logic) ---

  function datasetRole(item) {
    const text = `${item.original_name || ''} ${item.relative_path || ''}`.toLowerCase()
    if (text.includes('posli') || text.includes('posle')) return 'posli'
    if (text.includes('delistavb') || text.includes('deli_stavb')) return 'delistavb'
    if (text.includes('zemljisca') || text.includes('zemljisc')) return 'zemljisca'
    return 'other'
  }

  function datasetYear(item) {
    const match = `${item.original_name || ''} ${item.relative_path || ''}`.match(/(20\d{2})/)
    return match ? Number(match[1]) : null
  }

  // Track which years are selected (all selected by default)
  const deselectedYears = reactive(new Set())

  // Reactive computed: auto-detects ETN pairs grouped by year
  const detectedPairs = computed(() => {
    const byYear = new Map()
    const items = datasets.value || []
    for (const item of items) {
      const role = datasetRole(item)
      const year = datasetYear(item)
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

  async function prepareEtnBulk() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
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

      const { data } = await api.post('/api/data/prepare-etn-kpp-bulk', { pairs })
      result.value = data
      await dataStore.fetchTrainingDataset()
    } catch (e) {
      error.value = getPrepareErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function prepareEtnSingle() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const { data } = await api.post('/api/data/prepare-etn-kpp', {
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

  async function prepareManual() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const map = JSON.parse(columnMap.value)
      const { data } = await api.post('/api/data/prepare-train', {
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

  function togglePair(pair) {
    if (deselectedYears.has(pair.year)) {
      deselectedYears.delete(pair.year)
    } else {
      deselectedYears.add(pair.year)
    }
  }

  function toggleAll(checked) {
    if (checked) {
      deselectedYears.clear()
    } else {
      for (const p of detectedPairs.value) {
        deselectedYears.add(p.year)
      }
    }
  }

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
</script>

<template>
  <div class="prepare-page">
    <section class="card">
      <PageHeader
        :eyebrow="t('nav.prepare')"
        :title="t('prepare.title')"
        :description="trainingLocked ? t('prepare.trainingLockedHint') : t('layout.page.prepare')"
      />
    </section>

    <!-- Mode tabs -->
    <div class="card">
      <Tabs v-model:value="etnMode">
        <TabList>
          <Tab value="bulk">{{ t('prepare.autoEtn') }}</Tab>
          <Tab value="single">{{ t('prepare.singleEtn') }}</Tab>
          <Tab value="manual">{{ t('prepare.manualMapping') }}</Tab>
        </TabList>

        <TabPanels>
          <!-- Bulk ETN -->
          <TabPanel value="bulk">
            <div class="card-title">{{ t('prepare.autoEtn') }}</div>
            <p class="muted mb-4">{{ t('prepare.autoEtnDesc') }}</p>

            <div v-if="!detectedPairs.length" class="muted">
              {{ t('prepare.noPairsDetected') }}
            </div>

            <div v-else>
              <DataTable :value="detectedPairs" striped-rows size="small">
                <Column header-style="width: 3rem">
                  <template #header>
                    <Checkbox
                      binary
                      :model-value="detectedPairs.every((p) => isSelected(p.year))"
                      @update:model-value="toggleAll($event)"
                    />
                  </template>
                  <template #body="{ data: pair }">
                    <Checkbox
                      binary
                      :model-value="isSelected(pair.year)"
                      @update:model-value="togglePair(pair)"
                    />
                  </template>
                </Column>
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
          </TabPanel>

          <!-- Single ETN -->
          <TabPanel value="single">
            <div class="card-title">{{ t('prepare.singleEtn') }}</div>
            <p class="muted mb-4">{{ t('prepare.singleEtnDesc') }}</p>

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

            <Button
              class="mt-4"
              icon="pi pi-cog"
              :loading="loading"
              :disabled="loading || trainingLocked || !singlePosli || !singleDelistavb"
              :label="loading ? t('common.loading') : t('prepare.prepareButton')"
              @click="prepareEtnSingle"
            />
          </TabPanel>

          <!-- Manual mapping -->
          <TabPanel value="manual">
            <div class="card-title">{{ t('prepare.manualMapping') }}</div>
            <p class="muted mb-4">{{ t('prepare.manualDesc') }}</p>

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
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>

    <!-- Error -->
    <p v-if="error" class="error-text mt-4">{{ error }}</p>

    <!-- Result -->
    <div v-if="result" class="card result-card mt-6">
      <div class="card-title">{{ t('prepare.result') }}</div>

      <div class="flex flex-wrap gap-4">
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

      <div v-if="result.training_dataset" class="selected-source-card mt-4">
        <span class="eyebrow">{{ t('prepare.readyForModel') }}</span>
        <strong>{{ result.training_dataset.relative_path }}</strong>
        <p class="muted">{{ fmt(result.training_dataset.rows) }} {{ t('data.rows') }}</p>
        <div class="mt-3">
          <Button :label="t('prepare.openModel')" @click="openModelView" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .prepare-page {
    display: grid;
    gap: 1rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
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

  @media (max-width: 720px) {
    .form-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
