<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useLocalStorage } from '@vueuse/core'
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
  import FeatureImportanceChart from '../components/charts/FeatureImportanceChart.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useExport } from '../composables/useExport'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatDateTime, formatNumber } from '../utils/format'
  import { municipalitySlug, normalizeMunicipalityName } from '../utils/municipality'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  interface PredictionForm {
    size_m2: number | null
    rooms: number | null
    year_built: number | null
    floor: number | null
    latitude: number | null
    longitude: number | null
    naselje: string
    municipality: string
    ime_ko: string
    property_type: string
    uporabna_povrsina: number | null
    lega_v_stavbi: string
    novogradnja: number
    has_garaza: number
    has_klet: number
    has_shramba: number
    has_terasa: number
    stavba_je_dokoncana: number
    ddv_vkljucen: number
  }

  interface PredictionFormErrors {
    size_m2?: string | null
    naselje?: string | null
    municipality?: string | null
  }

  interface NaseljeOption {
    label: string
    naselje: string
    municipality: string
    region?: string | null
    latitude?: number | null
    longitude?: number | null
    sample_count?: number
  }

  type BinaryPredictionField =
    | 'novogradnja'
    | 'has_garaza'
    | 'has_klet'
    | 'has_shramba'
    | 'has_terasa'
    | 'stavba_je_dokoncana'
    | 'ddv_vkljucen'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()
  const workbench = useWorkbenchStore()
  const { exportToCSV } = useExport()

  const form = ref<PredictionForm>({
    size_m2: null,
    rooms: null,
    year_built: null,
    floor: null,
    latitude: null,
    longitude: null,
    naselje: '',
    municipality: '',
    ime_ko: '',
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
  const storedDraft = useLocalStorage<Partial<PredictionForm>>('prediction_form_draft', {})

  const propertyTypes = [
    'stanovanje',
    'hisa',
    'poslovni_prostor',
    'industrijski',
    'turisticni',
    'gostinstvo',
    'garaza',
    'kmetijsko',
    'parcela',
  ]

  const legaOptions = ['pritlicje', 'nadstropje', 'klet', 'unknown']
  const scenarioPresets = [
    {
      key: 'apartment',
      label: 'workbench.apartmentPreset',
      values: {
        property_type: 'stanovanje',
        size_m2: 68,
        rooms: 2.5,
        floor: 3,
        stavba_je_dokoncana: 1,
      },
    },
    {
      key: 'house',
      label: 'workbench.housePreset',
      values: {
        property_type: 'hisa',
        size_m2: 150,
        rooms: 5,
        floor: 1,
        has_garaza: 1,
        stavba_je_dokoncana: 1,
      },
    },
    {
      key: 'newbuild',
      label: 'workbench.newBuildPreset',
      values: {
        property_type: 'stanovanje',
        size_m2: 82,
        rooms: 3,
        year_built: new Date().getFullYear(),
        novogradnja: 1,
        ddv_vkljucen: 1,
        stavba_je_dokoncana: 0,
      },
    },
  ]
  const allMunicipalities = ref([])
  const municipalitySuggestions = ref([])
  const naseljeSuggestions = ref<string[]>([])
  const naseljeOptions = ref<NaseljeOption[]>([])
  const showAdvancedLocation = ref(false)
  const result = ref(null)
  const history = ref([])
  const loading = ref(false)
  const contextLoading = ref(false)
  const error = ref('')
  const formErrors = ref<PredictionFormErrors>({})

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
  const currentMunicipality = computed(
    () => form.value.municipality || selectedNaseljeMeta.value?.municipality || '',
  )
  const selectedMunicipalityMeta = computed(() => {
    return municipalityIndex.value.get(normalizeMunicipalityName(currentMunicipality.value))
  })
  const comparisonUrl = computed(() =>
    buildNepremicnineSearchUrl({
      municipality: form.value.municipality || selectedNaseljeMeta.value?.municipality,
      statisticalRegion: selectedMunicipalityMeta.value?.region,
      propertyType: form.value.property_type,
    }),
  )
  const selectedNaseljeMeta = computed(() => {
    const target = form.value.naselje.trim().toLowerCase()
    return (
      naseljeOptions.value.find(
        (item) =>
          item.naselje.trim().toLowerCase() === target ||
          item.label.trim().toLowerCase() === target,
      ) || null
    )
  })

  function toggleValue(field: BinaryPredictionField) {
    return form.value[field] === 1
  }

  function updateToggle(field: BinaryPredictionField, checked: boolean) {
    form.value[field] = checked ? 1 : 0
  }

  function applyScenario(values: Partial<PredictionForm>) {
    form.value = {
      ...form.value,
      ...values,
    }
  }

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

  async function searchNaselja(event) {
    const query = String(event.query || '').trim()
    try {
      const { data } = await api.get('/api/stats/naselja', {
        params: {
          q: query || undefined,
          municipality: form.value.municipality || undefined,
          limit: 12,
        },
      })
      naseljeOptions.value = (data || []).map((item) => ({
        ...item,
        label: `${item.naselje} (${item.municipality})`,
      }))
      naseljeSuggestions.value = naseljeOptions.value.map((item) => item.label)
    } catch {
      naseljeOptions.value = []
      naseljeSuggestions.value = []
    }
  }

  function validateForm() {
    const errors: PredictionFormErrors = {}
    if (!form.value.size_m2 || form.value.size_m2 <= 0) {
      errors.size_m2 = t('validation.minSize')
    }
    if (!form.value.naselje?.trim()) {
      errors.naselje = t('validation.required')
    }
    formErrors.value = errors
    return Object.keys(errors).length === 0
  }

  async function loadContext(estimatedPrice = null) {
    const municipality = form.value.municipality || selectedNaseljeMeta.value?.municipality
    if (!municipality || !form.value.property_type || !effectiveSize.value) {
      stats.resetComparables()
      stats.resetMunicipalityDetail()
      return
    }

    contextLoading.value = true
    try {
      await Promise.all([
        stats.fetchMunicipalityDetail(municipalitySlug(municipality)),
        stats.fetchComparables({
          municipality,
          naselje: form.value.naselje || undefined,
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
      if (!form.value.municipality && selectedNaseljeMeta.value?.municipality) {
        form.value.municipality = selectedNaseljeMeta.value.municipality
      }
      const payload = {}
      for (const [key, value] of Object.entries(form.value)) {
        if (value !== null && value !== '' && value !== undefined) {
          payload[key] = value
        }
      }

      const { data } = await api.post('/api/predict', payload)
      result.value = data
      if (currentMunicipality.value) {
        workbench.rememberMunicipality({
          id: `municipality:${municipalitySlug(currentMunicipality.value)}`,
          entity_type: 'municipality',
          label: currentMunicipality.value,
          slug: municipalitySlug(currentMunicipality.value),
          region: selectedMunicipalityMeta.value?.region || null,
        })
      }
      await Promise.all([fetchHistory(), loadContext(data.predicted_price_eur)])
    } catch (err) {
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  function applyRouteQuery(query) {
    const numericFields = ['size_m2', 'year_built', 'price_eur']

    for (const field of ['naselje', 'municipality', 'property_type']) {
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

  async function addCurrentToWatchlist() {
    if (!currentMunicipality.value) return
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: municipalitySlug(currentMunicipality.value),
      display_label: currentMunicipality.value,
      metadata: {
        link: `/obcine/${municipalitySlug(currentMunicipality.value)}`,
        region: selectedMunicipalityMeta.value?.region || null,
      },
    })
  }

  function addCurrentToCompare() {
    if (!currentMunicipality.value) return
    workbench.addCompareItem({
      id: `municipality:${municipalitySlug(currentMunicipality.value)}`,
      entity_type: 'municipality',
      label: currentMunicipality.value,
      slug: municipalitySlug(currentMunicipality.value),
      region: selectedMunicipalityMeta.value?.region || null,
      metadata: { source: 'prediction' },
    })
  }

  function openMunicipality() {
    if (!municipalityContext.value?.slug) return
    router.push({
      path: `/obcine/${municipalityContext.value.slug}`,
      query: {
        property_type: form.value.property_type || undefined,
      },
    })
  }

  function reuseComparable(item) {
    router.push({
      name: 'prediction',
      query: {
        municipality: item.municipality,
        naselje: item.naselje || '',
        property_type: item.property_type || form.value.property_type,
        size_m2: item.size_m2 || '',
        year_built: item.year_built || '',
        price_eur: item.price_eur || '',
      },
    })
  }

  function openMarketExplorer() {
    router.push({
      name: 'market',
      query: {
        tab: 'transactions',
        municipality: currentMunicipality.value || undefined,
        property_type: form.value.property_type || undefined,
      },
    })
  }

  function openMapExplorer() {
    router.push({
      name: 'map',
      query: {
        municipality: currentMunicipality.value || undefined,
        region: selectedMunicipalityMeta.value?.region || undefined,
        property_type: form.value.property_type || undefined,
        view: 'transactions',
      },
    })
  }

  function openAnalysis() {
    router.push({
      name: 'analysis',
      query: {
        municipality: currentMunicipality.value || undefined,
        naselje: form.value.naselje || undefined,
        property_type: form.value.property_type || undefined,
        size_m2: effectiveSize.value ? String(effectiveSize.value) : undefined,
        year_built: form.value.year_built != null ? String(form.value.year_built) : undefined,
        floor: form.value.floor != null ? String(form.value.floor) : undefined,
        asking_price:
          typeof route.query.price_eur === 'string' && route.query.price_eur
            ? route.query.price_eur
            : undefined,
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

  watch(
    () => form.value.naselje,
    (value) => {
      formErrors.value.naselje = null
      const target = String(value || '')
        .trim()
        .toLowerCase()
      const match = naseljeOptions.value.find(
        (item) =>
          item.naselje.trim().toLowerCase() === target ||
          item.label.trim().toLowerCase() === target,
      )
      if (!match) {
        return
      }
      if (form.value.naselje !== match.naselje) {
        form.value.naselje = match.naselje
      }
      form.value.municipality = match.municipality
      if (form.value.latitude == null && match.latitude != null) {
        form.value.latitude = match.latitude
      }
      if (form.value.longitude == null && match.longitude != null) {
        form.value.longitude = match.longitude
      }
    },
  )

  watch(
    form,
    (value) => {
      storedDraft.value = { ...value }
    },
    { deep: true },
  )

  onMounted(async () => {
    form.value = {
      ...form.value,
      ...storedDraft.value,
    }
    await Promise.all([fetchHistory(), fetchMunicipalities(), stats.fetchFeatureImportance()])
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
        >
          <template #actions>
            <SavedWorkspaceMenu
              page="prediction"
              :state="{
                page: 'prediction',
                filters: { ...form, predicted_price_eur: result?.predicted_price_eur || undefined },
              }"
            />
            <Button
              severity="secondary"
              text
              icon="pi pi-bookmark"
              :label="t('workbench.watch')"
              @click="addCurrentToWatchlist"
            />
            <Button
              severity="secondary"
              text
              icon="pi pi-plus-circle"
              :label="t('workbench.compare')"
              @click="addCurrentToCompare"
            />
          </template>
        </PageHeader>

        <div class="scenario-row">
          <Button
            v-for="preset in scenarioPresets"
            :key="preset.key"
            severity="secondary"
            outlined
            :label="t(preset.label)"
            @click="applyScenario(preset.values)"
          />
        </div>

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
                <span>{{ t('predict.naselje') }} *</span>
                <AutoComplete
                  v-model="form.naselje"
                  :suggestions="naseljeSuggestions"
                  :placeholder="t('predict.naseljePlaceholder')"
                  input-class="form-input"
                  dropdown
                  :force-selection="false"
                  fluid
                  :invalid="!!formErrors.naselje"
                  @complete="searchNaselja"
                  @update:model-value="formErrors.naselje = null"
                />
                <small v-if="formErrors.naselje" class="field-error">{{
                  formErrors.naselje
                }}</small>
              </label>

              <label class="field">
                <span>{{ t('predict.municipality') }}</span>
                <AutoComplete
                  v-model="form.municipality"
                  :suggestions="municipalitySuggestions"
                  :placeholder="t('predict.municipalityPlaceholder')"
                  input-class="form-input"
                  dropdown
                  :force-selection="false"
                  fluid
                  @complete="searchMunicipalities"
                />
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
              <label class="toggle-chip">
                <ToggleSwitch
                  :model-value="toggleValue('novogradnja')"
                  @update:model-value="updateToggle('novogradnja', $event)"
                />
                <span>{{ t('predict.novogradnja') }}</span>
              </label>
              <label class="toggle-chip">
                <ToggleSwitch
                  :model-value="toggleValue('has_garaza')"
                  @update:model-value="updateToggle('has_garaza', $event)"
                />
                <span>{{ t('predict.hasGaraza') }}</span>
              </label>
              <label class="toggle-chip">
                <ToggleSwitch
                  :model-value="toggleValue('has_klet')"
                  @update:model-value="updateToggle('has_klet', $event)"
                />
                <span>{{ t('predict.hasKlet') }}</span>
              </label>
              <label class="toggle-chip">
                <ToggleSwitch
                  :model-value="toggleValue('has_shramba')"
                  @update:model-value="updateToggle('has_shramba', $event)"
                />
                <span>{{ t('predict.hasShramba') }}</span>
              </label>
              <label class="toggle-chip">
                <ToggleSwitch
                  :model-value="toggleValue('has_terasa')"
                  @update:model-value="updateToggle('has_terasa', $event)"
                />
                <span>{{ t('predict.hasTerasa') }}</span>
              </label>
              <label class="toggle-chip">
                <ToggleSwitch
                  :model-value="toggleValue('stavba_je_dokoncana')"
                  @update:model-value="updateToggle('stavba_je_dokoncana', $event)"
                />
                <span>{{ t('predict.stavbaDokoncana') }}</span>
              </label>
              <label class="toggle-chip">
                <ToggleSwitch
                  :model-value="toggleValue('ddv_vkljucen')"
                  @update:model-value="updateToggle('ddv_vkljucen', $event)"
                />
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
            <div class="estimate-top">
              <div>
                <span>{{ t('predict.predictedPrice') }}</span>
                <strong>{{ formatCurrency(result.predicted_price_eur) }}</strong>
              </div>
              <p>{{ t('predict.modelUsed') }}: {{ result.model_used }}</p>
            </div>

            <div class="estimate-meta-grid">
              <article>
                <span>{{ t('predict.propertyType') }}</span>
                <strong>{{ formatType(form.property_type) || '—' }}</strong>
              </article>
              <article>
                <span>{{ t('predict.municipality') }}</span>
                <strong>{{ form.municipality || '—' }}</strong>
              </article>
              <article>
                <span>{{ t('predict.size') }}</span>
                <strong>{{ fmt(effectiveSize, 1) }} m²</strong>
              </article>
            </div>
          </section>

          <div class="story-actions">
            <a :href="comparisonUrl" target="_blank" rel="noreferrer">
              <Button
                severity="secondary"
                text
                class="action-link"
                :label="t('predict.compareOnPortal')"
              />
            </a>
            <Button
              severity="secondary"
              text
              icon="pi pi-table"
              :label="t('nav.market')"
              @click="openMarketExplorer"
            />
            <Button
              severity="secondary"
              text
              icon="pi pi-map"
              :label="t('nav.map')"
              @click="openMapExplorer"
            />
            <Button
              severity="secondary"
              text
              icon="pi pi-search"
              :label="t('nav.analysis')"
              @click="openAnalysis"
            />
          </div>

          <section class="story-block">
            <div class="story-head">
              <h3>{{ t('predict.featuresUsed') }}</h3>
              <Button
                severity="secondary"
                text
                :label="t('common.retry')"
                @click="loadContext(result.predicted_price_eur)"
              />
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
              <Button
                severity="secondary"
                text
                :label="t('predict.openMunicipality')"
                @click="openMunicipality"
              />
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
                <Button
                  size="small"
                  :label="t('predict.reuseComparable')"
                  @click="reuseComparable(item)"
                />
              </article>
            </div>
            <EmptyState v-else icon="📊" :message="t('predict.noComparables')" />
          </section>
        </template>

        <EmptyState v-else icon="🏠" :message="t('predict.emptyState')" />

        <section v-if="stats.featureImportance?.length" class="story-block">
          <div class="story-head">
            <h3>{{ t('market.featureImportance') }}</h3>
            <RouterLink
              :to="{
                path: '/trg',
                query: {
                  tab: 'rankings',
                  municipality: currentMunicipality || undefined,
                  property_type: form.property_type || undefined,
                },
              }"
              class="story-link"
            >
              <Button severity="secondary" text :label="t('market.viewAll')" />
            </RouterLink>
          </div>
          <p class="muted feature-desc">{{ t('market.featureImportanceDesc') }}</p>
          <FeatureImportanceChart :features="stats.featureImportance" :limit="7" />
        </section>

        <section class="story-block history-block">
          <div class="story-head">
            <h3>{{ t('predict.history') }}</h3>
            <Button
              severity="secondary"
              text
              :label="t('predict.exportHistory')"
              @click="exportHistoryRows"
            />
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

  .scenario-row {
    display: flex;
    gap: 0.65rem;
    flex-wrap: wrap;
    margin: 0 0 1rem;
  }

  .prediction-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
    gap: 1.15rem;
  }

  .panel {
    border-radius: 1.65rem;
    border: 1px solid var(--border);
    background: var(--surface-soft);
    box-shadow: var(--shadow-sm);
  }

  .input-panel,
  .story-panel {
    padding: 1.2rem;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-soft) 94%, white 6%),
        var(--surface-soft)
      ),
      var(--surface-soft);
  }

  .panel-head {
    margin-bottom: 1.1rem;
  }

  .story-actions {
    margin: 0.9rem 0 0.25rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
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

  .form-section {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 1.25rem;
    background: var(--surface-soft-subtle);
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
    padding: 0.9rem 1rem;
    border: 1px solid var(--border);
    border-radius: 1rem;
    background: var(--surface-soft-subtle);
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
    border-radius: 1rem;
    border: 1px solid var(--border);
    background: var(--surface-soft-subtle);
    font-weight: 600;
    line-height: 1.25;
    cursor: pointer;
    transition:
      border-color 0.18s ease,
      transform 0.18s ease,
      box-shadow 0.18s ease,
      background-color 0.18s ease;
  }

  .toggle-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 26%, var(--border));
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
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

  .submit-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.9rem 1.1rem;
    border-radius: 999px;
    border: 1px solid var(--primary-border);
    background: linear-gradient(135deg, var(--primary), var(--primary-strong));
    color: var(--primary-contrast);
  }

  .story-block {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 1.25rem;
    background: var(--surface-soft-subtle);
  }

  .story-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }

  .story-link {
    text-decoration: none;
  }

  .feature-desc {
    margin: -0.4rem 0 0.6rem;
    font-size: 0.86rem;
  }

  .estimate-card {
    display: grid;
    gap: 1rem;
    padding: 1.15rem;
    border-radius: 1.35rem;
    background:
      linear-gradient(135deg, var(--surface-dark), var(--surface-dark-alt)),
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 34%, transparent),
        transparent 38%
      ),
      linear-gradient(135deg, var(--primary-overlay), transparent);
    color: var(--primary-contrast);
    box-shadow: 0 28px 46px color-mix(in srgb, var(--surface-dark) 30%, transparent);
  }

  .estimate-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .estimate-card span {
    display: inline-block;
    margin-bottom: 0.35rem;
    color: var(--text-on-dark);
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
    margin: 0;
    color: var(--text-on-dark);
  }

  .estimate-meta-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .estimate-meta-grid article {
    padding: 0.85rem 0.9rem;
    border-radius: 1rem;
    background: color-mix(in srgb, white 10%, transparent);
    border: 1px solid color-mix(in srgb, white 10%, transparent);
    min-width: 0;
  }

  .estimate-meta-grid article strong {
    display: block;
    font-size: 1rem;
    line-height: 1.25;
  }

  .data-chip {
    display: inline-flex;
    padding: 0.45rem 0.7rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-soft-subtle);
  }

  .chip-grid {
    grid-template-columns: repeat(auto-fit, minmax(150px, max-content));
  }

  .context-card {
    padding: 1rem;
    border-radius: 1.25rem;
    background: linear-gradient(135deg, var(--primary-overlay), var(--warning-overlay));
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
    background: var(--surface-soft-muted);
  }

  .comparable-head,
  .comparable-foot,
  .history-card {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
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
    .context-metrics,
    .estimate-meta-grid,
    .estimate-top {
      grid-template-columns: 1fr;
    }

    .estimate-top {
      display: grid;
    }

    .input-panel,
    .story-panel {
      padding: 1rem;
    }
  }
</style>
