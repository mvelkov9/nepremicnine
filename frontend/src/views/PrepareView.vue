<script setup>
  import { ref, onMounted, computed, reactive } from 'vue'
  import { useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Checkbox from 'primevue/checkbox'
  import Select from 'primevue/select'
  import PageHeader from '../components/PageHeader.vue'
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
    <div class="card mode-shell">
      <div class="mode-tabs" role="tablist">
        <button
          :class="['tab-btn', { active: etnMode === 'bulk' }]"
          role="tab"
          :aria-selected="etnMode === 'bulk'"
          @click="etnMode = 'bulk'"
        >
          {{ t('prepare.autoEtn') }}
        </button>
        <button
          :class="['tab-btn', { active: etnMode === 'single' }]"
          role="tab"
          :aria-selected="etnMode === 'single'"
          @click="etnMode = 'single'"
        >
          {{ t('prepare.singleEtn') }}
        </button>
        <button
          :class="['tab-btn', { active: etnMode === 'manual' }]"
          role="tab"
          :aria-selected="etnMode === 'manual'"
          @click="etnMode = 'manual'"
        >
          {{ t('prepare.manualMapping') }}
        </button>
      </div>
    </div>

    <!-- Bulk ETN -->
    <div v-if="etnMode === 'bulk'" class="card" role="tabpanel">
      <div class="card-title">{{ t('prepare.autoEtn') }}</div>
      <p class="muted" style="margin-bottom: 1rem">{{ t('prepare.autoEtnDesc') }}</p>

      <div v-if="!detectedPairs.length" class="muted">
        {{ t('prepare.noPairsDetected') }}
      </div>

      <div v-else>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 40px">
                  <Checkbox
                    binary
                    :model-value="detectedPairs.every((p) => isSelected(p.year))"
                    @update:model-value="toggleAll($event)"
                  />
                </th>
                <th>{{ t('prepare.year') }}</th>
                <th>{{ t('prepare.posliFile') }}</th>
                <th>{{ t('prepare.delistavbFile') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="pair in detectedPairs" :key="pair.year">
                <td>
                  <Checkbox
                    binary
                    :model-value="isSelected(pair.year)"
                    @update:model-value="togglePair(pair)"
                  />
                </td>
                <td>
                  <span class="badge-blue">{{ pair.year }}</span>
                </td>
                <td>{{ pair.posli.original_name }}</td>
                <td>{{ pair.delistavb.original_name }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <Button
          class="prepare-btn"
          icon="pi pi-cog"
          :loading="loading"
          :disabled="loading || trainingLocked || !selectedPairs().length"
          :label="loading ? t('common.loading') : t('prepare.prepareButton')"
          @click="prepareEtnBulk"
        />
      </div>
    </div>

    <!-- Single ETN -->
    <div v-if="etnMode === 'single'" class="card" role="tabpanel">
      <div class="card-title">{{ t('prepare.singleEtn') }}</div>
      <p class="muted" style="margin-bottom: 1rem">{{ t('prepare.singleEtnDesc') }}</p>

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
        class="prepare-btn"
        icon="pi pi-cog"
        :loading="loading"
        :disabled="loading || trainingLocked || !singlePosli || !singleDelistavb"
        :label="loading ? t('common.loading') : t('prepare.prepareButton')"
        @click="prepareEtnSingle"
      />
    </div>

    <!-- Manual mapping -->
    <div v-if="etnMode === 'manual'" class="card" role="tabpanel">
      <div class="card-title">{{ t('prepare.manualMapping') }}</div>
      <p class="muted" style="margin-bottom: 1rem">{{ t('prepare.manualDesc') }}</p>

      <div style="margin-bottom: 1rem">
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
        <textarea
          v-model="columnMap"
          class="form-input code-textarea"
          rows="8"
          :placeholder="columnMapPlaceholder"
        ></textarea>
      </div>

      <Button
        class="prepare-btn"
        icon="pi pi-cog"
        :loading="loading"
        :disabled="loading || trainingLocked || !manualCsvPath || !columnMap"
        :label="loading ? t('common.loading') : t('prepare.prepareButton')"
        @click="prepareManual"
      />
    </div>

    <!-- Error -->
    <p v-if="error" class="error-text" style="margin-top: 1rem">{{ error }}</p>

    <!-- Result -->
    <div v-if="result" class="card result-card" style="margin-top: 1.5rem">
      <div class="card-title">{{ t('prepare.result') }}</div>
      <div class="kpi-grid">
        <div class="kpi-card">
          <span class="kpi-label">{{ t('prepare.outputRows') }}</span>
          <span class="kpi-value">{{ fmt(result.rows || result.total_rows || 0) }}</span>
        </div>
        <div v-if="result.columns" class="kpi-card">
          <span class="kpi-label">{{ t('prepare.outputColumns') }}</span>
          <span class="kpi-value">{{ fmt(result.columns?.length || 0) }}</span>
        </div>
        <div v-if="result.per_year" class="kpi-card">
          <span class="kpi-label">{{ t('prepare.yearsCovered') }}</span>
          <span class="kpi-value">{{ fmt(Object.keys(result.per_year).length) }}</span>
        </div>
      </div>

      <div v-if="result.per_year" class="table-wrap" style="margin-top: 1rem">
        <table>
          <thead>
            <tr>
              <th>{{ t('prepare.year') }}</th>
              <th>{{ t('data.rows') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(rows, year) in result.per_year" :key="year">
              <td>
                <span class="badge-blue">{{ year }}</span>
              </td>
              <td>{{ fmt(rows) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="result.reports?.length" class="table-wrap" style="margin-top: 1rem">
        <table>
          <thead>
            <tr>
              <th>{{ t('prepare.year') }}</th>
              <th>{{ t('prepare.reportStatus') }}</th>
              <th>{{ t('data.rows') }}</th>
              <th>{{ t('prepare.reportDetail') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="report in result.reports" :key="report.label">
              <td>
                <span class="badge-blue">{{ report.label }}</span>
              </td>
              <td>
                <span :class="report.status === 'ok' ? 'badge badge-green' : 'badge badge-red'">
                  {{ report.status }}
                </span>
              </td>
              <td>{{ fmt(report.rows || 0) }}</td>
              <td class="muted">{{ getReportDetail(report) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="result.training_dataset" class="selected-source-card" style="margin-top: 1rem">
        <span class="eyebrow">{{ t('prepare.readyForModel') }}</span>
        <strong>{{ result.training_dataset.relative_path }}</strong>
        <p class="muted">{{ fmt(result.training_dataset.rows) }} {{ t('data.rows') }}</p>
        <div class="actions">
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

  .mode-shell {
    margin-bottom: 0;
  }

  .mode-tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0;
  }
  .tab-btn {
    padding: 8px 20px;
    border: none;
    background: transparent;
    font-size: 14px;
    font-weight: 500;
    color: var(--text-soft);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition:
      color 0.2s,
      border-color 0.2s;
  }
  .tab-btn:hover {
    color: var(--primary);
  }
  .tab-btn.active {
    color: var(--primary);
    border-bottom-color: var(--primary);
  }
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
  .prepare-btn {
    margin-top: 1rem;
  }
  .code-textarea {
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
    resize: vertical;
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
