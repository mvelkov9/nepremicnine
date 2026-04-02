<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AutoComplete from 'primevue/autocomplete'
  import Button from 'primevue/button'
  import DataTable from 'primevue/datatable'
  import Column from 'primevue/column'
  import InputNumber from 'primevue/inputnumber'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import Textarea from 'primevue/textarea'
  import ToggleSwitch from 'primevue/toggleswitch'
  import api from '../composables/useApi'
  import { useAuthStore } from '../stores/auth'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useExport } from '../composables/useExport'
  import { useWorkbenchStore } from '../stores/workbench'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { municipalitySlug, normalizeMunicipalityName } from '../utils/municipality'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  interface GuidedAnalysisForm {
    naselje: string
    municipality: string
    ime_ko: string
    property_type: string
    size_m2: number
    uporabna_povrsina: number | null
    rooms: number | null
    year_built: number | null
    floor: number | null
    lega_v_stavbi: string
    novogradnja: number
    has_garaza: number
    has_klet: number
    has_shramba: number
    has_terasa: number
    stavba_je_dokoncana: number
    ddv_vkljucen: number
    asking_price: number | null
    notes: string
  }

  type BinaryGuidedField =
    | 'novogradnja'
    | 'has_garaza'
    | 'has_klet'
    | 'has_shramba'
    | 'has_terasa'
    | 'stavba_je_dokoncana'
    | 'ddv_vkljucen'

  const { t } = useI18n()
  const auth = useAuthStore()
  const workbench = useWorkbenchStore()
  const { exportToCSV } = useExport()
  const route = useRoute()
  const router = useRouter()

  const guidedForm = ref<GuidedAnalysisForm>({
    naselje: '',
    municipality: '',
    ime_ko: '',
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
  })
  const threshold = ref(15)
  const loading = ref(false)
  const error = ref('')
  const result = ref(null)
  const advancedJson = ref('')
  const municipalities = ref([])
  const municipalitySuggestions = ref([])
  const naseljeSuggestions = ref([])
  const naseljeOptions = ref([])

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

  const propertyTypeOptions = computed(() =>
    propertyTypes.map((value) => ({
      label: getPropertyTypeLabel(value, t),
      value,
    })),
  )
  const guidedPresets = [
    {
      key: 'apartment',
      label: 'workbench.apartmentPreset',
      values: { property_type: 'stanovanje', size_m2: 70, rooms: 3, asking_price: 280000 },
    },
    {
      key: 'house',
      label: 'workbench.housePreset',
      values: {
        property_type: 'hisa',
        size_m2: 160,
        rooms: 5,
        asking_price: 360000,
        has_garaza: 1,
      },
    },
  ]

  const primaryListing = computed(() => result.value?.listings?.[0] || null)
  const municipalityIndex = computed(
    () =>
      new Map(
        municipalities.value.map((item) => [normalizeMunicipalityName(item.municipality), item]),
      ),
  )
  const selectedMunicipalityMeta = computed(() => {
    const municipality =
      guidedForm.value.municipality || selectedNaseljeMeta.value?.municipality || ''
    return municipalityIndex.value.get(normalizeMunicipalityName(municipality))
  })
  const selectedNaseljeMeta = computed(() => {
    const target = guidedForm.value.naselje.trim().toLowerCase()
    return (
      naseljeOptions.value.find(
        (item) =>
          item.naselje.trim().toLowerCase() === target ||
          String(item.label || '')
            .trim()
            .toLowerCase() === target,
      ) || null
    )
  })

  const effectiveMunicipality = computed(
    () => guidedForm.value.municipality || selectedNaseljeMeta.value?.municipality || '',
  )

  function queryNumber(value: unknown) {
    if (typeof value !== 'string' || !value) return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

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
    if (!guidedForm.value.municipality && selectedNaseljeMeta.value?.municipality) {
      guidedForm.value.municipality = selectedNaseljeMeta.value.municipality
    }
    if (selectedNaseljeMeta.value?.naselje) {
      guidedForm.value.naselje = selectedNaseljeMeta.value.naselje
    }
    return Object.fromEntries(
      Object.entries(guidedForm.value).filter(
        ([key, value]) => key !== 'notes' && value !== null && value !== '',
      ),
    )
  }

  function applyGuidedPreset(values: Partial<GuidedAnalysisForm>) {
    guidedForm.value = {
      ...guidedForm.value,
      ...values,
    }
  }

  function applyRouteQuery(query = route.query) {
    if (typeof query.naselje === 'string') guidedForm.value.naselje = query.naselje
    if (typeof query.municipality === 'string') guidedForm.value.municipality = query.municipality
    if (typeof query.property_type === 'string')
      guidedForm.value.property_type = query.property_type

    const size = queryNumber(query.size_m2)
    if (size != null) guidedForm.value.size_m2 = size

    const usable = queryNumber(query.uporabna_povrsina)
    if (usable != null) guidedForm.value.uporabna_povrsina = usable

    const rooms = queryNumber(query.rooms)
    if (rooms != null) guidedForm.value.rooms = rooms

    const yearBuilt = queryNumber(query.year_built)
    if (yearBuilt != null) guidedForm.value.year_built = yearBuilt

    const floor = queryNumber(query.floor)
    if (floor != null) guidedForm.value.floor = floor

    const askingPrice = queryNumber(query.asking_price)
    if (askingPrice != null) guidedForm.value.asking_price = askingPrice
  }

  async function fetchMunicipalities() {
    try {
      const { data } = await api.get('/api/regions/municipalities')
      municipalities.value = data || []
    } catch {
      municipalities.value = []
    }
  }

  function searchMunicipalities(event) {
    const query = normalizeMunicipalityName(event.query || '')
    municipalitySuggestions.value = query
      ? municipalities.value
          .filter((item) => normalizeMunicipalityName(item.municipality).includes(query))
          .map((item) => item.municipality)
          .slice(0, 12)
      : municipalities.value.map((item) => item.municipality).slice(0, 12)
  }

  async function searchNaselja(event) {
    const query = String(event.query || '').trim()
    try {
      const { data } = await api.get('/api/stats/naselja', {
        params: {
          q: query || undefined,
          municipality: guidedForm.value.municipality || undefined,
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

  async function analyzeGuided() {
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const { data } = await api.post('/api/analysis/score', {
        listings: [buildGuidedPayload()],
        threshold: threshold.value,
      })
      result.value = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  async function analyzeAdvanced() {
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const parsed = JSON.parse(advancedJson.value)
      const listings = Array.isArray(parsed) ? parsed : [parsed]
      const { data } = await api.post('/api/analysis/score', {
        listings,
        threshold: threshold.value,
      })
      result.value = data
    } catch (e) {
      error.value = e instanceof SyntaxError ? t('analysis.invalidJson') : getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  function loadSample() {
    advancedJson.value = JSON.stringify(
      [
        {
          naselje: 'Ljubljana',
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
          naselje: 'Maribor',
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
      municipality: guidedForm.value.municipality || selectedNaseljeMeta.value?.municipality,
      statisticalRegion: selectedMunicipalityMeta.value?.region,
      propertyType: guidedForm.value.property_type,
    }),
  )

  function toggleValue(field: BinaryGuidedField) {
    return guidedForm.value[field] === 1
  }

  function updateToggle(field: BinaryGuidedField, checked: boolean) {
    guidedForm.value[field] = checked ? 1 : 0
  }

  function openPrediction() {
    router.push({
      name: 'prediction',
      query: {
        municipality: effectiveMunicipality.value || undefined,
        naselje: guidedForm.value.naselje || undefined,
        property_type: guidedForm.value.property_type || undefined,
        size_m2: guidedForm.value.uporabna_povrsina || guidedForm.value.size_m2 || undefined,
        year_built:
          guidedForm.value.year_built != null ? String(guidedForm.value.year_built) : undefined,
      },
    })
  }

  function openPredictionForListing(listing: any) {
    router.push({
      name: 'prediction',
      query: {
        municipality: listing.municipality || effectiveMunicipality.value || undefined,
        naselje: listing.naselje || undefined,
        property_type: listing.property_type || guidedForm.value.property_type || undefined,
        size_m2:
          listing.uporabna_povrsina || listing.size_m2
            ? String(listing.uporabna_povrsina || listing.size_m2)
            : undefined,
        year_built: listing.year_built != null ? String(listing.year_built) : undefined,
        floor: listing.floor != null ? String(listing.floor) : undefined,
        price_eur: listing.asking_price != null ? String(listing.asking_price) : undefined,
      },
    })
  }

  function openMarketExplorer() {
    router.push({
      name: 'market',
      query: {
        tab: 'transactions',
        municipality: effectiveMunicipality.value || undefined,
        property_type: guidedForm.value.property_type || undefined,
      },
    })
  }

  function openMapExplorer() {
    router.push({
      name: 'map',
      query: {
        municipality: effectiveMunicipality.value || undefined,
        region: selectedMunicipalityMeta.value?.region || undefined,
        property_type: guidedForm.value.property_type || undefined,
        view: 'transactions',
      },
    })
  }

  function openMunicipality() {
    if (!effectiveMunicipality.value) return
    router.push({
      path: `/obcine/${municipalitySlug(effectiveMunicipality.value)}`,
      query: {
        property_type: guidedForm.value.property_type || undefined,
      },
    })
  }

  async function addCurrentToWatchlist() {
    if (!effectiveMunicipality.value) return
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: municipalitySlug(effectiveMunicipality.value),
      display_label: effectiveMunicipality.value,
      metadata: {
        link: `/obcine/${municipalitySlug(effectiveMunicipality.value)}`,
        region: selectedMunicipalityMeta.value?.region || null,
      },
    })
  }

  function openMunicipalityForListing(listing: any) {
    if (!listing?.municipality) return
    router.push({
      path: `/obcine/${municipalitySlug(listing.municipality)}`,
      query: {
        property_type: listing.property_type || undefined,
      },
    })
  }

  onMounted(() => {
    applyRouteQuery()
    void fetchMunicipalities()
  })

  watch(
    () => route.query,
    (query) => {
      applyRouteQuery(query)
    },
  )
</script>

<template>
  <div class="analysis-page">
    <section class="hero-shell">
      <div class="hero-copy">
        <p class="eyebrow">{{ t('analysis.consumerKicker') }}</p>
        <h1>{{ t('analysis.consumerTitle') }}</h1>
        <p class="muted">{{ t('analysis.consumerBody') }}</p>
      </div>

      <div class="hero-side">
        <div class="hero-pill-grid">
          <article class="hero-pill">
            <span>{{ t('predict.propertyType') }}</span>
            <strong>{{ formatType(guidedForm.property_type) }}</strong>
          </article>
          <article class="hero-pill">
            <span>{{ t('map.region') }}</span>
            <strong>{{ selectedMunicipalityMeta?.region || t('common.noData') }}</strong>
          </article>
          <article class="hero-pill">
            <span>{{ t('analysis.threshold') }}</span>
            <strong>{{ threshold }}%</strong>
          </article>
        </div>

        <a :href="comparisonUrl" target="_blank" rel="noreferrer" class="hero-link">
          <Button
            severity="secondary"
            outlined
            icon="pi pi-external-link"
            :label="t('analysis.compareOnPortal')"
          />
        </a>
        <div class="hero-actions">
          <SavedWorkspaceMenu
            page="analysis"
            :state="{ page: 'analysis', filters: buildGuidedPayload() }"
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
            icon="pi pi-calculator"
            :label="t('predict.title')"
            @click="openPrediction"
          />
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
            icon="pi pi-building"
            :label="t('map.openMunicipality')"
            @click="openMunicipality"
          />
        </div>
      </div>
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

      <div class="guided-summary">
        <article class="summary-chip">
          <span>{{ t('predict.naselje') }}</span>
          <strong>{{ guidedForm.naselje || t('predict.naseljePlaceholder') }}</strong>
        </article>
        <article class="summary-chip">
          <span>{{ t('predict.size') }}</span>
          <strong>{{ fmt(guidedForm.uporabna_povrsina || guidedForm.size_m2, 1) }} m²</strong>
        </article>
        <article class="summary-chip">
          <span>{{ t('analysis.askingPrice') }}</span>
          <strong>{{ fmtCurrency(guidedForm.asking_price) }}</strong>
        </article>
      </div>

      <div class="actions-row">
        <Button
          v-for="preset in guidedPresets"
          :key="preset.key"
          severity="secondary"
          outlined
          :label="t(preset.label)"
          @click="applyGuidedPreset(preset.values)"
        />
      </div>

      <div class="form-grid">
        <label class="field">
          <span>{{ t('predict.naselje') }}</span>
          <AutoComplete
            v-model="guidedForm.naselje"
            :suggestions="naseljeSuggestions"
            :placeholder="t('predict.naseljePlaceholder')"
            dropdown
            fluid
            @complete="searchNaselja"
          />
        </label>

        <label class="field">
          <span>{{ t('predict.municipality') }}</span>
          <AutoComplete
            v-model="guidedForm.municipality"
            :suggestions="municipalitySuggestions"
            :placeholder="t('predict.municipalityPlaceholder')"
            dropdown
            fluid
            @complete="searchMunicipalities"
          />
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
          <InputNumber v-model="guidedForm.size_m2" :min="1" suffix=" m²" />
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
          />
        </label>

        <label class="field notes-field">
          <span>{{ t('analysis.contextNotes') }}</span>
          <InputText v-model="guidedForm.notes" />
        </label>
      </div>

      <div class="flag-row">
        <label class="focus-chip">
          <ToggleSwitch
            :model-value="toggleValue('novogradnja')"
            @update:model-value="updateToggle('novogradnja', $event)"
          />
          <span>{{ t('predict.novogradnja') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_garaza')"
            @update:model-value="updateToggle('has_garaza', $event)"
          />
          <span>{{ t('predict.hasGaraza') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_klet')"
            @update:model-value="updateToggle('has_klet', $event)"
          />
          <span>{{ t('predict.hasKlet') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_shramba')"
            @update:model-value="updateToggle('has_shramba', $event)"
          />
          <span>{{ t('predict.hasShramba') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_terasa')"
            @update:model-value="updateToggle('has_terasa', $event)"
          />
          <span>{{ t('predict.hasTerasa') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch
            :model-value="toggleValue('stavba_je_dokoncana')"
            @update:model-value="updateToggle('stavba_je_dokoncana', $event)"
          />
          <span>{{ t('predict.stavbaDokoncana') }}</span>
        </label>
        <label class="focus-chip">
          <ToggleSwitch
            :model-value="toggleValue('ddv_vkljucen')"
            @update:model-value="updateToggle('ddv_vkljucen', $event)"
          />
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

    <template v-if="result">
      <section v-if="primaryListing" class="result-band">
        <article class="result-card tone-default">
          <span>{{ t('analysis.askingPrice') }}</span>
          <strong>{{ fmtCurrency(primaryListing.asking_price) }}</strong>
        </article>
        <article class="result-card tone-primary">
          <span>{{ t('analysis.predictedPrice') }}</span>
          <strong>{{ fmtCurrency(primaryListing.predicted_price) }}</strong>
        </article>
        <article class="result-card tone-warning">
          <span>{{ t('analysis.deviation') }}</span>
          <strong
            >{{ fmt(primaryListing.deviation_pct ?? primaryListing.deviation_percent, 1) }}%</strong
          >
        </article>
        <article class="result-card tone-label">
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

        <DataTable
          :value="result.listings || []"
          paginator
          :rows="10"
          size="small"
          striped-rows
          responsive-layout="scroll"
          table-style="min-width: 100%"
        >
          <Column :header="t('dashboard.municipality')">
            <template #body="{ data }">{{ data.municipality || '—' }}</template>
          </Column>
          <Column :header="t('predict.propertyType')">
            <template #body="{ data }">{{ formatType(data.property_type) }}</template>
          </Column>
          <Column :header="t('predict.size')">
            <template #body="{ data }">
              {{ fmt(data.uporabna_povrsina || data.size_m2, 1) }} m²
            </template>
          </Column>
          <Column :header="t('predict.floor')">
            <template #body="{ data }">{{ data.floor ?? '—' }}</template>
          </Column>
          <Column :header="t('analysis.askingPrice')">
            <template #body="{ data }">{{ fmtCurrency(data.asking_price) }}</template>
          </Column>
          <Column :header="t('analysis.predictedPrice')">
            <template #body="{ data }">{{ fmtCurrency(data.predicted_price) }}</template>
          </Column>
          <Column :header="t('analysis.deviation')">
            <template #body="{ data }">
              {{ fmt(data.deviation_pct ?? data.deviation_percent, 1) }}%
            </template>
          </Column>
          <Column :header="t('analysis.label')">
            <template #body="{ data }">
              <Tag :severity="labelSeverity(data.label)" :value="labelText(data.label)" />
            </template>
          </Column>
          <Column :header="t('common.actions')">
            <template #body="{ data }">
              <div class="row-actions">
                <Button
                  size="small"
                  severity="secondary"
                  text
                  icon="pi pi-calculator"
                  :label="t('predict.title')"
                  @click="openPredictionForListing(data)"
                />
                <Button
                  v-if="data.municipality"
                  size="small"
                  severity="secondary"
                  text
                  icon="pi pi-building"
                  :label="t('map.openMunicipality')"
                  @click="openMunicipalityForListing(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
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
    background: linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft-strong));
    box-shadow: var(--shadow-sm);
  }

  .hero-shell,
  .panel {
    padding: 1.15rem;
  }

  .hero-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
    align-items: stretch;
    gap: 1rem;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 76%, transparent),
        var(--surface-soft-strong)
      ),
      var(--surface-soft-strong);
  }

  .hero-shell h1,
  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  .hero-link {
    text-decoration: none;
  }

  .hero-copy {
    display: grid;
    gap: 0.55rem;
    align-content: start;
  }

  .hero-copy p {
    margin: 0;
  }

  .hero-side,
  .hero-pill-grid,
  .guided-summary {
    display: grid;
    gap: 0.85rem;
  }

  .hero-side {
    align-content: space-between;
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .hero-pill-grid,
  .guided-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .hero-pill,
  .summary-chip {
    padding: 0.9rem 1rem;
    border-radius: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--primary) 28%);
    background: color-mix(in srgb, var(--surface-strong) 86%, white 14%);
  }

  .hero-pill span,
  .summary-chip span {
    display: block;
    margin-bottom: 0.3rem;
    color: var(--text-soft);
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .hero-pill strong,
  .summary-chip strong {
    display: block;
    font-size: 1rem;
    line-height: 1.2;
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
    gap: 0.35rem;
  }

  .notes-field {
    grid-column: span 2;
  }

  .actions-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 1rem;
  }

  .row-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
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
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .focus-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 28%, transparent);
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .result-band {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .result-card {
    padding: 1rem;
    display: grid;
    gap: 0.35rem;
  }

  .result-card.tone-primary {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 82%, transparent),
        var(--surface-soft-strong)
      ),
      var(--surface-soft-strong);
  }

  .result-card.tone-warning {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--warning-overlay) 80%, transparent),
        var(--surface-soft-strong)
      ),
      var(--surface-soft-strong);
  }

  .result-card.tone-label {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-dark-muted) 100%, transparent),
        var(--surface-soft-strong)
      ),
      var(--surface-soft-strong);
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
      grid-template-columns: 1fr;
    }

    .form-grid,
    .result-band,
    .hero-pill-grid,
    .guided-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
