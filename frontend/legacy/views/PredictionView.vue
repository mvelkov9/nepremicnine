<script setup>
  import { computed, onMounted, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AutoComplete from 'primevue/autocomplete'
  import Button from 'primevue/button'
  import InputNumber from 'primevue/inputnumber'
  import Select from 'primevue/select'
  import ToggleSwitch from 'primevue/toggleswitch'
  import api from '../composables/useApi'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useExport } from '../composables/useExport'
  import { useStatsStore } from '../stores/stats'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatDateTime, formatNumber } from '../utils/format'
  import { municipalitySlug, normalizeMunicipalityName } from '../utils/municipality'
  import { getPropertyTypeLabel } from '../utils/propertyType'

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
  const allMunicipalities = ref([])
  const municipalitySuggestions = ref([])
  const showAdvancedLocation = ref(false)
  const result = ref(null)
  const history = ref([])
  const loading = ref(false)
  const contextLoading = ref(false)
  const error = ref('')
  const formErrors = ref({})

  const municipalityContext = computed(() => stats.municipalityDetail)
  const comparables = computed(() => stats.comparables)
  const comparableRows = computed(() => comparables.value?.items || [])
  const municipalityIndex = computed(
    () =>
      new Map(
        allMunicipalities.value.map((item) => [normalizeMunicipalityName(item.municipality), item]),
      ),
  )
  const comparablesCountLabel = computed(
    () => `${comparables.value?.summary?.count || 0} ${t('dashboard.transactions')}`,
  )
  const effectiveSize = computed(() => form.value.uporabna_povrsina || form.value.size_m2)
  const selectedMunicipalityMeta = computed(() =>
    municipalityIndex.value.get(normalizeMunicipalityName(form.value.municipality)),
  )
  const comparisonUrl = computed(() =>
    buildNepremicnineSearchUrl({
      municipality: form.value.municipality,
      statisticalRegion: selectedMunicipalityMeta.value?.region,
      propertyType: form.value.property_type,
    }),
  )

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function formatType(value) {
    return getPropertyTypeLabel(value, t)
  }

  async function fetchMunicipalities() {
    try {
      const { data } = await api.get('/api/regions/municipalities')
      allMunicipalities.value = data || []
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

  function searchMunicipalities(event) {
    const query = normalizeMunicipalityName(event.query || '')
    municipalitySuggestions.value = query
      ? allMunicipalities.value
          .filter((item) => normalizeMunicipalityName(item.municipality).includes(query))
          .map((item) => item.municipality)
          .slice(0, 12)
      : allMunicipalities.value.map((item) => item.municipality).slice(0, 12)
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
        <PageHeader
          :eyebrow="t('predict.title')"
          :title="t('predict.avmTitle')"
          :description="t('predict.avmBody')"
        />

        <form class="predict-form" @submit.prevent="predict">
          <div class="form-section">
            <h2>{{ t('predict.subjectBasics') }}</h2>
            <div class="form-grid">
              <label class="field">
                <span>{{ t('predict.size') }} *</span>
                <InputNumber
                  v-model="form.size_m2"
                  input-class="form-input"
                  :min="1"
                  :min-fraction-digits="0"
                  :max-fraction-digits="1"
                  fluid
                  :invalid="!!formErrors.size_m2"
                  @update:model-value="formErrors.size_m2 = null"
                />
                <small v-if="formErrors.size_m2" class="field-error">{{
                  formErrors.size_m2
                }}</small>
              </label>

              <label class="field">
                <span>{{ t('predict.uporabnaPovrsina') }}</span>
                <InputNumber
                  v-model="form.uporabna_povrsina"
                  input-class="form-input"
                  :min="0"
                  :min-fraction-digits="0"
                  :max-fraction-digits="1"
                  fluid
                />
              </label>

              <label class="field">
                <span>{{ t('predict.rooms') }}</span>
                <InputNumber
                  v-model="form.rooms"
                  input-class="form-input"
                  :min="0"
                  :min-fraction-digits="0"
                  :max-fraction-digits="1"
                  fluid
                />
              </label>

              <label class="field">
                <span>{{ t('predict.yearBuilt') }}</span>
                <InputNumber
                  v-model="form.year_built"
                  input-class="form-input"
                  :min="1800"
                  :max="2030"
                  fluid
                />
              </label>

              <label class="field">
                <span>{{ t('predict.floor') }}</span>
                <InputNumber
                  v-model="form.floor"
                  input-class="form-input"
                  :min="-2"
                  :max="60"
                  fluid
                />
              </label>

              <label class="field">
                <span>{{ t('predict.propertyType') }}</span>
                <Select
                  v-model="form.property_type"
                  :options="propertyTypes.map((item) => ({ label: formatType(item), value: item }))"
                  option-label="label"
                  option-value="value"
                />
              </label>
            </div>
          </div>

          <div class="form-section">
            <h2>{{ t('predict.locationContext') }}</h2>
            <div class="form-grid">
              <label class="field">
                <span>{{ t('predict.municipality') }} *</span>
                <AutoComplete
                  v-model="form.municipality"
                  :suggestions="municipalitySuggestions"
                  :placeholder="t('predict.municipalityPlaceholder')"
                  input-class="form-input"
                  dropdown
                  :force-selection="false"
                  fluid
                  :invalid="!!formErrors.municipality"
                  @complete="searchMunicipalities"
                  @update:model-value="formErrors.municipality = null"
                />
                <small v-if="formErrors.municipality" class="field-error">{{
                  formErrors.municipality
                }}</small>
              </label>

              <label class="field">
                <span>{{ t('predict.legaVStavbi') }}</span>
                <Select
                  v-model="form.lega_v_stavbi"
                  :options="[
                    { label: t('common.noData'), value: '' },
                    ...legaOptions.map((option) => ({
                      label: t(`predict.lega.${option}`),
                      value: option,
                    })),
                  ]"
                  option-label="label"
                  option-value="value"
                />
              </label>

              <div class="field municipality-chip">
                <span>{{ t('predict.marketContext') }}</span>
                <strong>{{
                  selectedMunicipalityMeta?.region || t('predict.coordsAutoHint')
                }}</strong>
                <small class="muted">
                  {{
                    selectedMunicipalityMeta?.region
                      ? t('predict.coordsAutoHint')
                      : t('predict.pickMunicipalityHint')
                  }}
                </small>
              </div>
            </div>

            <div class="advanced-toggle">
              <Button
                severity="secondary"
                outlined
                icon="pi pi-map-marker"
                :label="
                  showAdvancedLocation
                    ? t('predict.hideAdvancedLocation')
                    : t('predict.showAdvancedLocation')
                "
                @click="showAdvancedLocation = !showAdvancedLocation"
              />
            </div>

            <div v-if="showAdvancedLocation" class="form-grid advanced-grid">
              <label class="field">
                <span>{{ t('predict.latitude') }}</span>
                <InputNumber
                  v-model="form.latitude"
                  input-class="form-input"
                  :min-fraction-digits="0"
                  :max-fraction-digits="4"
                  fluid
                />
              </label>

              <label class="field">
                <span>{{ t('predict.longitude') }}</span>
                <InputNumber
                  v-model="form.longitude"
                  input-class="form-input"
                  :min-fraction-digits="0"
                  :max-fraction-digits="4"
                  fluid
                />
              </label>
            </div>
          </div>

          <div class="form-section">
            <h2>{{ t('predict.buildingFlags') }}</h2>
            <div class="toggle-grid">
              <label class="toggle-chip" :class="{ active: form.novogradnja === 1 }">
                <ToggleSwitch v-model="form.novogradnja" :true-value="1" :false-value="0" />
                <span>{{ t('predict.novogradnja') }}</span>
              </label>
              <label class="toggle-chip" :class="{ active: form.has_garaza === 1 }">
                <ToggleSwitch v-model="form.has_garaza" :true-value="1" :false-value="0" />
                <span>{{ t('predict.hasGaraza') }}</span>
              </label>
              <label class="toggle-chip" :class="{ active: form.has_klet === 1 }">
                <ToggleSwitch v-model="form.has_klet" :true-value="1" :false-value="0" />
                <span>{{ t('predict.hasKlet') }}</span>
              </label>
              <label class="toggle-chip" :class="{ active: form.has_shramba === 1 }">
                <ToggleSwitch v-model="form.has_shramba" :true-value="1" :false-value="0" />
                <span>{{ t('predict.hasShramba') }}</span>
              </label>
              <label class="toggle-chip" :class="{ active: form.has_terasa === 1 }">
                <ToggleSwitch v-model="form.has_terasa" :true-value="1" :false-value="0" />
                <span>{{ t('predict.hasTerasa') }}</span>
              </label>
              <label class="toggle-chip" :class="{ active: form.stavba_je_dokoncana === 1 }">
                <ToggleSwitch v-model="form.stavba_je_dokoncana" :true-value="1" :false-value="0" />
                <span>{{ t('predict.stavbaDokoncana') }}</span>
              </label>
              <label class="toggle-chip" :class="{ active: form.ddv_vkljucen === 1 }">
                <ToggleSwitch v-model="form.ddv_vkljucen" :true-value="1" :false-value="0" />
                <span>{{ t('predict.ddvVkljucen') }}</span>
              </label>
            </div>
          </div>

          <p v-if="error" class="error-text">{{ error }}</p>

          <div class="form-actions">
            <Button
              class="submit-btn"
              type="submit"
              icon="pi pi-bolt"
              :loading="loading"
              :label="loading ? t('common.loading') : t('predict.predictButton')"
            />
          </div>
        </form>
      </article>

      <article class="panel story-panel">
        <PageHeader
          compact
          :eyebrow="t('predict.result')"
          :title="t('predict.valuationStory')"
          :description="t('predict.valuationBody')"
        />

        <div v-if="loading || contextLoading" class="inline-loading">
          <LoadingSpinner :label="t('common.loading')" />
        </div>

        <template v-else-if="result">
          <section class="estimate-card">
            <span>{{ t('predict.predictedPrice') }}</span>
            <strong>{{ formatCurrency(result.predicted_price_eur) }}</strong>
            <p>{{ t('predict.modelUsed') }}: {{ result.model_used }}</p>
          </section>

          <div class="story-actions">
            <a :href="comparisonUrl" target="_blank" rel="noreferrer">
              <button class="ghost-link action-link" type="button">
                {{ t('predict.compareOnPortal') }}
              </button>
            </a>
          </div>

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
                <strong>{{ formatCurrency(municipalityContext.overview?.median_price) }}</strong>
              </article>
              <article>
                <span>{{ t('dashboard.pricePerM2') }}</span>
                <strong>{{
                  formatCurrency(municipalityContext.overview?.median_price_per_m2)
                }}</strong>
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
                  {{ formatType(item.property_type) || '—' }} · {{ fmt(item.size_m2, 1) }} m² ·
                  {{ formatCurrency(item.price_per_m2) }}/m²
                </p>
                <div class="comparable-foot">
                  <strong>{{ formatCurrency(item.price_eur) }}</strong>
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
                <small>{{ formatDateTime(item.created_at) }}</small>
              </div>
              <div class="history-metric">
                <strong>{{ formatCurrency(item.predicted_price_eur) }}</strong>
                <small>{{ formatType(item.payload?.property_type) || '—' }}</small>
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
    gap: 1.1rem;
  }

  .panel {
    border-radius: 1.8rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-strong) 88%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .input-panel,
  .story-panel {
    padding: 1.3rem;
  }

  .panel-head {
    margin-bottom: 1.1rem;
  }

  .story-actions {
    margin: 0.9rem 0 0.25rem;
  }

  .action-link {
    text-decoration: none;
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

  .municipality-chip {
    align-content: flex-start;
    min-height: 100%;
    padding: 1rem 1.05rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    border-radius: 1.15rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 86%, transparent),
      color-mix(in srgb, var(--surface-muted) 78%, transparent)
    );
  }

  .municipality-chip strong {
    font-size: 1rem;
  }

  .field span {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--text-muted);
  }

  .advanced-toggle {
    display: flex;
    justify-content: flex-start;
  }

  .advanced-grid {
    margin-top: 0.85rem;
  }

  .toggle-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 0.7rem;
  }

  .toggle-chip {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.65rem;
    min-height: 3.4rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1.1rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 82%, transparent),
      color-mix(in srgb, var(--surface-muted) 80%, transparent)
    );
    font-weight: 600;
    line-height: 1.25;
    cursor: pointer;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 12px 20px rgb(15 23 42 / 5%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease,
      box-shadow 160ms ease,
      color 160ms ease;
  }

  .toggle-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 28%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 18px 28px rgb(15 23 42 / 10%);
  }

  .toggle-chip.active {
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 16%, transparent),
      color-mix(in srgb, var(--secondary) 12%, transparent)
    );
    color: var(--text);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 18px 30px rgb(15 23 42 / 12%);
  }

  .toggle-chip :deep(.p-toggleswitch) {
    flex: 0 0 auto;
  }

  .toggle-chip :deep(.p-toggleswitch-slider) {
    border-radius: 999px;
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
    border: 1px solid color-mix(in srgb, var(--primary) 28%, transparent);
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--primary) 86%, white 6%),
      color-mix(in srgb, var(--secondary) 18%, var(--primary) 82%)
    );
    color: var(--ui-text-inverted);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 16px 28px rgb(15 23 42 / 14%);
    transition:
      transform 160ms ease,
      box-shadow 160ms ease,
      filter 160ms ease;
  }

  .submit-btn:hover,
  .mini-btn:hover {
    transform: translateY(-2px);
    filter: saturate(1.04);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 20px 34px rgb(15 23 42 / 18%);
  }

  .submit-btn:active,
  .mini-btn:active {
    transform: translateY(0) scale(0.98);
  }

  .story-block {
    padding: 1.05rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    border-radius: 1.35rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 90%, transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 16px 28px rgb(15 23 42 / 6%);
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
    transition:
      color 160ms ease,
      transform 160ms ease;
  }

  .ghost-link:hover {
    color: var(--primary);
    transform: translateX(2px);
  }

  .estimate-card {
    padding: 1.25rem;
    border-radius: 1.5rem;
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 28%, transparent),
        transparent 32%
      ),
      radial-gradient(
        circle at bottom right,
        color-mix(in srgb, var(--secondary) 18%, transparent),
        transparent 26%
      ),
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--ui-bg-inverted) 88%, var(--ui-bg) 12%),
        color-mix(in srgb, var(--ui-bg-inverted) 80%, transparent)
      );
    color: var(--ui-text-inverted);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 26px 56px rgb(15 23 42 / 24%);
  }

  .estimate-card span {
    display: inline-block;
    margin-bottom: 0.35rem;
    color: color-mix(in srgb, var(--ui-text-inverted) 72%, transparent);
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
    color: color-mix(in srgb, var(--ui-text-inverted) 76%, transparent);
  }

  .data-chip {
    display: inline-flex;
    padding: 0.45rem 0.7rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-subtle) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 12%);
  }

  .chip-grid {
    grid-template-columns: repeat(auto-fit, minmax(150px, max-content));
  }

  .context-card {
    padding: 1.05rem;
    border-radius: 1.35rem;
    border: 1px solid color-mix(in srgb, var(--primary) 14%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 8%, transparent),
      color-mix(in srgb, var(--secondary) 9%, transparent)
    );
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
    padding: 1rem;
    border-radius: 1.2rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-muted) 90%, transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease,
      background 160ms ease;
  }

  .comparable-card:hover,
  .history-card:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 9%, var(--surface-soft-muted)),
      color-mix(in srgb, var(--secondary) 7%, var(--surface-soft))
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 30px rgb(15 23 42 / 10%);
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
