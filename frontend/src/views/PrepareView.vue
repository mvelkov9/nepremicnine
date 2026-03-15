<script setup>
  import { ref, onMounted, computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useDataStore } from '../stores/data'
  import api from '../composables/useApi'

  const { t } = useI18n()
  const dataStore = useDataStore()

  const loading = ref(false)
  const error = ref('')
  const result = ref(null)

  // ETN pair mode
  const etnMode = ref('bulk') // 'bulk' | 'single' | 'manual'
  const detectedPairs = ref([])
  const selectedPairs = ref([])
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

  onMounted(() => {
    dataStore.fetchDatasets()
    detectEtnPairs()
  })

  function detectEtnPairs() {
    const files = datasets.value
    const pairs = []
    const posliFiles = files.filter(
      (f) =>
        f.original_name.toLowerCase().includes('posli') ||
        f.original_name.toLowerCase().includes('posle'),
    )
    const delistavbFiles = files.filter(
      (f) =>
        f.original_name.toLowerCase().includes('deli') ||
        f.original_name.toLowerCase().includes('delistav'),
    )

    for (const posli of posliFiles) {
      // Extract year from filename
      const yearMatch = posli.original_name.match(/(\d{4})/)
      const year = yearMatch ? yearMatch[1] : ''

      // Find matching delistavb by year
      const match = delistavbFiles.find((d) => {
        const dYear = d.original_name.match(/(\d{4})/)
        return dYear && dYear[1] === year
      })

      if (match) {
        pairs.push({
          year,
          posli_path: posli.stored_path,
          posli_name: posli.original_name,
          delistavb_path: match.stored_path,
          delistavb_name: match.original_name,
          selected: true,
        })
      }
    }

    detectedPairs.value = pairs
    selectedPairs.value = pairs.filter((p) => p.selected)
  }

  async function prepareEtnBulk() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const pairs = detectedPairs.value
        .filter((p) => p.selected)
        .map((p) => ({
          posli_csv_path: p.posli_path,
          delistavb_csv_path: p.delistavb_path,
          year: p.year,
          label: p.year,
        }))

      if (!pairs.length) {
        error.value = t('prepare.noPairs')
        return
      }

      const { data } = await api.post('/api/data/prepare-etn-kpp-bulk', { pairs })
      result.value = data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
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
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
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
    } catch (e) {
      if (e instanceof SyntaxError) {
        error.value = t('prepare.invalidJson')
      } else {
        error.value = e.response?.data?.detail || e.message
      }
    } finally {
      loading.value = false
    }
  }

  function togglePair(index) {
    detectedPairs.value[index].selected = !detectedPairs.value[index].selected
  }

  function getDatasetPaths() {
    return datasets.value.map((d) => ({
      label: d.original_name,
      value: d.stored_path,
    }))
  }
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.prepare') }}</h1>

    <!-- Mode tabs -->
    <div class="card" style="margin-bottom: 1.5rem">
      <div class="mode-tabs">
        <button
          :class="['tab-btn', { active: etnMode === 'bulk' }]"
          @click="
            etnMode = 'bulk'
            detectEtnPairs()
          "
        >
          {{ t('prepare.autoEtn') }}
        </button>
        <button :class="['tab-btn', { active: etnMode === 'single' }]" @click="etnMode = 'single'">
          {{ t('prepare.singleEtn') }}
        </button>
        <button
          :class="['tab-btn', { active: etnMode === 'manual' }]"
          @click="etnMode = 'manual'"
        >
          {{ t('prepare.manualMapping') }}
        </button>
      </div>
    </div>

    <!-- Bulk ETN -->
    <div v-if="etnMode === 'bulk'" class="card">
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
                  <input
                    type="checkbox"
                    :checked="detectedPairs.every((p) => p.selected)"
                    @change="detectedPairs.forEach((p) => (p.selected = $event.target.checked))"
                  />
                </th>
                <th>{{ t('prepare.year') }}</th>
                <th>{{ t('prepare.posliFile') }}</th>
                <th>{{ t('prepare.delistavbFile') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(pair, i) in detectedPairs" :key="i">
                <td>
                  <input type="checkbox" v-model="pair.selected" @change="togglePair(i)" />
                </td>
                <td>
                  <span class="badge-blue">{{ pair.year }}</span>
                </td>
                <td>{{ pair.posli_name }}</td>
                <td>{{ pair.delistavb_name }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <button
          class="btn btn-primary"
          style="margin-top: 1rem"
          :disabled="loading || !detectedPairs.some((p) => p.selected)"
          @click="prepareEtnBulk"
        >
          {{ loading ? t('common.loading') : t('prepare.prepareButton') }}
        </button>
      </div>
    </div>

    <!-- Single ETN -->
    <div v-if="etnMode === 'single'" class="card">
      <div class="card-title">{{ t('prepare.singleEtn') }}</div>
      <p class="muted" style="margin-bottom: 1rem">{{ t('prepare.singleEtnDesc') }}</p>

      <div class="form-grid">
        <div>
          <label class="form-label">{{ t('prepare.posliFile') }}</label>
          <select v-model="singlePosli" class="form-input">
            <option value="">{{ t('prepare.selectFile') }}</option>
            <option v-for="opt in getDatasetPaths()" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div>
          <label class="form-label">{{ t('prepare.delistavbFile') }}</label>
          <select v-model="singleDelistavb" class="form-input">
            <option value="">{{ t('prepare.selectFile') }}</option>
            <option v-for="opt in getDatasetPaths()" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>

      <button
        class="btn btn-primary"
        style="margin-top: 1rem"
        :disabled="loading || !singlePosli || !singleDelistavb"
        @click="prepareEtnSingle"
      >
        {{ loading ? t('common.loading') : t('prepare.prepareButton') }}
      </button>
    </div>

    <!-- Manual mapping -->
    <div v-if="etnMode === 'manual'" class="card">
      <div class="card-title">{{ t('prepare.manualMapping') }}</div>
      <p class="muted" style="margin-bottom: 1rem">{{ t('prepare.manualDesc') }}</p>

      <div style="margin-bottom: 1rem">
        <label class="form-label">{{ t('prepare.sourceFile') }}</label>
        <select v-model="manualCsvPath" class="form-input">
          <option value="">{{ t('prepare.selectFile') }}</option>
          <option v-for="opt in getDatasetPaths()" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
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

      <button
        class="btn btn-primary"
        style="margin-top: 1rem"
        :disabled="loading || !manualCsvPath || !columnMap"
        @click="prepareManual"
      >
        {{ loading ? t('common.loading') : t('prepare.prepareButton') }}
      </button>
    </div>

    <!-- Error -->
    <p v-if="error" class="error-text" style="margin-top: 1rem">{{ error }}</p>

    <!-- Result -->
    <div v-if="result" class="card result-card" style="margin-top: 1.5rem">
      <div class="card-title">{{ t('prepare.result') }}</div>
      <div class="kpi-grid">
        <div class="kpi-card">
          <span class="kpi-label">{{ t('prepare.outputRows') }}</span>
          <span class="kpi-value">{{
            (result.rows || result.total_rows || 0).toLocaleString()
          }}</span>
        </div>
        <div v-if="result.columns" class="kpi-card">
          <span class="kpi-label">{{ t('prepare.outputColumns') }}</span>
          <span class="kpi-value">{{ result.columns?.length || 0 }}</span>
        </div>
        <div v-if="result.per_year" class="kpi-card">
          <span class="kpi-label">{{ t('prepare.yearsCovered') }}</span>
          <span class="kpi-value">{{ Object.keys(result.per_year).length }}</span>
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
              <td>{{ rows.toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .mode-tabs {
    display: flex;
    gap: 4px;
    border-bottom: 2px solid #e5e7eb;
    padding-bottom: 0;
  }
  .tab-btn {
    padding: 8px 20px;
    border: none;
    background: transparent;
    font-size: 14px;
    font-weight: 500;
    color: #6b7280;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition:
      color 0.2s,
      border-color 0.2s;
  }
  .tab-btn:hover {
    color: var(--color-primary, #3b82f6);
  }
  .tab-btn.active {
    color: var(--color-primary, #3b82f6);
    border-bottom-color: var(--color-primary, #3b82f6);
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
    resize: vertical;
  }
  .result-card {
    border-left: 4px solid #22c55e;
  }
</style>
