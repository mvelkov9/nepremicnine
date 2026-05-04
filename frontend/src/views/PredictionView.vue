<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
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
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useExport } from '../composables/useExport'
  import { useReferenceDataStore } from '../stores/referenceData'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import {
    buildPredictionFormFromQuery,
    createDefaultPredictionForm,
    hasPredictionRouteState,
    predictionRouteFields,
  } from '../features/prediction/routeState'
  import { buildNepremicnineSearchUrl } from '../utils/externalSearch'
  import { getApiErrorMessage } from '../utils/apiError'
  import { useFormat } from '../composables/useFormat'
  import { formatDateTime } from '../utils/format'
  import { municipalitySlug, normalizeMunicipalityName } from '../utils/municipality'
  import { readQueryTab } from '../utils/routeQuery'
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

  const form = ref<PredictionFormData>(createDefaultPredictionForm())
  const storedDraft = useLocalStorage<Partial<PredictionFormData>>('prediction_form_draft', {})

  const result = ref<PredictionResultPayload | null>(null)
  const history = ref<PredictionHistoryItem[]>([])
  const loading = ref(false)
  const contextLoading = ref(false)
  const error = ref('')
  const municipalityContextError = ref('')
  const comparablesError = ref('')
  let contextRequestToken = 0
  let lastContextSignature = ''

  const predictionRouteSignature = computed(() =>
    JSON.stringify(
      Object.fromEntries(predictionRouteFields.map((field) => [field, route.query[field]])),
    ),
  )

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
    const requestToken = ++contextRequestToken
    const municipality = form.value.municipality
    municipalityContextError.value = ''
    comparablesError.value = ''

    if (!municipality || !form.value.property_type || !effectiveSize.value) {
      lastContextSignature = ''
      stats.resetComparables()
      stats.resetMunicipalityDetail()
      contextLoading.value = false
      return
    }

    const contextSignature = JSON.stringify({
      municipality: municipalitySlug(municipality),
      naselje: form.value.naselje || '',
      property_type: form.value.property_type,
      size_m2: effectiveSize.value,
      year_built: form.value.year_built || null,
      price_eur: estimatedPrice || null,
    })

    if (contextSignature !== lastContextSignature) {
      stats.resetComparables()
      stats.resetMunicipalityDetail()
    }

    contextLoading.value = true
    try {
      const [municipalityResult, comparablesResult] = await Promise.allSettled([
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

      if (requestToken !== contextRequestToken) return
      lastContextSignature = contextSignature

      if (municipalityResult.status === 'rejected') {
        stats.resetMunicipalityDetail()
        municipalityContextError.value = getApiErrorMessage(municipalityResult.reason, t)
      }

      if (comparablesResult.status === 'rejected') {
        stats.resetComparables()
        comparablesError.value = getApiErrorMessage(comparablesResult.reason, t)
      }
    } finally {
      if (requestToken === contextRequestToken) {
        contextLoading.value = false
      }
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

  watch(predictionRouteSignature, () => {
    if (!hasPredictionRouteState(route.query as PredictionRouteQuery)) return
    form.value = buildPredictionFormFromQuery(route.query as PredictionRouteQuery)
  })

  watch(
    form,
    (value) => {
      storedDraft.value = { ...value }
    },
    { deep: true },
  )

  onMounted(async () => {
    form.value = hasPredictionRouteState(route.query as PredictionRouteQuery)
      ? buildPredictionFormFromQuery(route.query as PredictionRouteQuery)
      : {
          ...createDefaultPredictionForm(),
          ...storedDraft.value,
        }
    await Promise.allSettled([fetchHistory(), referenceData.ensureLoaded()])
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
                tab: 'history',
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
        <div v-if="(loading || contextLoading) && !result" class="inline-loading" aria-busy="true">
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

            <div class="readiness-list preview-readiness-list">
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

        <section
          v-else-if="result && contextLoading && !municipalityContextError"
          class="story-block context-card context-card-loading"
          aria-busy="true"
        >
          <LoadingSpinner :label="t('common.loading')" />
        </section>

        <section
          v-else-if="result && municipalityContextError"
          class="story-block context-alert"
          role="status"
        >
          <div class="context-alert-copy">
            <p class="eyebrow subtle">{{ t('predict.marketContext') }}</p>
            <strong>{{ t('common.warning') }}</strong>
            <p>{{ municipalityContextError }}</p>
          </div>
          <Button
            size="small"
            severity="secondary"
            outlined
            icon="pi pi-refresh"
            :label="t('common.retry')"
            @click="loadContext(result.predicted_price_eur)"
          />
        </section>

        <PredictionComparables
          v-if="result"
          :items="comparableRows"
          :count-label="comparablesCountLabel"
          :loading="contextLoading && !comparableRows.length && !comparablesError"
          :error="comparablesError"
          @reuse="reuseComparable"
          @refresh="loadContext(result.predicted_price_eur)"
        />
      </article>
    </section>

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
  </div>
</template>

<style scoped>
  .prediction-page {
    display: grid;
    gap: var(--space-section);
    animation: prediction-in 430ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .prediction-tabs,
  .prediction-tab-content {
    display: grid;
    gap: 1rem;
  }

  .prediction-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 18%);
    border-radius: var(--radius-lg);
    background: color-mix(in srgb, var(--surface-strong) 92%, var(--primary-overlay) 8%);
    box-shadow: 0 10px 22px color-mix(in srgb, var(--shadow-color) 8%, transparent);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .prediction-tabs :deep(.p-tabpanels) {
    padding-top: 0.15rem;
  }

  .prediction-secondary-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(22rem, 0.88fr);
    gap: var(--space-section);
  }

  .prediction-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.16fr) minmax(22rem, 0.84fr);
    gap: var(--space-section);
    align-items: start;
  }

  .panel {
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
    transition:
      border-color 170ms ease,
      box-shadow 170ms ease,
      transform 170ms ease;
  }

  .panel:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--border) 60%, var(--primary) 40%);
    box-shadow: 0 22px 42px color-mix(in srgb, var(--shadow-color) 14%, transparent);
  }

  .input-panel,
  .story-panel,
  .secondary-panel {
    padding: 1.35rem;
    background: var(--surface-panel);
  }

  .story-panel {
    position: sticky;
    top: 5.75rem;
  }

  .secondary-panel {
    position: static;
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

  .preview-readiness-list {
    margin-top: 0.1rem;
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

  .context-card-loading,
  .context-alert {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .context-alert {
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--warning) 42%, var(--border) 58%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-strong)) 92%,
      var(--warning) 8%
    );
    box-shadow: var(--shadow-sm);
  }

  .context-alert-copy {
    display: grid;
    gap: 0.25rem;
  }

  .context-alert-copy strong {
    font-size: 0.95rem;
    letter-spacing: -0.01em;
  }

  .context-alert-copy p {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.5;
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
    transition:
      border-color 140ms ease,
      box-shadow 140ms ease,
      transform 140ms ease;
  }

  .history-card:hover {
    border-color: color-mix(in srgb, var(--border) 64%, var(--primary) 36%);
    box-shadow: 0 14px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
    transform: translateY(-1px);
  }

  .history-metric {
    text-align: right;
  }

  .story-link {
    text-decoration: none;
  }

  @keyframes prediction-in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 1120px) {
    .prediction-shell,
    .prediction-secondary-grid {
      grid-template-columns: 1fr;
    }

    .story-panel,
    .secondary-panel {
      position: static;
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

  @media (prefers-reduced-motion: reduce) {
    .prediction-page {
      animation: none;
    }

    .panel,
    .history-card {
      transition: none;
    }

    .panel:hover,
    .history-card:hover {
      transform: none;
    }
  }

  @media (max-width: 720px) {
    .context-card-loading,
    .context-alert {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
