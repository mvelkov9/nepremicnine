<script setup>
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import AutoComplete from 'primevue/autocomplete'
  import Button from 'primevue/button'
  import InputNumber from 'primevue/inputnumber'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import Textarea from 'primevue/textarea'
  import ToggleSwitch from 'primevue/toggleswitch'
  import api from '../composables/useApi'
  import { useMunicipalityLookup } from '../composables/useMunicipalityLookup'
  import { useToast } from '../composables/useToast'
  import AppDataTable from '../components/AppDataTable.vue'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useAuthStore } from '../stores/auth'
  import { useExport } from '../composables/useExport'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const auth = useAuthStore()
  const { exportToCSV } = useExport()
  const { showToast } = useToast()
  const {
    municipalitySuggestions,
    fetchMunicipalities,
    findMunicipalityMeta,
    searchMunicipalities,
  } = useMunicipalityLookup()

  function createDefaultGuidedForm() {
    return {
      municipality: '',
      property_type: 'stanovanje',
      size_m2: 65,
      uporabna_povrsina: null,
      rooms: 2.5,
      year_built: null,
      floor: null,
      lega_v_stavbi: '',
      novogradnja: 0,
      has_garaza: 0,
      has_klet: 0,
      has_shramba: 0,
      has_terasa: 0,
      stavba_je_dokoncana: 1,
      ddv_vkljucen: 0,
      asking_price: null,
      notes: '',
    }
  }

  const guidedForm = ref(createDefaultGuidedForm())
  const threshold = ref(15)
  const loading = ref(false)
  const error = ref('')
  const result = ref(null)
  const advancedJson = ref('')
  const formErrors = ref({})

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

  const propertyTypeOptions = computed(() =>
    propertyTypes.map((value) => ({
      label: getPropertyTypeLabel(value, t),
      value,
    })),
  )

  const primaryListing = computed(() => result.value?.listings?.[0] || null)
  const selectedMunicipalityMeta = computed(() => findMunicipalityMeta(guidedForm.value.municipality))
  const resultColumns = computed(() => [
    { key: 'municipality', label: t('dashboard.municipality'), sortable: true },
    { key: 'property_type', label: t('predict.propertyType'), sortable: true },
    { key: 'size', label: t('predict.size'), sortable: true, value: (row) => row.uporabna_povrsina || row.size_m2 },
    { key: 'floor', label: t('predict.floor'), sortable: true },
    { key: 'asking_price', label: t('analysis.askingPrice'), sortable: true },
    { key: 'predicted_price', label: t('analysis.predictedPrice'), sortable: true },
    { key: 'deviation_percent', label: t('analysis.deviation'), sortable: true },
    { key: 'label', label: t('analysis.label'), sortable: true },
  ])
  const summaryCards = computed(() => {
    const listings = result.value?.listings || []
    const counts = listings.reduce(
      (accumulator, item) => {
        accumulator.total += 1
        if (item.label === 'overpriced') accumulator.overpriced += 1
        if (item.label === 'underpriced') accumulator.underpriced += 1
        if (item.label === 'market_aligned') accumulator.marketAligned += 1
        return accumulator
      },
      { total: 0, overpriced: 0, underpriced: 0, marketAligned: 0 },
    )

    return [
      { label: t('analysis.total'), value: fmt(counts.total) },
      { label: t('analysis.overpriced'), value: fmt(counts.overpriced) },
      { label: t('analysis.underpriced'), value: fmt(counts.underpriced) },
      { label: t('analysis.marketAligned'), value: fmt(counts.marketAligned) },
    ]
  })

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value) {
    return formatCurrency(value)
  }

  function labelSeverity(label) {
    if (label === 'overpriced') return 'danger'
    if (label === 'underpriced') return 'success'
    return 'info'
  }

  function labelText(label) {
    if (label === 'market_aligned') return t('analysis.marketAligned')
    return t(`analysis.${label}`)
  }

  function formatType(value) {
    return getPropertyTypeLabel(value, t)
  }

  function buildGuidedPayload() {
    return Object.fromEntries(
      Object.entries(guidedForm.value).filter(
        ([key, value]) => key !== 'notes' && value !== null && value !== '',
      ),
    )
  }

  function validateGuidedForm() {
    const nextErrors = {}
    if (!guidedForm.value.municipality?.trim()) {
      nextErrors.municipality = t('validation.required')
    }
    if (!guidedForm.value.size_m2 || guidedForm.value.size_m2 <= 0) {
      nextErrors.size_m2 = t('validation.minSize')
    }
    if (!guidedForm.value.asking_price || guidedForm.value.asking_price <= 0) {
      nextErrors.asking_price = t('validation.minValue')
    }

    formErrors.value = nextErrors
    return Object.keys(nextErrors).length === 0
  }

  async function analyzeListings(listings, successMessage) {
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const { data } = await api.post('/api/analysis/score', {
        listings,
        threshold: threshold.value,
      }, { skipErrorToast: true })
      result.value = data
      showToast(t(successMessage, { count: data.listings?.length || 0 }), 'success')
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  async function analyzeGuided() {
    if (!validateGuidedForm()) {
      return
    }

    await analyzeListings([buildGuidedPayload()], 'analysis.guidedCompleted')
  }

  async function analyzeAdvanced() {
    try {
      const parsed = JSON.parse(advancedJson.value)
      const listings = Array.isArray(parsed) ? parsed : [parsed]
      await analyzeListings(listings, 'analysis.bulkCompleted')
    } catch (e) {
      error.value = e instanceof SyntaxError ? t('analysis.invalidJson') : getApiErrorMessage(e, t)
    }
  }

  function loadSample() {
    advancedJson.value = JSON.stringify(
      [
        {
          size_m2: 65,
          uporabna_povrsina: 60,
          rooms: 2.5,
          year_built: 2005,
          floor: 3,
          municipality: 'Ljubljana',
          property_type: 'stanovanje',
          has_terasa: 1,
          asking_price: 250000,
        },
        {
          size_m2: 120,
          uporabna_povrsina: 114,
          rooms: 4,
          year_built: 1990,
          floor: 1,
          municipality: 'Maribor',
          property_type: 'hisa',
          has_garaza: 1,
          asking_price: 180000,
        },
      ],
      null,
      2,
    )
  }

  const comparisonUrl = computed(() =>
    buildNepremicnineSearchUrl({
      municipality: guidedForm.value.municipality,
      statisticalRegion: selectedMunicipalityMeta.value?.region,
      propertyType: guidedForm.value.property_type,
    }),
  )

  onMounted(() => {
    void fetchMunicipalities()
  })
</script>

<template>
  <div class="analysis-page">
    <section class="hero-shell">
      <PageHeader
        :eyebrow="t('analysis.consumerKicker')"
        :title="t('analysis.consumerTitle')"
        :description="t('analysis.consumerBody')"
      />

      <a :href="comparisonUrl" target="_blank" rel="noreferrer" class="hero-link">
        <Button
          severity="secondary"
          outlined
          icon="pi pi-external-link"
          :label="t('analysis.compareOnPortal')"
        />
      </a>
    </section>

    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow subtle">{{ t('analysis.guidedCheck') }}</p>
          <h2>{{ t('analysis.guidedTitle') }}</h2>
        </div>

        <div class="threshold">
          <label>{{ t('analysis.threshold') }}</label>
          <InputNumber v-model="threshold" input-id="threshold" :min="1" :max="100" suffix="%" />
        </div>
      </div>

      <div class="form-grid">
        <label class="field">
          <span>{{ t('predict.municipality') }}</span>
          <AutoComplete
            v-model="guidedForm.municipality"
            :suggestions="municipalitySuggestions"
            :placeholder="t('predict.municipalityPlaceholder')"
            dropdown
            fluid
            :invalid="!!formErrors.municipality"
            @complete="searchMunicipalities"
            @update:model-value="formErrors.municipality = null"
          />
          <small v-if="formErrors.municipality" class="field-error">{{ formErrors.municipality }}</small>
        </label>

        <label class="field">
          <span>{{ t('predict.propertyType') }}</span>
          <Select
            v-model="guidedForm.property_type"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </label>

        <label class="field">
          <span>{{ t('predict.size') }}</span>
          <InputNumber
            v-model="guidedForm.size_m2"
            :min="1"
            suffix=" m²"
            :invalid="!!formErrors.size_m2"
            @update:model-value="formErrors.size_m2 = null"
          />
          <small v-if="formErrors.size_m2" class="field-error">{{ formErrors.size_m2 }}</small>
        </label>

        <label class="field">
          <span>{{ t('predict.uporabnaPovrsina') }}</span>
          <InputNumber v-model="guidedForm.uporabna_povrsina" :min="0" suffix=" m²" />
        </label>

        <label class="field">
          <span>{{ t('predict.rooms') }}</span>
          <InputNumber v-model="guidedForm.rooms" :min="0" :step="0.5" />
        </label>

        <label class="field">
          <span>{{ t('predict.yearBuilt') }}</span>
          <InputNumber v-model="guidedForm.year_built" :min="1800" :max="2100" />
        </label>

        <label class="field">
          <span>{{ t('predict.floor') }}</span>
          <InputNumber v-model="guidedForm.floor" :min="-2" :max="60" />
        </label>

        <label class="field">
          <span>{{ t('predict.legaVStavbi') }}</span>
          <Select
            v-model="guidedForm.lega_v_stavbi"
            :options="[
              { label: t('common.noData'), value: '' },
              { label: t('predict.lega.pritlicje'), value: 'pritlicje' },
              { label: t('predict.lega.nadstropje'), value: 'nadstropje' },
              { label: t('predict.lega.klet'), value: 'klet' },
              { label: t('predict.lega.unknown'), value: 'unknown' },
            ]"
            option-label="label"
            option-value="value"
          />
        </label>

        <label class="field">
          <span>{{ t('analysis.askingPrice') }}</span>
          <InputNumber
            v-model="guidedForm.asking_price"
            mode="currency"
            currency="EUR"
            locale="sl-SI"
            :invalid="!!formErrors.asking_price"
            @update:model-value="formErrors.asking_price = null"
          />
          <small v-if="formErrors.asking_price" class="field-error">{{ formErrors.asking_price }}</small>
        </label>

        <label class="field notes-field">
          <span>{{ t('analysis.contextNotes') }}</span>
          <InputText v-model="guidedForm.notes" />
        </label>

        <div class="field municipality-chip">
          <span>{{ t('analysis.marketContext') }}</span>
          <strong>{{ selectedMunicipalityMeta?.region || '—' }}</strong>
          <small class="muted">
            {{
              selectedMunicipalityMeta?.region
                ? t('predict.coordsAutoHint')
                : t('predict.pickMunicipalityHint')
            }}
          </small>
        </div>
      </div>

      <div class="flag-row">
        <label class="focus-chip">
          <ToggleSwitch v-model="guidedForm.novogradnja" :true-value="1" :false-value="0" />
          <span>{{ t('predict.novogradnja') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch v-model="guidedForm.has_garaza" :true-value="1" :false-value="0" />
          <span>{{ t('predict.hasGaraza') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch v-model="guidedForm.has_klet" :true-value="1" :false-value="0" />
          <span>{{ t('predict.hasKlet') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch v-model="guidedForm.has_shramba" :true-value="1" :false-value="0" />
          <span>{{ t('predict.hasShramba') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch v-model="guidedForm.has_terasa" :true-value="1" :false-value="0" />
          <span>{{ t('predict.hasTerasa') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch v-model="guidedForm.stavba_je_dokoncana" :true-value="1" :false-value="0" />
          <span>{{ t('predict.stavbaDokoncana') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch v-model="guidedForm.ddv_vkljucen" :true-value="1" :false-value="0" />
          <span>{{ t('predict.ddvVkljucen') }}</span>
        </label>
      </div>

      <div class="actions-row">
        <Button
          icon="pi pi-search"
          :loading="loading"
          :label="t('analysis.analyzeButton')"
          @click="analyzeGuided"
        />
        <a :href="comparisonUrl" target="_blank" rel="noreferrer">
          <Button
            severity="contrast"
            outlined
            icon="pi pi-external-link"
            :label="t('analysis.compareOnPortal')"
          />
        </a>
      </div>
    </section>

    <section v-if="auth.isAdmin" class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow subtle">{{ t('analysis.bulkMode') }}</p>
          <h2>{{ t('analysis.advancedTitle') }}</h2>
        </div>
      </div>

      <Textarea
        v-model="advancedJson"
        rows="8"
        auto-resize
        :placeholder="t('analysis.jsonPlaceholder')"
      />

      <div class="actions-row">
        <Button
          severity="secondary"
          outlined
          icon="pi pi-file-edit"
          :label="t('analysis.loadSample')"
          @click="loadSample"
        />
        <Button
          severity="secondary"
          icon="pi pi-play"
          :loading="loading"
          :label="t('analysis.runBulk')"
          @click="analyzeAdvanced"
        />
      </div>
    </section>

    <p v-if="error" class="error-text">{{ error }}</p>

    <section v-if="loading" class="panel state-panel">
      <LoadingSpinner :label="t('common.loading')" />
    </section>

    <section v-else-if="!result" class="panel state-panel">
      <EmptyState icon="📈" :message="t('analysis.emptyState')" />
    </section>

    <template v-else>
      <section class="result-band">
        <article v-for="card in summaryCards" :key="card.label" class="result-card summary-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
        </article>
      </section>

      <section v-if="primaryListing" class="result-band">
        <article class="result-card">
          <span>{{ t('analysis.askingPrice') }}</span>
          <strong>{{ fmtCurrency(primaryListing.asking_price) }}</strong>
        </article>
        <article class="result-card">
          <span>{{ t('analysis.predictedPrice') }}</span>
          <strong>{{ fmtCurrency(primaryListing.predicted_price) }}</strong>
        </article>
        <article class="result-card">
          <span>{{ t('analysis.deviation') }}</span>
          <strong>{{ fmt(primaryListing.deviation_percent, 1) }}%</strong>
        </article>
        <article class="result-card">
          <span>{{ t('analysis.label') }}</span>
          <Tag
            :severity="labelSeverity(primaryListing.label)"
            :value="labelText(primaryListing.label)"
          />
        </article>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow subtle">{{ t('analysis.results') }}</p>
            <h2>{{ t('analysis.scoredListings') }}</h2>
          </div>

          <Button
            v-if="result.listings?.length"
            severity="contrast"
            outlined
            icon="pi pi-download"
            :label="t('analysis.export')"
            @click="exportToCSV(result.listings, 'analysis.csv')"
          />
        </div>

        <AppDataTable
          :rows="result.listings || []"
          :columns="resultColumns"
          row-key="municipality"
          :page-size="10"
          :empty-message="t('empty.noResults')"
        >
          <template #cell-municipality="{ row }">{{ row.municipality || '—' }}</template>
          <template #cell-property_type="{ row }">{{ formatType(row.property_type) }}</template>
          <template #cell-size="{ row }">{{ fmt(row.uporabna_povrsina || row.size_m2, 1) }} m²</template>
          <template #cell-floor="{ row }">{{ row.floor ?? '—' }}</template>
          <template #cell-asking_price="{ row }">{{ fmtCurrency(row.asking_price) }}</template>
          <template #cell-predicted_price="{ row }">{{ fmtCurrency(row.predicted_price) }}</template>
          <template #cell-deviation_percent="{ row }">{{ fmt(row.deviation_percent, 1) }}%</template>
          <template #cell-label="{ row }">
            <Tag :severity="labelSeverity(row.label)" :value="labelText(row.label)" />
          </template>
        </AppDataTable>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .analysis-page {
    display: grid;
    gap: 1rem;
  }

  .hero-shell,
  .panel,
  .result-card {
    border: 1px solid var(--border);
    border-radius: 1.5rem;
    background: var(--surface-soft-strong);
    box-shadow: var(--shadow-sm);
  }

  .hero-shell,
  .panel {
    padding: 1.15rem;
  }

  .hero-shell {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
  }

  .hero-shell h1,
  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  .hero-link {
    text-decoration: none;
  }

  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.9rem;
  }

  .threshold {
    min-width: 8rem;
  }

  .threshold label,
  .field span {
    display: block;
    margin-bottom: 0.35rem;
    color: var(--text-muted);
    font-size: 0.86rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .field {
    display: grid;
  }

  .field-error,
  .error-text {
    color: var(--danger);
  }

  .notes-field {
    grid-column: span 2;
  }

  .municipality-chip {
    align-content: flex-start;
    padding: 0.9rem 1rem;
    border: 1px solid var(--border);
    border-radius: 1rem;
    background: var(--surface-soft);
  }

  .municipality-chip strong {
    font-size: 1rem;
  }

  .actions-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 1rem;
  }

  .flag-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .focus-chip {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.7rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface-soft);
    color: var(--text);
    padding: 0.7rem 0.9rem;
    font-weight: 700;
  }

  .result-band {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .state-panel {
    display: grid;
    place-items: center;
    min-height: 14rem;
  }

  .result-card {
    padding: 1rem;
    display: grid;
    gap: 0.35rem;
  }

  .summary-card {
    background: var(--surface-soft);
  }

  .result-card span {
    color: var(--text-muted);
    font-size: 0.84rem;
  }

  .result-card strong {
    font-size: 1.25rem;
  }

  @media (max-width: 900px) {
    .hero-shell,
    .panel-head {
      flex-direction: column;
      align-items: stretch;
    }

    .form-grid,
    .result-band {
      grid-template-columns: 1fr;
    }
  }
</style>
