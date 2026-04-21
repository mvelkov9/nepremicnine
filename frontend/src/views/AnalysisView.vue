<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AutoComplete from 'primevue/autocomplete'
  import Button from 'primevue/button'
  import InputNumber from 'primevue/inputnumber'
  import Select from 'primevue/select'
  import Slider from 'primevue/slider'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tabs from 'primevue/tabs'
  import Textarea from 'primevue/textarea'
  import ToggleSwitch from 'primevue/toggleswitch'
  import api from '../composables/useApi'
  import { useAuthStore } from '../stores/auth'
  import { useReferenceDataStore } from '../stores/referenceData'
  import EmptyState from '../components/EmptyState.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import AnalysisWorkspaceHero from '../features/analysis/AnalysisWorkspaceHero.vue'
  import AnalysisResultsPanel from '../features/analysis/AnalysisResultsPanel.vue'
  import { useExport } from '../composables/useExport'
  import { useWorkbenchStore } from '../stores/workbench'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { getApiErrorMessage } from '../utils/apiError'
  import { useFormat } from '../composables/useFormat'
  import { municipalitySlug, normalizeMunicipalityName } from '../utils/municipality'
  import type {
    AnalysisHeroMetric,
    AnalysisHeroPill,
    AnalysisListing,
    AnalysisReadinessItem,
    AnalysisResultPayload,
    AnalysisSummaryCard,
  } from '../features/analysis/types'

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
  const { fmt, fmtCurrency, formatType } = useFormat()
  const auth = useAuthStore()
  const referenceData = useReferenceDataStore()
  const workbench = useWorkbenchStore()
  const { exportToCSV } = useExport()
  const route = useRoute()
  const router = useRouter()

  const defaultGuidedForm: GuidedAnalysisForm = {
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
  }
  const guidedForm = ref<GuidedAnalysisForm>({ ...defaultGuidedForm })
  const threshold = ref(15)
  const loading = ref(false)
  const error = ref('')
  const analysisTab = ref('guided')
  const result = ref<AnalysisResultPayload | null>(null)
  const advancedJson = ref('')
  const lastRunMode = ref<'guided' | 'advanced' | null>(null)
  const municipalitySuggestions = ref([])
  const naseljeSuggestions = ref([])
  const naseljeOptions = ref([])
  let activeNaseljeController: AbortController | null = null
  let naseljeRequestToken = 0

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
      label: formatType(value),
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

  const resultListings = computed(() =>
    Array.isArray(result.value?.listings) ? result.value.listings : [],
  )
  const resultStats = computed(() => {
    const listings = resultListings.value
    const deviations = listings
      .map((item) => Number(item.deviation_pct ?? item.deviation_percent))
      .filter((value) => Number.isFinite(value))
    const aligned = listings.filter((item) => item.label === 'market_aligned').length
    const averageDeviation = deviations.length
      ? deviations.reduce((sum, value) => sum + value, 0) / deviations.length
      : null

    return {
      count: listings.length,
      aligned,
      averageDeviation,
      alignedShare: listings.length ? (aligned / listings.length) * 100 : null,
    }
  })
  const resultSummaryCards = computed<AnalysisSummaryCard[]>(() => [
    {
      key: 'count',
      label: t('analysis.scoredListings'),
      value: String(resultStats.value.count || 0),
      hint: t('analysis.previewVerdictBody'),
    },
    {
      key: 'deviation',
      label: t('analysis.deviation'),
      value:
        resultStats.value.averageDeviation == null
          ? '—'
          : `${fmt(resultStats.value.averageDeviation, 1)}%`,
      hint: t('analysis.previewGapBody'),
    },
    {
      key: 'aligned',
      label: t('analysis.marketAligned'),
      value:
        resultStats.value.alignedShare == null ? '—' : `${fmt(resultStats.value.alignedShare, 0)}%`,
      hint: t('analysis.previewActionBody'),
    },
  ])
  const municipalityIndex = computed(
    () =>
      new Map(
        referenceData.municipalities.map((item) => [
          normalizeMunicipalityName(item.municipality),
          item,
        ]),
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
  const effectiveSize = computed(
    () => guidedForm.value.uporabna_povrsina || guidedForm.value.size_m2 || null,
  )
  const enabledSignalsCount = computed(
    () =>
      (
        [
          'novogradnja',
          'has_garaza',
          'has_klet',
          'has_shramba',
          'has_terasa',
          'stavba_je_dokoncana',
          'ddv_vkljucen',
        ] as BinaryGuidedField[]
      ).filter((field) => guidedForm.value[field] === 1).length,
  )
  const heroMetrics = computed<AnalysisHeroMetric[]>(() => [
    {
      key: 'coverage',
      title: t('analysis.previewCoverageTitle'),
      value: effectiveMunicipality.value || t('predict.municipalityPlaceholder'),
      body: selectedMunicipalityMeta.value?.region || t('analysis.previewCoverageBody'),
    },
    {
      key: 'threshold',
      title: t('analysis.previewThresholdTitle'),
      value: `${threshold.value}%`,
      body: t('analysis.previewThresholdBody'),
    },
    {
      key: 'signals',
      title: t('analysis.previewSignalsTitle'),
      value: `${enabledSignalsCount.value}`,
      body: t('analysis.previewSignalsBody'),
    },
  ])
  const heroPills = computed<AnalysisHeroPill[]>(() => [
    {
      key: 'property',
      label: t('predict.propertyType'),
      value: formatType(guidedForm.value.property_type),
    },
    {
      key: 'region',
      label: t('map.region'),
      value: selectedMunicipalityMeta.value?.region || t('common.noData'),
    },
    {
      key: 'size',
      label: t('predict.size'),
      value: effectiveSize.value ? `${fmt(effectiveSize.value, 1)} m²` : t('common.noData'),
    },
  ])
  const analysisPreviewCards = computed(() => [
    {
      key: 'verdict',
      icon: 'pi pi-compass',
      title: t('analysis.previewVerdictTitle'),
      body: t('analysis.previewVerdictBody'),
    },
    {
      key: 'gap',
      icon: 'pi pi-percentage',
      title: t('analysis.previewGapTitle'),
      body: t('analysis.previewGapBody'),
    },
    {
      key: 'action',
      icon: 'pi pi-arrow-right',
      title: t('analysis.previewActionTitle'),
      body: t('analysis.previewActionBody'),
    },
  ])
  const guidedReadiness = computed<AnalysisReadinessItem[]>(() => [
    {
      key: 'subject',
      ready: Boolean(guidedForm.value.property_type && effectiveSize.value),
      text:
        guidedForm.value.property_type && effectiveSize.value
          ? t('analysis.readinessSubjectReady')
          : t('analysis.readinessSubjectMissing'),
    },
    {
      key: 'pricing',
      ready: Boolean(guidedForm.value.asking_price),
      text: guidedForm.value.asking_price
        ? t('analysis.readinessPricingReady')
        : t('analysis.readinessPricingMissing'),
    },
    {
      key: 'location',
      ready: Boolean(effectiveMunicipality.value || guidedForm.value.naselje),
      text:
        effectiveMunicipality.value || guidedForm.value.naselje
          ? t('analysis.readinessLocationReady')
          : t('analysis.readinessLocationMissing'),
    },
  ])

  function queryNumber(value: unknown) {
    if (typeof value !== 'string' || !value) return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  function labelSeverity(label?: string | null) {
    if (label === 'overpriced') return 'danger'
    if (label === 'underpriced') return 'success'
    return 'info'
  }

  function labelText(label?: string | null) {
    if (label === 'market_aligned') return t('analysis.marketAligned')
    if (!label) return t('common.noData')
    return t(`analysis.${label}`)
  }

  function buildGuidedPayload() {
    const payload: Record<string, unknown> = { ...guidedForm.value }
    if (!payload.municipality && selectedNaseljeMeta.value?.municipality) {
      payload.municipality = selectedNaseljeMeta.value.municipality
    }
    if (selectedNaseljeMeta.value?.naselje) {
      payload.naselje = selectedNaseljeMeta.value.naselje
    }
    return Object.fromEntries(
      Object.entries(payload).filter(
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
    guidedForm.value = {
      ...defaultGuidedForm,
      ...guidedForm.value,
      naselje: typeof query.naselje === 'string' ? query.naselje : defaultGuidedForm.naselje,
      municipality:
        typeof query.municipality === 'string'
          ? query.municipality
          : defaultGuidedForm.municipality,
      property_type:
        typeof query.property_type === 'string'
          ? query.property_type
          : defaultGuidedForm.property_type,
    }

    const size = queryNumber(query.size_m2)
    guidedForm.value.size_m2 = size ?? defaultGuidedForm.size_m2

    const usable = queryNumber(query.uporabna_povrsina)
    guidedForm.value.uporabna_povrsina = usable ?? defaultGuidedForm.uporabna_povrsina

    const rooms = queryNumber(query.rooms)
    guidedForm.value.rooms = rooms ?? defaultGuidedForm.rooms

    const yearBuilt = queryNumber(query.year_built)
    guidedForm.value.year_built = yearBuilt ?? defaultGuidedForm.year_built

    const floor = queryNumber(query.floor)
    guidedForm.value.floor = floor ?? defaultGuidedForm.floor

    const askingPrice = queryNumber(query.asking_price)
    guidedForm.value.asking_price = askingPrice ?? defaultGuidedForm.asking_price
  }

  function searchMunicipalities(event) {
    const query = normalizeMunicipalityName(event.query || '')
    municipalitySuggestions.value = query
      ? referenceData.municipalities
          .filter((item) => normalizeMunicipalityName(item.municipality).includes(query))
          .map((item) => item.municipality)
          .slice(0, 12)
      : referenceData.municipalities.map((item) => item.municipality).slice(0, 12)
  }

  async function searchNaselja(event) {
    const requestToken = ++naseljeRequestToken
    const query = String(event.query || '').trim()
    activeNaseljeController?.abort()
    const controller = new AbortController()
    activeNaseljeController = controller

    try {
      const { data } = await api.get('/api/stats/naselja', {
        params: {
          q: query || undefined,
          municipality: guidedForm.value.municipality || undefined,
          limit: 12,
        },
        signal: controller.signal,
      })

      if (requestToken !== naseljeRequestToken || controller.signal.aborted) return

      naseljeOptions.value = (data || []).map((item) => ({
        ...item,
        label: `${item.naselje} (${item.municipality})`,
      }))
      naseljeSuggestions.value = naseljeOptions.value.map((item) => item.label)
    } catch {
      if (requestToken !== naseljeRequestToken || controller.signal.aborted) return
      naseljeOptions.value = []
      naseljeSuggestions.value = []
    } finally {
      if (activeNaseljeController === controller) {
        activeNaseljeController = null
      }
    }
  }

  async function analyzeGuided() {
    loading.value = true
    error.value = ''
    result.value = null
    lastRunMode.value = 'guided'

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
    lastRunMode.value = 'advanced'

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

  function retryAnalysis() {
    if (lastRunMode.value === 'advanced') {
      void analyzeAdvanced()
      return
    }
    void analyzeGuided()
  }

  const comparisonUrl = computed(() =>
    buildNepremicnineSearchUrl({
      municipality: guidedForm.value.municipality || selectedNaseljeMeta.value?.municipality,
      statisticalRegion: selectedMunicipalityMeta.value?.region,
      propertyType: guidedForm.value.property_type,
    }),
  )
  const guidedWorkspaceState = computed(() => ({
    page: 'analysis',
    tab: analysisTab.value,
    filters: buildGuidedPayload(),
  }))

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

  function openPredictionForListing(listing: AnalysisListing) {
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

  function openMunicipalityForListing(listing: AnalysisListing) {
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
    void referenceData.ensureLoaded()
  })

  onBeforeUnmount(() => {
    activeNaseljeController?.abort()
  })

  watch(
    () => route.query,
    (query) => {
      applyRouteQuery(query)
    },
  )

  watch(
    () => guidedForm.value.municipality,
    () => {
      naseljeRequestToken += 1
      activeNaseljeController?.abort()
      activeNaseljeController = null
      naseljeOptions.value = []
      naseljeSuggestions.value = []
    },
  )
</script>

<template>
  <div class="analysis-page">
    <AnalysisWorkspaceHero
      :kicker="t('analysis.consumerKicker')"
      :title="t('analysis.consumerTitle')"
      :body="t('analysis.consumerBody')"
      :note-title="t('analysis.previewTitle')"
      :note-body="t('analysis.previewBody')"
      :metrics="heroMetrics"
      :pills="heroPills"
      workspace-page="analysis"
      :workspace-state="guidedWorkspaceState"
      @watch="addCurrentToWatchlist"
      @open-prediction="openPrediction"
    >
      <template #actions>
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
      </template>
    </AnalysisWorkspaceHero>

    <Tabs v-model:value="analysisTab" class="analysis-tabs">
      <TabList>
        <Tab value="guided">{{ t('analysis.guidedTitle') }}</Tab>
        <Tab value="results">{{ t('analysis.results') }}</Tab>
        <Tab value="explore">{{ t('common.explore') }}</Tab>
        <Tab v-if="auth.isAdmin" value="bulk">{{ t('analysis.bulkMode') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="guided">
          <section class="analysis-tab-content">
            <SectionPanel :eyebrow="t('analysis.guidedCheck')" :title="t('analysis.guidedTitle')">
              <template #actions>
                <div class="threshold">
                  <label for="analysis-threshold">{{ t('analysis.threshold') }}</label>
                  <div class="threshold-control">
                    <InputNumber
                      v-model="threshold"
                      input-id="analysis-threshold"
                      :min="1"
                      :max="100"
                      suffix="%"
                    />
                    <Slider v-model="threshold" :min="1" :max="100" />
                  </div>
                </div>
              </template>

              <div class="guided-workbench">
                <div class="guided-summary">
                  <article class="summary-chip">
                    <span>{{ t('predict.naselje') }}</span>
                    <strong>{{ guidedForm.naselje || t('predict.naseljePlaceholder') }}</strong>
                  </article>
                  <article class="summary-chip">
                    <span>{{ t('predict.size') }}</span>
                    <strong
                      >{{ fmt(guidedForm.uporabna_povrsina || guidedForm.size_m2, 1) }} m²</strong
                    >
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

                <div class="guided-layout">
                  <div class="guided-form-stack">
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
                          fluid
                        />
                      </label>

                      <label class="field">
                        <span>{{ t('predict.size') }}</span>
                        <InputNumber v-model="guidedForm.size_m2" :min="1" suffix=" m²" fluid />
                      </label>

                      <label class="field">
                        <span>{{ t('predict.uporabnaPovrsina') }}</span>
                        <InputNumber
                          v-model="guidedForm.uporabna_povrsina"
                          :min="0"
                          suffix=" m²"
                          fluid
                        />
                      </label>

                      <label class="field">
                        <span>{{ t('predict.rooms') }}</span>
                        <InputNumber v-model="guidedForm.rooms" :min="0" :step="0.5" fluid />
                      </label>

                      <label class="field">
                        <span>{{ t('predict.yearBuilt') }}</span>
                        <InputNumber
                          v-model="guidedForm.year_built"
                          :min="1800"
                          :max="2100"
                          fluid
                        />
                      </label>

                      <label class="field">
                        <span>{{ t('predict.floor') }}</span>
                        <InputNumber v-model="guidedForm.floor" :min="-2" :max="60" fluid />
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
                          fluid
                        />
                      </label>

                      <label class="field">
                        <span>{{ t('analysis.askingPrice') }}</span>
                        <InputNumber
                          v-model="guidedForm.asking_price"
                          mode="currency"
                          currency="EUR"
                          locale="sl-SI"
                          fluid
                        />
                      </label>

                      <label class="field notes-field">
                        <span>{{ t('analysis.contextNotes') }}</span>
                        <Textarea v-model="guidedForm.notes" rows="3" auto-resize />
                      </label>
                    </div>

                    <details class="analysis-fold">
                      <summary>{{ t('analysis.previewSignalsTitle') }}</summary>
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
                    </details>
                  </div>

                  <aside class="workspace-status">
                    <div class="guided-readiness">
                      <article
                        v-for="item in guidedReadiness"
                        :key="item.key"
                        class="guided-readiness-item"
                        :class="{ ready: item.ready }"
                      >
                        <i
                          :class="item.ready ? 'pi pi-check-circle' : 'pi pi-circle'"
                          aria-hidden="true"
                        ></i>
                        <span>{{ item.text }}</span>
                      </article>
                    </div>

                    <div class="actions-row">
                      <Button
                        icon="pi pi-search"
                        :loading="loading"
                        :label="t('analysis.analyzeButton')"
                        @click="analyzeGuided"
                      />
                    </div>
                  </aside>
                </div>
              </div>
            </SectionPanel>
          </section>
        </TabPanel>

        <TabPanel value="results">
          <section class="analysis-tab-content">
            <div v-if="error" class="state-card state-card-stack" role="alert">
              <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
              <div class="state-card-actions">
                <Button
                  size="small"
                  severity="secondary"
                  outlined
                  icon="pi pi-refresh"
                  :label="t('common.retry')"
                  @click="retryAnalysis"
                />
              </div>
            </div>

            <AnalysisResultsPanel
              v-if="result"
              :eyebrow="t('analysis.results')"
              :title="t('analysis.scoredListings')"
              :result="result"
              :primary-listing="resultListings[0] || null"
              :summary-cards="resultSummaryCards"
              :comparison-url="comparisonUrl"
              @export="exportToCSV(result.listings || [], 'analysis.csv')"
              @open-prediction="openPredictionForListing"
              @open-municipality="openMunicipalityForListing"
            />

            <SectionPanel
              v-else
              class="preview-panel"
              :eyebrow="t('analysis.previewTitle')"
              :title="t('analysis.previewHeading')"
            >
              <div class="guided-readiness">
                <article
                  v-for="item in guidedReadiness"
                  :key="item.key"
                  class="guided-readiness-item"
                  :class="{ ready: item.ready }"
                >
                  <i
                    :class="item.ready ? 'pi pi-check-circle' : 'pi pi-circle'"
                    aria-hidden="true"
                  ></i>
                  <span>{{ item.text }}</span>
                </article>
              </div>
            </SectionPanel>
          </section>
        </TabPanel>

        <TabPanel value="explore">
          <section class="analysis-tab-content">
            <SectionPanel
              class="analysis-explore-panel"
              :eyebrow="t('nav.market')"
              :title="t('analysis.previewHeading')"
            >
              <div class="analysis-preview-grid">
                <article
                  v-for="card in analysisPreviewCards"
                  :key="card.key"
                  class="analysis-preview-card"
                >
                  <span class="preview-icon"><i :class="card.icon"></i></span>
                  <div>
                    <strong>{{ card.title }}</strong>
                    <p>{{ card.body }}</p>
                  </div>
                </article>
              </div>

              <div class="analysis-explore-actions">
                <a :href="comparisonUrl" target="_blank" rel="noreferrer" class="hero-link">
                  <Button
                    severity="contrast"
                    outlined
                    icon="pi pi-external-link"
                    :label="t('analysis.compareOnPortal')"
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
                  icon="pi pi-building"
                  :label="t('map.openMunicipality')"
                  @click="openMunicipality"
                />
              </div>
            </SectionPanel>
          </section>
        </TabPanel>

        <TabPanel v-if="auth.isAdmin" value="bulk">
          <section class="analysis-tab-content">
            <SectionPanel
              class="analysis-advanced-panel"
              :eyebrow="t('analysis.bulkMode')"
              :title="t('analysis.advancedTitle')"
            >
              <details class="analysis-fold">
                <summary>{{ t('analysis.advancedTitle') }}</summary>
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
              </details>
            </SectionPanel>
          </section>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
  .analysis-page {
    display: grid;
    gap: var(--space-section);
    --page-accent: var(--primary);
    --page-accent-2: var(--accent);
  }

  .analysis-tabs,
  .analysis-tab-content {
    display: grid;
    gap: 1rem;
  }

  .analysis-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 18%);
    border-radius: var(--radius-lg);
    background: color-mix(in srgb, var(--surface-strong) 92%, var(--primary-overlay) 8%);
    box-shadow: 0 10px 22px color-mix(in srgb, var(--shadow-color) 8%, transparent);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .analysis-tabs :deep(.p-tabpanels) {
    padding-top: 0.15rem;
  }

  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }

  .state-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .result-card {
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    border-radius: var(--radius-md);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
  }

  .hero-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
    align-items: stretch;
    gap: 1.15rem;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--page-accent) 16%, transparent),
        transparent 30%
      ),
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--page-accent-2) 11%, transparent),
        transparent 26%
      ),
      var(--surface-hero);
  }

  .panel {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 88%, transparent),
        transparent 38%
      ),
      var(--surface-panel);
  }

  .hero-shell h1 {
    margin: 0;
    font-family: var(--font-display);
    text-wrap: balance;
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
  .guided-summary,
  .hero-story-grid,
  .analysis-preview-grid,
  .guided-readiness {
    display: grid;
    gap: 0.85rem;
  }

  .hero-side {
    align-content: space-between;
    padding: 0.15rem 0;
  }

  .hero-metric-stack,
  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: stretch;
  }

  .analysis-explore-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .hero-pill-grid,
  .guided-summary {
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  }

  .hero-metric-stack {
    flex-direction: column;
  }

  .hero-story-grid,
  .analysis-preview-grid {
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  }

  .hero-pill,
  .summary-chip,
  .hero-story-card,
  .analysis-preview-card,
  .hero-note,
  .guided-readiness-item {
    padding: 0.9rem 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--page-accent) 8%
    );
    box-shadow: var(--shadow-sm);
  }

  .hero-pill {
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 90%,
      var(--page-accent-2) 10%
    );
  }

  .hero-pill span,
  .summary-chip span,
  .hero-story-card span {
    display: block;
    margin-bottom: 0.3rem;
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .hero-pill strong,
  .summary-chip strong,
  .hero-story-card strong,
  .analysis-preview-card strong {
    display: block;
    font-size: 1rem;
    line-height: 1.2;
  }

  .hero-story-card p,
  .analysis-preview-card p,
  .hero-note p {
    margin: 0.3rem 0 0;
    color: var(--text-muted);
  }

  .guided-workbench {
    display: grid;
    gap: 1rem;
  }

  .guided-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(20rem, 0.92fr);
    gap: 1rem;
    align-items: start;
  }

  .guided-form-stack {
    display: grid;
    gap: 1rem;
  }

  .hero-note {
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--warning) 8%
    );
  }

  .analysis-advanced-panel {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-subtle) 88%, transparent),
        transparent 24%
      ),
      var(--surface-panel);
  }

  .results-overview {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: 0.85rem;
    margin-bottom: 1rem;
  }

  .results-summary-card {
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--secondary) 24%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 93%,
      var(--page-accent-2) 7%
    );
    box-shadow: var(--shadow-sm);
  }

  .results-summary-card span {
    display: block;
    margin-bottom: 0.25rem;
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .results-summary-card strong {
    display: block;
    font-size: 1.4rem;
    line-height: 1.1;
  }

  .results-summary-card p {
    margin: 0.35rem 0 0;
    color: var(--text-muted);
  }

  .threshold {
    min-width: 8rem;
  }

  .threshold-control {
    display: grid;
    gap: 0.55rem;
    min-width: min(21rem, 42vw);
  }

  .threshold label,
  .field span {
    display: block;
    margin-bottom: 0.35rem;
    color: var(--text-muted);
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: 1rem;
  }

  .field {
    display: grid;
    gap: 0.35rem;
    min-width: 0;
  }

  .field :deep(.p-autocomplete),
  .field :deep(.p-inputnumber),
  .field :deep(.p-select),
  .field :deep(.p-inputtext),
  .field :deep(textarea) {
    width: 100%;
  }

  .field :deep(.p-autocomplete),
  .field :deep(.p-inputnumber),
  .field :deep(.p-select) {
    min-height: 3.15rem;
  }

  .field :deep(.p-inputtext),
  .field :deep(.p-autocomplete-input),
  .field :deep(.p-inputnumber-input),
  .field :deep(.p-select-label),
  .field :deep(textarea) {
    font-size: 0.98rem;
  }

  .field :deep(.p-inputtext),
  .field :deep(.p-autocomplete-input),
  .field :deep(.p-inputnumber-input) {
    min-height: 3.15rem;
    padding-block: 0.82rem;
  }

  .field :deep(.p-select-label) {
    padding-block: 0.82rem;
  }

  .notes-field :deep(textarea) {
    min-height: 8.5rem;
  }

  .workspace-status {
    position: sticky;
    top: 5.9rem;
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--page-accent-2) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      color-mix(in srgb, var(--surface-panel) 92%, var(--page-accent-2) 8%);
    box-shadow: var(--shadow-sm);
  }

  .workspace-status .actions-row {
    margin-top: 0;
  }

  .notes-field {
    grid-column: 1 / -1;
  }

  .actions-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 1rem;
  }

  .analysis-fold {
    display: grid;
    gap: 0.8rem;
  }

  .analysis-fold > summary {
    list-style: none;
    cursor: pointer;
    user-select: none;
    padding: 0.75rem 0.95rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--page-accent) 40%);
    background:
      linear-gradient(
        125deg,
        color-mix(in srgb, var(--page-accent-2) 12%, transparent),
        transparent 55%
      ),
      var(--surface-subtle);
    color: var(--text-soft);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .analysis-fold > summary::-webkit-details-marker {
    display: none;
  }

  .analysis-fold[open] > summary {
    color: var(--text);
    border-color: color-mix(in srgb, var(--border) 52%, var(--page-accent) 48%);
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
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    border-radius: 999px;
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--page-accent-2) 8%
    );
    color: var(--text);
    padding: 0.7rem 0.9rem;
    font-weight: 700;
    box-shadow: var(--shadow-sm);
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease,
      background 0.16s ease;
  }

  .focus-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 88%,
      var(--page-accent-2) 12%
    );
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .preview-panel {
    display: grid;
    gap: 1rem;
  }

  .analysis-preview-card,
  .guided-readiness-item {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.85rem;
    align-items: start;
  }

  .preview-icon {
    display: inline-grid;
    place-items: center;
    width: 2.55rem;
    height: 2.55rem;
    border-radius: var(--radius-xs);
    background: color-mix(
      in srgb,
      var(--primary) 14%,
      var(--surface-card-strong, var(--surface-strong))
    );
    color: var(--primary-strong);
  }

  .guided-readiness {
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  }

  .guided-readiness-item {
    align-items: center;
    border-radius: 999px;
    padding: 0.85rem 1rem;
    font-weight: 700;
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 94%,
      transparent
    );
  }

  .guided-readiness-item i {
    color: var(--text-soft);
  }

  .guided-readiness-item.ready {
    border-color: color-mix(in srgb, var(--success) 26%, var(--border));
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--success) 8%
    );
  }

  .guided-readiness-item.ready i {
    color: var(--success-strong, var(--success));
  }

  .result-band {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.85rem;
    margin-bottom: 0.9rem;
  }

  .result-card {
    padding: 1rem;
    display: grid;
    gap: 0.35rem;
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 94%,
      transparent
    );
  }

  .result-card.tone-primary {
    background: color-mix(in srgb, var(--surface-soft-strong) 94%, var(--primary) 6%);
  }

  .result-card.tone-warning {
    background: color-mix(in srgb, var(--surface-soft-strong) 94%, var(--warning) 6%);
  }

  .result-card.tone-label {
    background: color-mix(in srgb, var(--surface-soft-strong) 94%, var(--secondary) 6%);
  }

  .result-card span {
    color: var(--text-muted);
    font-size: var(--text-sm);
  }

  .result-card strong {
    font-size: 1.25rem;
  }

  @media (max-width: 1040px) {
    .hero-shell {
      grid-template-columns: 1fr;
    }

    .guided-layout {
      grid-template-columns: 1fr;
    }

    .workspace-status {
      position: static;
    }

    .form-grid {
      grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
    }
  }

  @media (max-width: 640px) {
    .analysis-page {
      gap: 1rem;
    }

    .hero-shell,
    .result-band,
    .results-overview {
      gap: 0.7rem;
    }

    .hero-story-card,
    .hero-pill,
    .summary-chip,
    .analysis-preview-card,
    .results-summary-card {
      padding: 0.85rem 0.9rem;
    }

    .form-grid {
      grid-template-columns: 1fr;
    }

    .notes-field {
      grid-column: auto;
    }

    .actions-row,
    .analysis-explore-actions,
    .hero-actions {
      width: 100%;
    }
  }
</style>
