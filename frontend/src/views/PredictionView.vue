<script setup>
  import { computed, onMounted, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import api from '../composables/useApi'
  import AppIcon from '../components/AppIcon.vue'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import { useExport } from '../composables/useExport'
  import { useStatsStore } from '../stores/stats'
  import { getApiErrorMessage } from '../utils/apiError'
  import { municipalitySlug } from '../utils/municipality'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()
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
  const municipalityQuery = ref('')
  const allMunicipalities = ref([])
  const showSuggestions = ref(false)
  const highlightedIndex = ref(-1)
  const result = ref(null)
  const history = ref([])
  const loading = ref(false)
  const contextLoading = ref(false)
  const error = ref('')
  const formErrors = ref({})

  const filteredMunicipalities = computed(() => {
    if (!municipalityQuery.value) return []
    const query = municipalityQuery.value.toLowerCase()
    return allMunicipalities.value.filter((item) => item.toLowerCase().includes(query)).slice(0, 10)
  })

  const municipalityContext = computed(() => stats.municipalityDetail)
  const comparables = computed(() => stats.comparables)
  const comparableRows = computed(() => comparables.value?.items || [])
  const comparablesCountLabel = computed(
    () => `${comparables.value?.summary?.count || 0} ${t('dashboard.transactions')}`,
  )
  const effectiveSize = computed(() => form.value.uporabna_povrsina || form.value.size_m2)

  function fmt(value, decimals = 0) {
    if (value == null) return '—'
    return Number(value).toLocaleString('sl-SI', { maximumFractionDigits: decimals })
  }

  async function fetchMunicipalities() {
    try {
      const { data } = await api.get('/api/municipalities')
      allMunicipalities.value = data.map((item) => item.municipality)
    } catch {
      allMunicipalities.value = []
    }
  }

  async function fetchHistory() {
    try {
      const { data } = await api.get('/api/predict/history', { params: { per_page: 12 } })
      history.value = data.items || []
    } catch {
      history.value = []
    }
  }

  function selectMunicipality(name) {
    form.value.municipality = name
    municipalityQuery.value = name
    showSuggestions.value = false
    highlightedIndex.value = -1
  }

  function onMunicipalityInput() {
    form.value.municipality = municipalityQuery.value
    showSuggestions.value = true
    highlightedIndex.value = -1
  }

  function onMunicipalityKeydown(event) {
    const list = filteredMunicipalities.value
    if (!showSuggestions.value || !list.length) return

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      highlightedIndex.value = (highlightedIndex.value + 1) % list.length
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      highlightedIndex.value = (highlightedIndex.value - 1 + list.length) % list.length
    } else if (event.key === 'Enter' && highlightedIndex.value >= 0) {
      event.preventDefault()
      selectMunicipality(list[highlightedIndex.value])
    }
  }

  function validateForm() {
    const errors = {}
    if (!form.value.size_m2 || form.value.size_m2 <= 0) {
      errors.size_m2 = t('validation.minSize')
    }
    if (!form.value.municipality?.trim()) {
      errors.municipality = t('validation.required')
    }
    formErrors.value = errors
    return Object.keys(errors).length === 0
  }

  async function loadContext(estimatedPrice = null) {
    if (!form.value.municipality || !form.value.property_type || !effectiveSize.value) {
      stats.resetComparables()
      stats.resetMunicipalityDetail()
      return
    }

    contextLoading.value = true
    try {
      await Promise.all([
        stats.fetchMunicipalityDetail(municipalitySlug(form.value.municipality)),
        stats.fetchComparables({
          municipality: form.value.municipality,
          property_type: form.value.property_type,
          size_m2: effectiveSize.value,
          year_built: form.value.year_built || undefined,
          price_eur: estimatedPrice || undefined,
          limit: 8,
        }),
      ])
    } catch {
      stats.resetComparables()
      stats.resetMunicipalityDetail()
    } finally {
      contextLoading.value = false
    }
  }

  async function predict() {
    if (!validateForm()) return

    loading.value = true
    error.value = ''
    result.value = null

    try {
      const payload = {}
      for (const [key, value] of Object.entries(form.value)) {
        if (value !== null && value !== '' && value !== undefined) {
          payload[key] = value
        }
      }

      const { data } = await api.post('/api/predict', payload)
      result.value = data
      await Promise.all([fetchHistory(), loadContext(data.predicted_price_eur)])
    } catch (err) {
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  function applyRouteQuery(query) {
    const numericFields = ['size_m2', 'year_built', 'price_eur']

    for (const field of ['municipality', 'property_type']) {
      if (query[field]) {
        form.value[field] = String(query[field])
      }
    }

    for (const field of numericFields) {
      if (query[field]) {
        const numericValue = Number(query[field])
        if (!Number.isNaN(numericValue)) {
          if (field === 'price_eur') {
            result.value = result.value || {
              predicted_price_eur: numericValue,
              model_used: 'prefill',
              features_used: {},
            }
          } else {
            form.value[field] = numericValue
          }
        }
      }
    }

    municipalityQuery.value = form.value.municipality || ''
  }

  function exportHistoryRows() {
    exportToCSV(history.value, 'prediction-history.csv')
  }

  function openMunicipality() {
    if (!municipalityContext.value?.slug) return
    router.push(`/obcine/${municipalityContext.value.slug}`)
  }

  function reuseComparable(item) {
    router.push({
      name: 'prediction',
      query: {
        municipality: item.municipality,
        property_type: item.property_type || form.value.property_type,
        size_m2: item.size_m2 || '',
        year_built: item.year_built || '',
        price_eur: item.price_eur || '',
      },
    })
  }

  watch(
    () => route.query,
    (query) => {
      applyRouteQuery(query)
    },
    { immediate: true },
  )

  onMounted(async () => {
    await Promise.all([fetchHistory(), fetchMunicipalities()])
    if (form.value.municipality && effectiveSize.value) {
      await loadContext(result.value?.predicted_price_eur || null)
    }
  })
</script>

<template>
  <div class="prediction-page">
    <section class="prediction-shell">
      <article class="panel input-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">{{ t('predict.title') }}</span>
            <h1>{{ t('predict.avmTitle') }}</h1>
            <p>{{ t('predict.avmBody') }}</p>
          </div>
        </div>

        <form class="predict-form" @submit.prevent="predict">
          <div class="form-section">
            <h2>{{ t('predict.subjectBasics') }}</h2>
            <div class="form-grid">
              <label class="field">
                <span>{{ t('predict.size') }} *</span>
                <input
                  v-model.number="form.size_m2"
                  type="number"
                  min="1"
                  step="0.1"
                  class="form-input"
                  :class="{ 'input-error': formErrors.size_m2 }"
                  @input="formErrors.size_m2 = null"
                />
                <small v-if="formErrors.size_m2" class="field-error">{{
                  formErrors.size_m2
                }}</small>
              </label>

              <label class="field">
                <span>{{ t('predict.uporabnaPovrsina') }}</span>
                <input
                  v-model.number="form.uporabna_povrsina"
                  type="number"
                  min="0"
                  step="0.1"
                  class="form-input"
                />
              </label>

              <label class="field">
                <span>{{ t('predict.rooms') }}</span>
                <input
                  v-model.number="form.rooms"
                  type="number"
                  min="0"
                  step="0.5"
                  class="form-input"
                />
              </label>

              <label class="field">
                <span>{{ t('predict.yearBuilt') }}</span>
                <input
                  v-model.number="form.year_built"
                  type="number"
                  min="1800"
                  max="2030"
                  class="form-input"
                />
              </label>

              <label class="field">
                <span>{{ t('predict.floor') }}</span>
                <input
                  v-model.number="form.floor"
                  type="number"
                  min="-2"
                  max="60"
                  class="form-input"
                />
              </label>

              <label class="field">
                <span>{{ t('predict.propertyType') }}</span>
                <select v-model="form.property_type" class="form-input">
                  <option v-for="item in propertyTypes" :key="item" :value="item">
                    {{ item }}
                  </option>
                </select>
              </label>
            </div>
          </div>

          <div class="form-section">
            <h2>{{ t('predict.locationContext') }}</h2>
            <div class="form-grid">
              <label class="field municipality-field">
                <span>{{ t('predict.municipality') }} *</span>
                <input
                  v-model="municipalityQuery"
                  type="text"
                  class="form-input"
                  :class="{ 'input-error': formErrors.municipality }"
                  role="combobox"
                  :aria-expanded="showSuggestions && filteredMunicipalities.length > 0"
                  aria-autocomplete="list"
                  aria-controls="municipality-listbox"
                  :placeholder="t('predict.municipalityPlaceholder')"
                  @input="onMunicipalityInput"
                  @keydown="onMunicipalityKeydown"
                  @focus="showSuggestions = true"
                  @blur="setTimeout(() => (showSuggestions = false), 180)"
                />
                <small v-if="formErrors.municipality" class="field-error">{{
                  formErrors.municipality
                }}</small>
                <ul
                  v-if="showSuggestions && filteredMunicipalities.length"
                  id="municipality-listbox"
                  class="suggestions"
                >
                  <li
                    v-for="(item, index) in filteredMunicipalities"
                    :key="item"
                    :class="{ highlighted: index === highlightedIndex }"
                    @mousedown.prevent="selectMunicipality(item)"
                  >
                    {{ item }}
                  </li>
                </ul>
              </label>

              <label class="field">
                <span>{{ t('predict.latitude') }}</span>
                <input
                  v-model.number="form.latitude"
                  type="number"
                  step="0.0001"
                  class="form-input"
                />
              </label>

              <label class="field">
                <span>{{ t('predict.longitude') }}</span>
                <input
                  v-model.number="form.longitude"
                  type="number"
                  step="0.0001"
                  class="form-input"
                />
              </label>

              <label class="field">
                <span>{{ t('predict.legaVStavbi') }}</span>
                <select v-model="form.lega_v_stavbi" class="form-input">
                  <option value="">{{ t('common.noData') }}</option>
                  <option v-for="option in legaOptions" :key="option" :value="option">
                    {{ t(`predict.lega.${option}`) }}
                  </option>
                </select>
              </label>
            </div>
          </div>

          <div class="form-section">
            <h2>{{ t('predict.buildingFlags') }}</h2>
            <div class="toggle-grid">
              <label class="toggle-chip">
                <input
                  v-model="form.novogradnja"
                  type="checkbox"
                  :true-value="1"
                  :false-value="0"
                />
                <span>{{ t('predict.novogradnja') }}</span>
              </label>
              <label class="toggle-chip">
                <input v-model="form.has_garaza" type="checkbox" :true-value="1" :false-value="0" />
                <span>{{ t('predict.hasGaraza') }}</span>
              </label>
              <label class="toggle-chip">
                <input v-model="form.has_klet" type="checkbox" :true-value="1" :false-value="0" />
                <span>{{ t('predict.hasKlet') }}</span>
              </label>
              <label class="toggle-chip">
                <input
                  v-model="form.has_shramba"
                  type="checkbox"
                  :true-value="1"
                  :false-value="0"
                />
                <span>{{ t('predict.hasShramba') }}</span>
              </label>
              <label class="toggle-chip">
                <input v-model="form.has_terasa" type="checkbox" :true-value="1" :false-value="0" />
                <span>{{ t('predict.hasTerasa') }}</span>
              </label>
              <label class="toggle-chip">
                <input
                  v-model="form.stavba_je_dokoncana"
                  type="checkbox"
                  :true-value="1"
                  :false-value="0"
                />
                <span>{{ t('predict.stavbaDokoncana') }}</span>
              </label>
              <label class="toggle-chip">
                <input
                  v-model="form.ddv_vkljucen"
                  type="checkbox"
                  :true-value="1"
                  :false-value="0"
                />
                <span>{{ t('predict.ddvVkljucen') }}</span>
              </label>
            </div>
          </div>

          <p v-if="error" class="error-text">{{ error }}</p>

          <div class="form-actions">
            <button class="submit-btn" type="submit" :disabled="loading">
              <AppIcon name="prediction" :size="16" />
              <span>{{ loading ? t('common.loading') : t('predict.predictButton') }}</span>
            </button>
          </div>
        </form>
      </article>

      <article class="panel story-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow">{{ t('predict.result') }}</span>
            <h2>{{ t('predict.valuationStory') }}</h2>
            <p>{{ t('predict.valuationBody') }}</p>
          </div>
        </div>

        <div v-if="loading || contextLoading" class="inline-loading">
          <LoadingSpinner :label="t('common.loading')" />
        </div>

        <template v-else-if="result">
          <section class="estimate-card">
            <span>{{ t('predict.predictedPrice') }}</span>
            <strong>{{ fmt(result.predicted_price_eur) }} €</strong>
            <p>{{ t('predict.modelUsed') }}: {{ result.model_used }}</p>
          </section>

          <section class="story-block">
            <div class="story-head">
              <h3>{{ t('predict.featuresUsed') }}</h3>
              <button
                class="ghost-link"
                type="button"
                @click="loadContext(result.predicted_price_eur)"
              >
                {{ t('common.retry') }}
              </button>
            </div>
            <div class="chip-grid">
              <span v-for="(value, key) in result.features_used" :key="key" class="data-chip">
                {{ key }}: {{ value }}
              </span>
            </div>
          </section>

          <section v-if="municipalityContext" class="story-block context-card">
            <div class="story-head">
              <h3>{{ t('predict.marketContext') }}</h3>
              <button class="ghost-link" type="button" @click="openMunicipality">
                {{ t('predict.openMunicipality') }}
              </button>
            </div>
            <div class="context-metrics">
              <article>
                <span>{{ t('dashboard.medianPrice') }}</span>
                <strong>{{ fmt(municipalityContext.overview?.median_price) }} €</strong>
              </article>
              <article>
                <span>{{ t('dashboard.pricePerM2') }}</span>
                <strong>{{ fmt(municipalityContext.overview?.median_price_per_m2) }} €</strong>
              </article>
              <article>
                <span>{{ t('dashboard.transactions') }}</span>
                <strong>{{ fmt(municipalityContext.overview?.count) }}</strong>
              </article>
            </div>
          </section>

          <section class="story-block">
            <div class="story-head">
              <h3>{{ t('predict.comparablesTitle') }}</h3>
              <small>{{ comparablesCountLabel }}</small>
            </div>

            <div v-if="comparableRows.length" class="comparables-list">
              <article
                v-for="item in comparableRows"
                :key="`${item.slug}-${item.price_eur}-${item.size_m2}`"
                class="comparable-card"
              >
                <div class="comparable-head">
                  <strong>{{ item.municipality }}</strong>
                  <span>{{ item.year || '—' }}</span>
                </div>
                <p>
                  {{ item.property_type || '—' }} · {{ fmt(item.size_m2, 1) }} m² ·
                  {{ fmt(item.price_per_m2) }} €/m²
                </p>
                <div class="comparable-foot">
                  <strong>{{ fmt(item.price_eur) }} €</strong>
                  <small>{{ t('predict.similarityLabel') }} {{ item.similarity_score }}</small>
                </div>
                <button class="mini-btn" type="button" @click="reuseComparable(item)">
                  {{ t('predict.reuseComparable') }}
                </button>
              </article>
            </div>
            <EmptyState v-else icon="📊" :message="t('predict.noComparables')" />
          </section>
        </template>

        <EmptyState v-else icon="🏠" :message="t('predict.emptyState')" />

        <section class="story-block history-block">
          <div class="story-head">
            <h3>{{ t('predict.history') }}</h3>
            <button class="ghost-link" type="button" @click="exportHistoryRows">
              {{ t('predict.exportHistory') }}
            </button>
          </div>

          <div v-if="history.length" class="history-list">
            <article v-for="item in history" :key="item.id" class="history-card">
              <div>
                <strong>{{ item.payload?.municipality || '—' }}</strong>
                <small>{{ new Date(item.created_at).toLocaleString('sl-SI') }}</small>
              </div>
              <div class="history-metric">
                <strong>{{ fmt(item.predicted_price_eur) }} €</strong>
                <small>{{ item.payload?.property_type || '—' }}</small>
              </div>
            </article>
          </div>
          <EmptyState v-else icon="🧾" :message="t('predict.noHistory')" />
        </section>
      </article>
    </section>
  </div>
</template>

<style scoped>
  .prediction-page {
    display: grid;
  }

  .prediction-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
    gap: 1rem;
  }

  .panel {
    border-radius: 1.65rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 78%);
    box-shadow: var(--shadow-sm);
  }

  .input-panel,
  .story-panel {
    padding: 1.2rem;
  }

  .panel-head {
    margin-bottom: 1.1rem;
  }

  .panel-head h1,
  .panel-head h2,
  .story-head h3 {
    margin: 0;
    font-family: var(--font-display);
  }

  .panel-head p,
  .estimate-card p,
  .context-card span,
  .context-card p,
  .comparable-card p,
  .comparable-card small,
  .history-card small,
  .inline-loading {
    color: var(--text-muted);
  }

  .eyebrow {
    display: inline-flex;
    margin-bottom: 0.55rem;
    color: var(--primary-strong);
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.17em;
    text-transform: uppercase;
  }

  .predict-form,
  .story-panel,
  .form-section,
  .story-block,
  .comparables-list,
  .history-list,
  .chip-grid,
  .context-metrics {
    display: grid;
    gap: 1rem;
  }

  .form-section h2 {
    margin: 0 0 0.15rem;
    font-size: 1rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .field {
    display: grid;
    gap: 0.38rem;
  }

  .field span {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--text-muted);
  }

  .municipality-field {
    position: relative;
  }

  .suggestions {
    position: absolute;
    top: calc(100% + 0.35rem);
    left: 0;
    right: 0;
    z-index: 6;
    margin: 0;
    padding: 0.35rem;
    list-style: none;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: var(--surface-strong);
    box-shadow: var(--shadow-sm);
  }

  .suggestions li {
    padding: 0.65rem 0.75rem;
    border-radius: 0.85rem;
    cursor: pointer;
  }

  .suggestions li.highlighted,
  .suggestions li:hover {
    background: rgb(37 99 235 / 10%);
    color: var(--primary-strong);
  }

  .toggle-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 0.7rem;
  }

  .toggle-chip {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 70%);
    font-weight: 600;
  }

  .form-actions {
    display: flex;
    justify-content: flex-start;
  }

  .submit-btn,
  .mini-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.9rem 1.1rem;
    border-radius: 999px;
    border: 1px solid rgb(37 99 235 / 22%);
    background: linear-gradient(135deg, var(--primary), var(--primary-strong));
    color: #eff6ff;
  }

  .story-block {
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }

  .story-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }

  .ghost-link {
    border: none;
    background: none;
    color: var(--primary-strong);
    font-weight: 700;
  }

  .estimate-card {
    padding: 1.15rem;
    border-radius: 1.35rem;
    background:
      linear-gradient(135deg, rgb(15 23 42 / 96%), rgb(28 39 63 / 96%)),
      linear-gradient(135deg, rgb(37 99 235 / 25%), transparent);
    color: #eff6ff;
  }

  .estimate-card span {
    display: inline-block;
    margin-bottom: 0.35rem;
    color: rgb(255 255 255 / 72%);
    font-size: 0.82rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .estimate-card strong {
    display: block;
    font-size: clamp(2rem, 4vw, 3rem);
    line-height: 1.05;
  }

  .estimate-card p {
    margin: 0.45rem 0 0;
    color: rgb(255 255 255 / 76%);
  }

  .data-chip {
    display: inline-flex;
    padding: 0.45rem 0.7rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 68%);
  }

  .chip-grid {
    grid-template-columns: repeat(auto-fit, minmax(150px, max-content));
  }

  .context-card {
    padding: 1rem;
    border-radius: 1.25rem;
    background: linear-gradient(135deg, rgb(37 99 235 / 9%), rgb(245 158 11 / 10%));
  }

  .context-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .context-metrics article span {
    display: block;
    margin-bottom: 0.25rem;
    font-size: 0.8rem;
    color: var(--text-soft);
  }

  .context-metrics article strong,
  .comparable-foot strong,
  .history-metric strong {
    display: block;
    font-size: 1.05rem;
  }

  .comparables-list,
  .history-list {
    gap: 0.8rem;
  }

  .comparable-card,
  .history-card {
    display: grid;
    gap: 0.4rem;
    padding: 0.95rem;
    border-radius: 1.15rem;
    border: 1px solid var(--border);
    background: rgb(255 255 255 / 72%);
  }

  .comparable-head,
  .comparable-foot,
  .history-card {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .mini-btn {
    justify-self: start;
    padding: 0.65rem 0.85rem;
    font-size: 0.82rem;
  }

  .history-metric {
    text-align: right;
  }

  .error-text,
  .field-error {
    color: var(--danger);
  }

  @media (max-width: 1100px) {
    .prediction-shell {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .form-grid,
    .context-metrics {
      grid-template-columns: 1fr;
    }

    .input-panel,
    .story-panel {
      padding: 1rem;
    }
  }
</style>
