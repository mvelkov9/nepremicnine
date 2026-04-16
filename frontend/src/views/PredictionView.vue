<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useLocalStorage } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import api from '../composables/useApi'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import PageHeader from '../components/PageHeader.vue'
  import PredictionComparables from '../components/prediction/PredictionComparables.vue'
  import PredictionForm from '../components/prediction/PredictionForm.vue'
  import PredictionResultSummary from '../components/prediction/PredictionResultSummary.vue'
  import FeatureImportanceChart from '../components/charts/FeatureImportanceChart.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useExport } from '../composables/useExport'
  import { useReferenceDataStore } from '../stores/referenceData'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { getApiErrorMessage } from '../utils/apiError'
  import { useFormat } from '../composables/useFormat'
  import { formatDateTime } from '../utils/format'
  import { municipalitySlug, normalizeMunicipalityName } from '../utils/municipality'
  import type { TransactionRecord } from '../types/api'
  import type {
    PredictionFormData,
    PredictionHistoryItem,
    PredictionReadinessItem,
    PredictionResultPayload,
    PredictionRouteQuery,
    PredictionSummaryCard,
  } from '../components/prediction/types'

  const { t } = useI18n()
  const { fmt, fmtCurrency, formatType } = useFormat()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()
  const referenceData = useReferenceDataStore()
  const workbench = useWorkbenchStore()
  const { exportToCSV } = useExport()

  const form = ref<PredictionFormData>({
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
  const storedDraft = useLocalStorage<Partial<PredictionFormData>>('prediction_form_draft', {})

  const result = ref<PredictionResultPayload | null>(null)
  const history = ref<PredictionHistoryItem[]>([])
  const loading = ref(false)
  const contextLoading = ref(false)
  const error = ref('')

  const municipalityContext = computed(() => stats.municipalityDetail)
  const comparables = computed(() => stats.comparables)
  const comparableRows = computed<TransactionRecord[]>(() => comparables.value?.items || [])
  const municipalityIndex = computed(
    () =>
      new Map(
        referenceData.municipalities.map((item) => [
          normalizeMunicipalityName(item.municipality),
          item,
        ]),
      ),
  )
  const comparablesCountLabel = computed(
    () => `${comparables.value?.summary?.count || 0} ${t('dashboard.transactions')}`,
  )
  const effectiveSize = computed(() => form.value.uporabna_povrsina || form.value.size_m2)
  const submittedSize = computed(() => {
    const candidates = [form.value.size_m2, form.value.uporabna_povrsina]
    return candidates.find((value) => typeof value === 'number' && value > 0) ?? null
  })
  const currentMunicipality = computed(() => form.value.municipality || '')
  const selectedMunicipalityMeta = computed(() => {
    return municipalityIndex.value.get(normalizeMunicipalityName(currentMunicipality.value))
  })
  const comparisonUrl = computed(() =>
    buildNepremicnineSearchUrl({
      municipality: form.value.municipality || undefined,
      statisticalRegion: selectedMunicipalityMeta.value?.region,
      propertyType: form.value.property_type,
    }),
  )
  const enabledSignalCount = computed(
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
        ] as const
      ).filter((field) => form.value[field] === 1).length,
  )
  const predictionSummaryCards = computed<PredictionSummaryCard[]>(() => [
    {
      key: 'type',
      icon: 'pi pi-home',
      label: t('predict.propertyType'),
      value: formatType(form.value.property_type) || t('common.noData'),
    },
    {
      key: 'market',
      icon: 'pi pi-map-marker',
      label: t('predict.municipality'),
      value: currentMunicipality.value || t('predict.municipalityPlaceholder'),
      detail: selectedMunicipalityMeta.value?.region || t('common.noData'),
    },
    {
      key: 'size',
      icon: 'pi pi-expand',
      label: t('predict.size'),
      value: effectiveSize.value ? `${fmt(effectiveSize.value, 1)} m²` : '-',
    },
    {
      key: 'signals',
      icon: 'pi pi-sparkles',
      label: t('predict.buildingFlags'),
      value: `${enabledSignalCount.value}`,
      detail: t('predict.previewSignalsDetail'),
    },
  ])
  const predictionReadiness = computed<PredictionReadinessItem[]>(() => [
    {
      key: 'subject',
      ready: Boolean(form.value.naselje?.trim() && effectiveSize.value && form.value.property_type),
      text:
        form.value.naselje?.trim() && effectiveSize.value && form.value.property_type
          ? t('predict.readinessSubjectReady')
          : t('predict.readinessSubjectMissing'),
    },
    {
      key: 'location',
      ready: Boolean(currentMunicipality.value),
      text: currentMunicipality.value
        ? t('predict.readinessLocationReady')
        : t('predict.readinessLocationMissing'),
    },
    {
      key: 'signals',
      ready: enabledSignalCount.value > 0,
      text:
        enabledSignalCount.value > 0
          ? t('predict.readinessSignalsReady')
          : t('predict.readinessSignalsMissing'),
    },
  ])

  async function fetchHistory() {
    try {
      const { data } = await api.get<{ items: PredictionHistoryItem[] }>('/api/predict/history', {
        params: { per_page: 12 },
      })
      history.value = data.items || []
    } catch {
      history.value = []
    }
  }

  async function loadContext(estimatedPrice: number | null = null) {
    const municipality = form.value.municipality
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
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const payload: Record<string, unknown> = {}
      for (const [key, value] of Object.entries(form.value)) {
        if (value !== null && value !== '' && value !== undefined) {
          payload[key] = value
        }
      }
      if (payload.size_m2 == null && submittedSize.value != null) {
        payload.size_m2 = submittedSize.value
      }

      const { data } = await api.post<PredictionResultPayload>('/api/predict', payload, {
        // Prediction can include heavy server-side enrichment; don't abort client-side.
        timeout: 0,
      })
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

  function applyRouteQuery(query: PredictionRouteQuery) {
    const nextForm: PredictionFormData = {
      ...form.value,
      naselje: '',
      municipality: '',
      property_type: 'stanovanje',
      size_m2: null,
      year_built: null,
      floor: null,
    }

    for (const field of ['naselje', 'municipality', 'property_type'] as const) {
      if (query[field]) {
        nextForm[field] = String(query[field])
      }
    }

    for (const field of ['size_m2', 'year_built', 'floor'] as const) {
      if (query[field]) {
        const numericValue = Number(query[field])
        if (!Number.isNaN(numericValue)) {
          nextForm[field] = numericValue
        }
      }
    }

    form.value = nextForm
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

  function reuseComparable(item: TransactionRecord) {
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
      applyRouteQuery(query as PredictionRouteQuery)
    },
    { immediate: true },
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
    applyRouteQuery(route.query as PredictionRouteQuery)
    await Promise.all([
      fetchHistory(),
      referenceData.ensureLoaded(),
      stats.fetchFeatureImportance(),
    ])
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

        <PredictionForm
          v-model="form"
          :loading="loading"
          :error="error"
          :municipality-region="selectedMunicipalityMeta?.region || ''"
          @submit="predict"
        />

        <div class="input-brief">
          <article class="brief-card">
            <span>{{ t('predict.subjectBasics') }}</span>
            <strong>{{
              submittedSize ? `${fmt(submittedSize, 1)} m²` : t('common.noData')
            }}</strong>
            <small>{{ t('predict.previewBody') }}</small>
          </article>
          <article class="brief-card">
            <span>{{ t('predict.locationContext') }}</span>
            <strong>{{ currentMunicipality || t('predict.municipalityPlaceholder') }}</strong>
            <small>{{ selectedMunicipalityMeta?.region || t('common.noData') }}</small>
          </article>
        </div>
      </article>

      <article class="panel story-panel">
        <div v-if="loading || contextLoading" class="inline-loading" aria-busy="true">
          <LoadingSpinner :label="t('common.loading')" />
        </div>

        <PredictionResultSummary
          v-else-if="result"
          :result="result"
          :form="form"
          :comparison-url="comparisonUrl"
          :current-municipality="currentMunicipality"
          :municipality-region="selectedMunicipalityMeta?.region || ''"
          :effective-size="effectiveSize"
          :property-type-label="formatType(form.property_type) || ''"
          @open-market="openMarketExplorer"
          @open-map="openMapExplorer"
          @open-analysis="openAnalysis"
          @refresh-context="loadContext(result.predicted_price_eur)"
        />

        <template v-else>
          <section class="story-block preview-lead">
            <div class="story-head">
              <div>
                <p class="eyebrow subtle">{{ t('predict.previewTitle') }}</p>
                <h3>{{ t('predict.previewHeading') }}</h3>
              </div>
            </div>
            <p class="muted preview-copy">{{ t('predict.previewBody') }}</p>

            <div class="workflow-band">
              <article class="workflow-step">
                <span>01</span>
                <strong>{{ t('predict.subjectBasics') }}</strong>
                <p>{{ t('predict.previewReadinessBody') }}</p>
              </article>
              <article class="workflow-step">
                <span>02</span>
                <strong>{{ t('predict.locationContext') }}</strong>
                <p>{{ t('predict.pickMunicipalityHint') }}</p>
              </article>
              <article class="workflow-step">
                <span>03</span>
                <strong>{{ t('predict.result') }}</strong>
                <p>{{ t('predict.valuationBody') }}</p>
              </article>
            </div>

            <div class="preview-signal-grid">
              <article
                v-for="card in predictionSummaryCards"
                :key="card.key"
                class="preview-signal-card"
              >
                <span class="preview-icon"><i :class="card.icon"></i></span>
                <div>
                  <small>{{ card.label }}</small>
                  <strong>{{ card.value }}</strong>
                  <p v-if="card.detail">{{ card.detail }}</p>
                </div>
              </article>
            </div>
          </section>

          <section class="story-block readiness-block">
            <div class="story-head">
              <h3>{{ t('predict.previewReadinessTitle') }}</h3>
            </div>
            <p class="muted preview-copy">{{ t('predict.previewReadinessBody') }}</p>
            <div class="readiness-list">
              <article
                v-for="item in predictionReadiness"
                :key="item.key"
                class="readiness-item"
                :class="{ ready: item.ready }"
              >
                <i
                  :class="item.ready ? 'pi pi-check-circle' : 'pi pi-circle'"
                  aria-hidden="true"
                ></i>
                <span>{{ item.text }}</span>
              </article>
            </div>
          </section>
        </template>

        <section v-if="result && municipalityContext" class="story-block context-card">
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
              <strong>{{ fmtCurrency(municipalityContext.overview?.median_price) }}</strong>
            </article>
            <article>
              <span>{{ t('dashboard.pricePerM2') }}</span>
              <strong>{{ fmtCurrency(municipalityContext.overview?.median_price_per_m2) }}</strong>
            </article>
            <article>
              <span>{{ t('dashboard.transactions') }}</span>
              <strong>{{ fmt(municipalityContext.overview?.count) }}</strong>
            </article>
          </div>
        </section>

        <PredictionComparables
          v-if="result"
          :items="comparableRows"
          :count-label="comparablesCountLabel"
          @reuse="reuseComparable"
        />
      </article>
    </section>

    <section class="prediction-secondary-grid">
      <article v-if="stats.featureImportance?.length" class="panel secondary-panel">
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
      </article>

      <article class="panel secondary-panel">
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
              <strong>{{ item.payload?.municipality || '-' }}</strong>
              <small>{{ formatDateTime(item.created_at) }}</small>
            </div>
            <div class="history-metric">
              <strong>{{ fmtCurrency(item.predicted_price_eur) }}</strong>
              <small>{{ formatType(item.payload?.property_type) || '-' }}</small>
            </div>
          </article>
        </div>
        <EmptyState v-else icon="pi pi-inbox" :message="t('predict.noHistory')" />
      </article>
    </section>
  </div>
</template>

<style scoped>
  .prediction-page {
    display: grid;
    gap: var(--space-section);
  }

  .prediction-secondary-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(22rem, 0.88fr);
    gap: var(--space-section);
  }

  .prediction-shell {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(23rem, 0.92fr);
    gap: var(--space-section);
  }

  .panel {
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
  }

  .input-panel,
  .story-panel,
  .secondary-panel {
    padding: 1.35rem;
    background: var(--surface-panel);
  }

  .input-brief {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 0.8rem;
    margin: 1rem 0 1.15rem;
  }

  .brief-card {
    display: grid;
    gap: 0.3rem;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--primary) 26%);
    background:
      linear-gradient(
        180deg,
        color-mix(
          in srgb,
          var(--surface-card-strong, var(--surface-strong)) 96%,
          var(--primary) 4%
        ),
        var(--surface-panel)
      ),
      var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  .brief-card span,
  .workflow-step span {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--text-soft);
  }

  .brief-card strong {
    font-size: 1.02rem;
    letter-spacing: -0.02em;
  }

  .brief-card small,
  .preview-copy,
  .workflow-step p,
  .history-card small,
  .feature-desc,
  .inline-loading {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .story-panel,
  .history-list,
  .context-metrics {
    display: grid;
    gap: 1rem;
  }

  .feature-desc {
    margin: -0.35rem 0 0.6rem;
    font-size: var(--text-meta);
  }

  .preview-copy {
    margin: -0.35rem 0 0;
  }

  .workflow-band {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
    gap: 0.8rem;
    margin: 1rem 0 0.4rem;
  }

  .workflow-step {
    padding: 0.95rem 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 94%,
      var(--primary) 6%
    );
    box-shadow: var(--shadow-sm);
  }

  .workflow-step span {
    display: inline-flex;
    margin-bottom: 0.4rem;
    color: var(--primary);
  }

  .workflow-step strong {
    display: block;
    margin-bottom: 0.25rem;
    font-size: 0.94rem;
  }

  .preview-signal-grid,
  .readiness-list {
    display: grid;
    gap: 0.8rem;
  }

  .preview-signal-grid {
    grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  }

  .preview-signal-card,
  .readiness-item {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.85rem;
    padding: 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--primary) 8%
    );
    box-shadow: var(--shadow-sm);
  }

  .preview-signal-card strong {
    display: block;
    font-size: 1rem;
    line-height: 1.25;
  }

  .preview-signal-card p {
    margin: 0.25rem 0 0;
    color: var(--text-muted);
  }

  .preview-signal-card small {
    display: block;
    margin-bottom: 0.25rem;
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .preview-icon {
    display: inline-grid;
    place-items: center;
    width: 2.6rem;
    height: 2.6rem;
    border-radius: var(--radius-xs);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 90%,
      var(--primary) 10%
    );
    color: var(--primary);
  }

  .readiness-item {
    align-items: center;
    border-radius: 999px;
    padding: 0.9rem 1rem;
    font-weight: 700;
  }

  .readiness-item i {
    color: var(--text-soft);
  }

  .readiness-item.ready {
    border-color: color-mix(in srgb, var(--success) 26%, var(--border));
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--success) 8%
    );
  }

  .readiness-item.ready i {
    color: var(--success-strong, var(--success));
  }

  .context-card {
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 94%,
      var(--warning) 6%
    );
    box-shadow: var(--shadow-sm);
  }

  .context-metrics {
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  }

  .context-metrics article span {
    display: block;
    margin-bottom: 0.25rem;
    font-size: 0.8rem;
    color: var(--text-soft);
  }

  .context-metrics article strong,
  .history-metric strong {
    display: block;
    font-size: 1.05rem;
  }

  .history-list {
    gap: 0.8rem;
  }

  .history-card {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 94%,
      transparent
    );
    box-shadow: var(--shadow-sm);
  }

  .history-metric {
    text-align: right;
  }

  .story-link {
    text-decoration: none;
  }

  @media (max-width: 1120px) {
    .prediction-shell,
    .prediction-secondary-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .input-panel,
    .story-panel {
      padding: 1rem;
    }

    .history-card {
      flex-direction: column;
    }

    .history-metric {
      text-align: left;
    }
  }
</style>
