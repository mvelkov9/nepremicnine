<script setup>
  import { ref, onMounted, computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import api from '../composables/useApi'
  import EmptyState from '../components/EmptyState.vue'
  import { useExport } from '../composables/useExport'

  const { t } = useI18n()
  const { exportToCSV } = useExport()

  const form = ref({
    size_m2: null,
    rooms: null,
    year_built: null,
    floor: null,
    latitude: null,
    longitude: null,
    municipality: '',
    property_type: 'stanovanje',
    uporabna_povrsina: null,
    lega_v_stavbi: '',
    novogradnja: 0,
    has_garaza: 0,
    has_klet: 0,
    has_shramba: 0,
    has_terasa: 0,
    stavba_je_dokoncana: 1,
    ddv_vkljucen: 0,
  })

  const propertyTypes = [
    'stanovanje',
    'hisa',
    'poslovni_prostor',
    'industrijski',
    'turisticni',
    'gostinstvo',
    'garaza',
    'kmetijsko',
  ]

  const legaOptions = ['pritlicje', 'nadstropje', 'klet', 'unknown']

  // Municipality autocomplete
  const municipalityQuery = ref('')
  const allMunicipalities = ref([])
  const showSuggestions = ref(false)

  const filteredMunicipalities = computed(() => {
    if (!municipalityQuery.value) return []
    const q = municipalityQuery.value.toLowerCase()
    return allMunicipalities.value.filter((m) => m.toLowerCase().includes(q)).slice(0, 10)
  })

  async function fetchMunicipalities() {
    try {
      const { data } = await api.get('/api/municipalities')
      allMunicipalities.value = data.map((m) => m.municipality)
    } catch {
      allMunicipalities.value = []
    }
  }

  function selectMunicipality(name) {
    form.value.municipality = name
    municipalityQuery.value = name
    showSuggestions.value = false
  }

  const highlightedIndex = ref(-1)

  function onMunicipalityInput() {
    form.value.municipality = municipalityQuery.value
    showSuggestions.value = true
    highlightedIndex.value = -1
  }

  function onMunicipalityKeydown(e) {
    const list = filteredMunicipalities.value
    if (!showSuggestions.value || !list.length) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      highlightedIndex.value = (highlightedIndex.value + 1) % list.length
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      highlightedIndex.value = (highlightedIndex.value - 1 + list.length) % list.length
    } else if (e.key === 'Enter' && highlightedIndex.value >= 0) {
      e.preventDefault()
      selectMunicipality(list[highlightedIndex.value])
    }
  }

  const result = ref(null)
  const history = ref([])
  const loading = ref(false)
  const error = ref(null)
  const formErrors = ref({})

  function validateForm() {
    const errors = {}
    if (!form.value.size_m2 || form.value.size_m2 <= 0) {
      errors.size_m2 = t('validation.minSize')
    }
    formErrors.value = errors
    return Object.keys(errors).length === 0
  }

  async function predict() {
    if (!validateForm()) return
    loading.value = true
    error.value = null
    result.value = null
    try {
      const payload = {}
      for (const [key, val] of Object.entries(form.value)) {
        if (val !== null && val !== '' && val !== undefined) {
          payload[key] = val
        }
      }
      const { data } = await api.post('/api/predict', payload)
      result.value = data
      await fetchHistory()
    } catch (e) {
      error.value = e.response?.data?.detail || e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchHistory() {
    try {
      const { data } = await api.get('/api/predict/history?limit=20')
      history.value = data
    } catch {
      history.value = []
    }
  }

  onMounted(() => {
    fetchHistory()
    fetchMunicipalities()
  })
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('nav.prediction') }}</h1>

    <div class="card" style="margin-bottom: 1.5rem">
      <h2>{{ t('predict.title') }}</h2>
      <form @submit.prevent="predict" class="predict-form">
        <div class="form-grid">
          <div>
            <label class="form-label">{{ t('predict.size') }} *</label>
            <input
              v-model.number="form.size_m2"
              type="number"
              step="0.1"
              min="1"
              class="form-input"
              :class="{ 'input-error': formErrors.size_m2 }"
              required
              @input="formErrors.size_m2 = null"
            />
            <span v-if="formErrors.size_m2" class="field-error">{{ formErrors.size_m2 }}</span>
          </div>
          <div>
            <label class="form-label">{{ t('predict.rooms') }}</label>
            <input
              v-model.number="form.rooms"
              type="number"
              step="0.5"
              min="0"
              class="form-input"
            />
          </div>
          <div>
            <label class="form-label">{{ t('predict.yearBuilt') }}</label>
            <input
              v-model.number="form.year_built"
              type="number"
              min="1800"
              max="2030"
              class="form-input"
            />
          </div>
          <div>
            <label class="form-label">{{ t('predict.floor') }}</label>
            <input v-model.number="form.floor" type="number" min="-2" max="50" class="form-input" />
          </div>
          <div>
            <label class="form-label">{{ t('predict.latitude') }}</label>
            <input
              v-model.number="form.latitude"
              type="number"
              step="0.0001"
              class="form-input"
              placeholder="46.05"
            />
          </div>
          <div>
            <label class="form-label">{{ t('predict.longitude') }}</label>
            <input
              v-model.number="form.longitude"
              type="number"
              step="0.0001"
              class="form-input"
              placeholder="14.50"
            />
          </div>
          <div class="municipality-field">
            <label class="form-label">{{ t('predict.municipality') }}</label>
            <input
              v-model="municipalityQuery"
              type="text"
              class="form-input"
              role="combobox"
              :aria-expanded="showSuggestions && filteredMunicipalities.length > 0"
              aria-autocomplete="list"
              aria-controls="municipality-listbox"
              :placeholder="t('predict.municipalityPlaceholder')"
              @input="onMunicipalityInput"
              @keydown="onMunicipalityKeydown"
              @focus="showSuggestions = true"
              @blur="setTimeout(() => (showSuggestions = false), 200)"
            />
            <ul
              v-if="showSuggestions && filteredMunicipalities.length"
              id="municipality-listbox"
              role="listbox"
              class="suggestions"
            >
              <li
                v-for="(m, idx) in filteredMunicipalities"
                :key="m"
                role="option"
                :aria-selected="idx === highlightedIndex"
                :class="{ highlighted: idx === highlightedIndex }"
                @mousedown.prevent="selectMunicipality(m)"
              >
                {{ m }}
              </li>
            </ul>
          </div>
          <div>
            <label class="form-label">{{ t('predict.propertyType') }}</label>
            <select v-model="form.property_type" class="form-input">
              <option v-for="pt in propertyTypes" :key="pt" :value="pt">{{ pt }}</option>
            </select>
          </div>
          <div>
            <label class="form-label">{{ t('predict.uporabnaPovrsina') }}</label>
            <input
              v-model.number="form.uporabna_povrsina"
              type="number"
              step="0.1"
              min="0"
              class="form-input"
            />
          </div>
          <div>
            <label class="form-label">{{ t('predict.legaVStavbi') }}</label>
            <select v-model="form.lega_v_stavbi" class="form-input">
              <option value="">—</option>
              <option v-for="l in legaOptions" :key="l" :value="l">
                {{ t(`predict.lega.${l}`) }}
              </option>
            </select>
          </div>
        </div>

        <!-- Property feature checkboxes -->
        <div class="checkbox-grid">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model.number="form.novogradnja"
              :true-value="1"
              :false-value="0"
            />
            {{ t('predict.novogradnja') }}
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model.number="form.has_garaza"
              :true-value="1"
              :false-value="0"
            />
            {{ t('predict.hasGaraza') }}
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model.number="form.has_klet"
              :true-value="1"
              :false-value="0"
            />
            {{ t('predict.hasKlet') }}
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model.number="form.has_shramba"
              :true-value="1"
              :false-value="0"
            />
            {{ t('predict.hasShramba') }}
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model.number="form.has_terasa"
              :true-value="1"
              :false-value="0"
            />
            {{ t('predict.hasTerasa') }}
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model.number="form.stavba_je_dokoncana"
              :true-value="1"
              :false-value="0"
            />
            {{ t('predict.stavbaDokoncana') }}
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model.number="form.ddv_vkljucen"
              :true-value="1"
              :false-value="0"
            />
            {{ t('predict.ddvVkljucen') }}
          </label>
        </div>

        <button
          type="submit"
          class="btn btn-primary"
          :disabled="loading || !form.size_m2"
          style="margin-top: 1rem"
        >
          {{ loading ? t('common.loading') : t('predict.predictButton') }}
        </button>
      </form>

      <p v-if="error" class="error-text" style="margin-top: 1rem">{{ error }}</p>
    </div>

    <!-- Result -->
    <div v-if="result" class="card result-card" style="margin-bottom: 1.5rem">
      <h2>{{ t('predict.result') }}</h2>
      <div class="predicted-price">
        €{{ Math.round(result.predicted_price_eur).toLocaleString() }}
      </div>
      <p class="muted">{{ t('predict.modelUsed') }}: {{ result.model_used }}</p>

      <!-- Show features used -->
      <div v-if="result.features_used" class="features-used">
        <h3>{{ t('predict.featuresUsed') }}</h3>
        <div class="features-grid">
          <div v-for="(val, key) in result.features_used" :key="key" class="feature-item">
            <span class="feature-key">{{ key }}</span>
            <span class="feature-val">{{
              typeof val === 'number'
                ? val.toLocaleString('sl-SI', { maximumFractionDigits: 2 })
                : val
            }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- History -->
    <div class="card">
      <div
        style="
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 0.5rem;
          margin-bottom: 0.5rem;
        "
      >
        <h2 style="margin: 0">{{ t('predict.history') }}</h2>
        <button
          v-if="history.length"
          class="btn btn-secondary"
          @click="exportToCSV(history, 'predictions.csv')"
        >
          {{ t('predict.exportHistory') }}
        </button>
      </div>
      <EmptyState v-if="!history.length" icon="📋" :message="t('empty.noPredictions')" />
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('predict.date') }}</th>
              <th>{{ t('predict.size') }}</th>
              <th>{{ t('predict.propertyType') }}</th>
              <th>{{ t('predict.predictedPrice') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in history" :key="item.id">
              <td>{{ new Date(item.created_at).toLocaleString() }}</td>
              <td>{{ item.payload.size_m2 }} m²</td>
              <td>{{ item.payload.property_type || '-' }}</td>
              <td class="price">€{{ Math.round(item.predicted_price_eur).toLocaleString() }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .predict-form .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
  }
  .municipality-field {
    position: relative;
  }
  .suggestions {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--card-bg, #fff);
    border: 1px solid var(--border, #d1d5db);
    border-radius: 6px;
    max-height: 200px;
    overflow-y: auto;
    z-index: 10;
    list-style: none;
    margin: 2px 0 0;
    padding: 0;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
  .suggestions li {
    padding: 8px 12px;
    cursor: pointer;
    font-size: 0.875rem;
  }
  .suggestions li:hover,
  .suggestions li.highlighted {
    background: var(--card-bg-muted, #eff6ff);
  }
  .checkbox-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-top: 1rem;
    padding: 1rem;
    background: var(--card-bg-muted, #f9fafb);
    border-radius: 8px;
    border: 1px solid var(--border, #e5e7eb);
  }
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.875rem;
    cursor: pointer;
    white-space: nowrap;
  }
  .checkbox-label input[type='checkbox'] {
    width: 16px;
    height: 16px;
    accent-color: var(--color-primary, #3b82f6);
  }
  .result-card {
    text-align: center;
  }
  .predicted-price {
    font-size: 2.5rem;
    font-weight: 700;
    color: var(--color-primary);
    margin: 1rem 0;
  }
  .price {
    font-weight: 600;
    color: var(--color-primary);
  }
  .features-used {
    margin-top: 1rem;
    text-align: left;
  }
  .features-used h3 {
    font-size: 0.875rem;
    color: var(--text-muted, #6b7280);
    margin-bottom: 0.5rem;
  }
  .features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 4px;
  }
  .feature-item {
    display: flex;
    justify-content: space-between;
    padding: 4px 8px;
    font-size: 0.8rem;
    background: var(--card-bg-muted, #f3f4f6);
    border-radius: 4px;
  }
  .feature-key {
    color: var(--text-muted, #6b7280);
  }
  .feature-val {
    font-weight: 600;
  }
</style>
