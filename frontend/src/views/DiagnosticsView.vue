<script setup lang="ts">
  import { computed, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { Bar } from 'vue-chartjs'
  import {
    BarElement,
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    Tooltip,
  } from 'chart.js'
  import DataTable from 'primevue/datatable'
  import Column from 'primevue/column'
  import Select from 'primevue/select'
  import SelectButton from 'primevue/selectbutton'
  import Tag from 'primevue/tag'
  import AdminRunDetailPanel from '../components/admin/AdminRunDetailPanel.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import EmptyState from '../components/EmptyState.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useWorkbenchStore } from '../stores/workbench'
  import { buildGursEnrichmentRows, summarizeGursEnrichment } from '../utils/enrichmentSummary'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

  const { t } = useI18n()
  const model = useModelStore()
  const dataStore = useDataStore()
  const workbench = useWorkbenchStore()

  const viewerQuery = useViewerQueryState({
    metric: 'r2',
    property_type: 'all',
    segment_group: 'property_type',
    training_run: '',
  })
  const selectedMetric = computed({
    get: () => viewerQuery.state.metric,
    set: (value: string) => {
      void viewerQuery.patchState({ metric: value })
    },
  })
  const selectedType = computed({
    get: () => viewerQuery.state.property_type,
    set: (value: string) => {
      void viewerQuery.patchState({ property_type: value })
    },
  })
  const selectedSegmentGroup = computed({
    get: () => viewerQuery.state.segment_group,
    set: (value: string) => {
      void viewerQuery.patchState({ segment_group: value })
    },
  })
  const selectedTrainingRunId = computed({
    get: () => viewerQuery.state.training_run,
    set: (value: string) => {
      void viewerQuery.patchState({ training_run: value })
    },
  })
  const metrics = ['mae', 'rmse', 'r2', 'mape', 'median_ae']

  function formatType(value) {
    return getPropertyTypeLabel(value, t)
  }

  function formatMetric(value, digits = 4) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    return formatNumber(value, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  }

  function formatDuration(value) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    return `${formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }

  function humanizeStage(stage) {
    if (!stage) return '—'
    return String(stage)
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase())
  }

  function segmentGroupLabel(group) {
    const labels = {
      property_type: t('diag.byPropertyType'),
      sale_type: t('diag.saleTypeSegments'),
      transaction_year: t('diag.yearSegments'),
      parcel_land_type: t('diag.parcelLandTypeSegments'),
    }
    return labels[group] || group
  }

  const availableTypes = computed(() => Object.keys(model.info?.per_type_metrics || {}))

  const typeOptions = computed(() => [
    { label: t('diag.allTypes'), value: 'all' },
    ...availableTypes.value.map((type) => ({ label: formatType(type), value: type })),
  ])

  const metricOptions = computed(() => metrics.map((m) => ({ label: m.toUpperCase(), value: m })))

  const segmentGroupOptions = computed(() =>
    Object.keys(model.diagnostics?.segment_diagnostics || {}).map((key) => ({
      label: segmentGroupLabel(key),
      value: key,
    })),
  )

  const selectedTypeMetrics = computed(() => {
    if (selectedType.value === 'all') return model.info?.global_metrics || null
    return model.info?.per_type_metrics?.[selectedType.value] || null
  })
  const selectedTrainingRun = computed(() => workbench.selectedTrainingRun)

  const focusMetrics = computed(() => {
    const metricsData = selectedTypeMetrics.value
    if (!metricsData) return []
    return [
      { label: 'MAE', value: formatCurrency(metricsData.mae), desc: t('diag.maeDesc') },
      { label: 'RMSE', value: formatCurrency(metricsData.rmse), desc: t('diag.rmseDesc') },
      { label: 'R²', value: formatMetric(metricsData.r2), desc: t('diag.r2Desc') },
      {
        label: 'MAPE',
        value:
          metricsData.mape == null
            ? '—'
            : formatPercent(metricsData.mape, { scale: 0.01, minimumFractionDigits: 1 }),
        desc: t('diag.mapeDesc'),
      },
      {
        label: t('diag.medianError'),
        value: formatCurrency(metricsData.median_ae),
        desc: t('diag.medianDesc'),
      },
      {
        label: t('diag.trainSamples'),
        value: formatNumber(metricsData.n_train),
        desc:
          selectedType.value === 'all'
            ? t('diag.focusAllDesc')
            : t('diag.focusTypeDesc', { type: formatType(selectedType.value) }),
      },
      {
        label: t('diag.testSamples'),
        value: formatNumber(metricsData.n_test),
        desc: t('diag.testRows'),
      },
    ]
  })

  const featureHighlights = computed(() => model.importance.slice(0, 8))

  function getChartPalette() {
    const style = getComputedStyle(document.documentElement)
    return {
      primary: style.getPropertyValue('--primary').trim() || '#1d4ed8',
      primarySoft:
        style.getPropertyValue('--secondary').trim() ||
        style.getPropertyValue('--primary').trim() ||
        '#0f766e',
      success: style.getPropertyValue('--success').trim() || '#15803d',
    }
  }

  const perTypeChart = computed(() => {
    const ptm = model.info?.per_type_metrics
    if (!ptm) return null
    const labels = Object.keys(ptm)
    const data = labels.map((k) => ptm[k]?.[selectedMetric.value] ?? 0)
    const palette = getChartPalette()
    return {
      labels: labels.map((label) => formatType(label)),
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: labels.map((label) =>
            selectedType.value === 'all' || selectedType.value === label
              ? palette.primary
              : palette.primarySoft,
          ),
          borderRadius: 4,
        },
      ],
    }
  })

  const perRegionChart = computed(() => {
    const prm = model.info?.per_region_metrics
    if (!prm) return null
    const labels = Object.keys(prm)
    const data = labels.map((k) => prm[k]?.[selectedMetric.value] ?? 0)
    const palette = getChartPalette()
    return {
      labels,
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: palette.success,
          borderRadius: 4,
        },
      ],
    }
  })

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } },
  }

  const combinedMetrics = computed(() => {
    const metricsData = model.diagnostics?.combined_metrics
    if (!metricsData) return []
    return [
      { label: 'MAE', value: formatCurrency(metricsData.mae) },
      { label: 'RMSE', value: formatCurrency(metricsData.rmse) },
      { label: 'R²', value: formatMetric(metricsData.r2) },
      {
        label: 'MAPE',
        value:
          metricsData.mape == null
            ? '—'
            : formatPercent(metricsData.mape, { scale: 0.01, minimumFractionDigits: 1 }),
      },
      { label: t('diag.medianError'), value: formatCurrency(metricsData.median_ae) },
    ]
  })

  const variantBenchmarks = computed(() => model.diagnostics?.variant_benchmarks || null)
  const variantMatrix = computed(() => model.diagnostics?.variant_matrix || null)

  const variantBenchmarkCards = computed(() => {
    const variants = variantBenchmarks.value
    if (!variants) return []

    const production = variants.production_combined?.metrics
    const etnOnly = variants.etn_only?.metrics
    const deterministic = variants.deterministic?.metrics
    const fullGlobal = variants.full_global?.metrics
    if (!production || !etnOnly || !deterministic || !fullGlobal) return []

    return [
      {
        label: t('diag.productionR2'),
        value: formatMetric(production.r2, 3),
        meta: t('diag.productionR2Desc'),
      },
      {
        label: t('diag.detVsEtnR2'),
        value: formatSignedNumber(deterministic.r2 - etnOnly.r2, 3),
        meta: t('diag.detVsEtnR2Desc'),
      },
      {
        label: t('diag.fullVsDetR2'),
        value: formatSignedNumber(fullGlobal.r2 - deterministic.r2, 3),
        meta: t('diag.fullVsDetR2Desc'),
      },
      {
        label: t('diag.prodVsFullMae'),
        value: formatSignedCurrency(production.mae - fullGlobal.mae),
        meta: t('diag.prodVsFullMaeDesc'),
      },
    ]
  })

  const variantBenchmarkRows = computed(() => {
    const variants = variantBenchmarks.value
    if (!variants) return []

    return Object.entries(variants).map(([key, variant]: [string, any]) => ({
      key,
      label: variant.label || key,
      sources: variant.enabled_sources || {},
      mae: variant.metrics?.mae,
      rmse: variant.metrics?.rmse,
      r2: variant.metrics?.r2,
      mape: variant.metrics?.mape,
      delta_r2: variant.delta_vs_full_global?.r2,
      delta_mae: variant.delta_vs_full_global?.mae,
      removedFeatures: Array.isArray(variant.removed_features) ? variant.removed_features : [],
    }))
  })

  const variantMatrixRows = computed(() => {
    const variants = variantMatrix.value
    if (!variants) return []

    return Object.entries(variants).map(([key, variant]: [string, any]) => ({
      key,
      label: variant.label || key,
      sources: variant.enabled_sources || {},
      globalR2: variant.global_metrics?.r2,
      globalMae: variant.global_metrics?.mae,
      combinedR2: variant.combined_metrics?.r2,
      combinedMae: variant.combined_metrics?.mae,
      perTypeCount: variant.per_type_count ?? 0,
    }))
  })

  const evBaseline = computed(() => model.diagnostics?.ev_baseline_metrics || null)

  const evBaselineCards = computed(() => {
    const baseline = evBaseline.value
    if (!baseline?.benchmark_metrics || !baseline?.model_metrics_on_coverage) return []
    const coveragePct =
      baseline.coverage_ratio == null
        ? ''
        : ` (${formatPercent(baseline.coverage_ratio, { minimumFractionDigits: 1 })})`
    return [
      {
        label: t('diag.evCoverageRows'),
        value: `${formatNumber(baseline.coverage_rows)}${coveragePct}`,
        meta: t('diag.evCoverageRowsDesc'),
      },
      {
        label: t('diag.modelMaeOnCoverage'),
        value: formatCurrency(baseline.model_metrics_on_coverage.mae),
        meta: t('diag.modelMaeOnCoverageDesc'),
      },
      {
        label: t('diag.evBenchmarkMae'),
        value: formatCurrency(baseline.benchmark_metrics.mae),
        meta: t('diag.evBenchmarkMaeDesc'),
      },
      {
        label: t('diag.modelEdgeR2'),
        value: formatSignedNumber(baseline.delta_vs_model?.r2, 3),
        meta: t('diag.modelEdgeR2Desc'),
      },
    ]
  })

  const evBaselinePerTypeRows = computed(() => {
    const rows = evBaseline.value?.per_type_metrics
    if (!rows) return []
    return Object.entries(rows).map(([propertyType, metricsData]: [string, any]) => ({
      propertyType,
      typeLabel: formatType(propertyType),
      n: metricsData.n,
      mae: metricsData.mae,
      rmse: metricsData.rmse,
      r2: metricsData.r2,
      model_mae: metricsData.model_mae,
      model_r2: metricsData.model_r2,
      delta_mae: metricsData.mae - metricsData.model_mae,
    }))
  })

  const diagnosticsSummaryCards = computed(() => [
    {
      label: 'R²',
      value:
        model.info?.global_metrics?.r2 != null
          ? formatMetric(model.info.global_metrics.r2, 3)
          : '—',
      meta: t('diag.r2Desc'),
      tone: 'success' as const,
    },
    {
      label: 'MAE',
      value:
        model.info?.global_metrics?.mae != null
          ? formatCurrency(model.info.global_metrics.mae)
          : '—',
      meta: t('diag.maeDesc'),
    },
    {
      label: t('diag.focusType'),
      value: selectedType.value === 'all' ? t('diag.allTypes') : formatType(selectedType.value),
      meta:
        selectedType.value === 'all'
          ? t('diag.focusAllDesc')
          : t('diag.focusTypeDesc', { type: formatType(selectedType.value) }),
    },
    {
      label: t('diag.variantBenchmarks'),
      value: formatNumber(variantBenchmarkRows.value.length),
      meta: t('diag.variantBenchmarksDesc'),
    },
  ])

  const modelDetailsRows = computed(() => {
    if (!model.info) return []
    const rows = [
      { key: t('diag.version'), val: model.info.version },
      { key: t('diag.trainedAt'), val: formatDateTime(model.info.trained_at) },
      { key: t('diag.rows'), val: formatNumber(model.info.rows) },
    ]
    if (model.diagnostics?.train_rows) {
      rows.push({ key: t('diag.trainRows'), val: formatNumber(model.diagnostics.train_rows) })
    }
    if (model.diagnostics?.test_rows) {
      rows.push({ key: t('diag.testRows'), val: formatNumber(model.diagnostics.test_rows) })
    }
    rows.push(
      { key: t('diag.duration'), val: formatDuration(model.info.duration_sec) },
      { key: t('diag.perTypeModels'), val: formatNumber(model.info.per_type_count) },
    )
    if (model.diagnostics?.model_type) {
      rows.push({ key: t('diag.modelType'), val: model.diagnostics.model_type })
    }
    if (model.diagnostics?.type_models_trained?.length) {
      rows.push({
        key: t('diag.trainedTypes'),
        val: model.diagnostics.type_models_trained.map((type) => formatType(type)).join(', '),
      })
    }
    return rows
  })

  const perTypeRows = computed(() => {
    const ptm = model.info?.per_type_metrics
    if (!ptm) return []
    return Object.entries(ptm).map(([propertyType, metricsData]: [string, any]) => ({
      propertyType,
      typeLabel: formatType(propertyType),
      mae: metricsData.mae,
      rmse: metricsData.rmse,
      r2: metricsData.r2,
      mape: metricsData.mape,
      n_train: metricsData.n_train,
      n_test: metricsData.n_test,
    }))
  })

  function perTypeRowClass(data) {
    return selectedType.value === data.propertyType ? 'active-focus-row' : ''
  }

  const perRegionRows = computed(() => {
    const prm = model.info?.per_region_metrics
    if (!prm) return []
    return Object.entries(prm).map(([region, metricsData]: [string, any]) => ({
      region,
      mae: metricsData.mae,
      rmse: metricsData.rmse,
      r2: metricsData.r2,
      mape: metricsData.mape,
    }))
  })

  const preparationMetadata = computed(
    () =>
      model.diagnostics?.data_preparation ||
      dataStore.trainingDataset?.preparation_metadata ||
      null,
  )

  const filterRows = computed(() => {
    const summary = preparationMetadata.value?.filter_summary
    if (!summary) return []
    return Object.entries(summary).flatMap(([group, stages]) =>
      ((stages as any[]) || []).map((stage) => ({
        group,
        groupLabel: group === 'building' ? t('diag.buildingFlow') : t('diag.landFlow'),
        stage: stage.stage,
        stageLabel: humanizeStage(stage.stage),
        rows: stage.rows,
        dropped_since_previous: stage.dropped_since_previous,
        reports: stage.reports,
      })),
    )
  })

  const enrichmentRows = computed(() =>
    buildGursEnrichmentRows(
      preparationMetadata.value?.reports,
      preparationMetadata.value?.enrichment_summary,
    ),
  )

  const enrichmentTotals = computed(() => summarizeGursEnrichment(enrichmentRows.value))

  const enrichmentSourcesMissing = computed(() => {
    if (!enrichmentRows.value.length) return false
    return enrichmentRows.value.every(
      (row) =>
        !row.sources.length &&
        !row.rnAvailable &&
        !row.evBuildingAvailable &&
        !row.evParcelAvailable &&
        !row.knAvailable &&
        !row.gjiAvailable &&
        !row.emvAvailable,
    )
  })

  const segmentRows = computed(
    () => model.diagnostics?.segment_diagnostics?.[selectedSegmentGroup.value] || [],
  )

  const scoreDriverCards = computed(() => {
    const diagnostics = model.diagnostics?.segment_diagnostics || {}
    const cards = []
    const property = diagnostics.property_type?.[0]
    if (property) {
      cards.push({
        label: t('diag.worstPropertyType'),
        value: `${formatType(property.segment)} · R² ${formatMetric(property.r2, 3)}`,
        meta: `${t('diag.testSamples')}: ${formatNumber(property.n)}`,
      })
    }
    const saleType = diagnostics.sale_type?.[0]
    if (saleType) {
      cards.push({
        label: t('diag.worstSaleType'),
        value: `${saleType.segment} · R² ${formatMetric(saleType.r2, 3)}`,
        meta: `${t('diag.testSamples')}: ${formatNumber(saleType.n)}`,
      })
    }
    const landType = diagnostics.parcel_land_type?.[0]
    if (landType) {
      cards.push({
        label: t('diag.worstParcelLandType'),
        value: `${landType.segment} · R² ${formatMetric(landType.r2, 3)}`,
        meta: `${t('diag.testSamples')}: ${formatNumber(landType.n)}`,
      })
    }
    return cards
  })

  function r2Severity(value) {
    if (value > 0.7) return 'success'
    if (value > 0.4) return 'warn'
    return 'danger'
  }

  function formatMape(mape) {
    return mape == null ? '—' : formatPercent(mape, { scale: 0.01, minimumFractionDigits: 1 })
  }

  function formatSignedNumber(value, digits = 2) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    const sign = Number(value) > 0 ? '+' : ''
    return `${sign}${formatMetric(value, digits)}`
  }

  function formatSignedCurrency(value) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    const sign = Number(value) > 0 ? '+' : ''
    return `${sign}${formatCurrency(value)}`
  }

  function variantSourceSummary(sources) {
    const labels = []
    if (sources?.rn) labels.push('RN')
    if (sources?.ev) labels.push('EV')
    if (sources?.emv) labels.push('EMV')
    return labels.length ? labels.join(' + ') : t('diag.etnOnly')
  }

  function enrichmentRunLabel(label) {
    return label === 'single' ? t('diag.currentRun') : String(label)
  }

  function enrichmentSeverity(available, matched) {
    if (matched) return 'success'
    if (available) return 'warn'
    return 'contrast'
  }

  function enrichmentSourcesLabel(row) {
    if (row.matchedSources.length) return row.matchedSources.join(', ')
    if (row.sources.length) {
      return t('diag.detectedOnlySources', { sources: row.sources.join(', ') })
    }
    return t('common.noData')
  }

  onMounted(async () => {
    await Promise.all([
      model.fetchInfo(),
      model.fetchDiagnostics(),
      model.fetchImportance(),
      dataStore.fetchTrainingDataset(),
      workbench.fetchTrainingRuns(),
    ])
    const initialTrainingRunId = selectedTrainingRunId.value || workbench.trainingRuns[0]?.id
    if (initialTrainingRunId) await loadTrainingRunDetail(initialTrainingRunId)
    if (
      segmentGroupOptions.value.length &&
      !segmentGroupOptions.value.some((item) => item.value === selectedSegmentGroup.value)
    ) {
      selectedSegmentGroup.value = segmentGroupOptions.value[0].value
    }
  })

  async function loadTrainingRunDetail(jobId: string) {
    selectedTrainingRunId.value = jobId
    await workbench.fetchTrainingRunDetail(jobId)
  }
</script>

<template>
  <div class="diagnostics-page">
    <AdminWorkspaceHero
      :eyebrow="t('nav.diagnostics')"
      :title="t('nav.diagnostics')"
      :description="t('layout.page.diagnostics')"
      :metrics="diagnosticsSummaryCards"
      :links="adminWorkspaceLinks"
      :status="selectedType === 'all' ? t('diag.allTypes') : formatType(selectedType)"
      status-severity="secondary"
    >
      <template #actions>
        <SavedWorkspaceMenu
          page="diagnostics"
          :state="{
            page: 'diagnostics',
            filters: {
              metric: selectedMetric,
              property_type: selectedType,
              segment_group: selectedSegmentGroup,
              training_run: selectedTrainingRunId,
            },
          }"
        />
      </template>
    </AdminWorkspaceHero>

    <div v-if="!model.info" class="card diagnostics-card">
      <p class="muted">{{ t('diag.noModel') }}</p>
    </div>

    <template v-else>
      <AdminRunDetailPanel
        :eyebrow="t('nav.model')"
        :title="t('workbench.recentTrainingRuns')"
        :description="t('workbench.trainingRunDetailHint')"
        :runs="workbench.trainingRuns.slice(0, 8)"
        :selected-run="selectedTrainingRun"
        @select="loadTrainingRunDetail"
      />

      <!-- Focus type selector + KPI cards -->
      <div class="card diagnostics-card focus-card">
        <div class="focus-head">
          <div>
            <h2>{{ t('diag.focusType') }}</h2>
            <p class="muted">
              {{
                selectedType === 'all'
                  ? t('diag.focusAllDesc')
                  : t('diag.focusTypeDesc', { type: formatType(selectedType) })
              }}
            </p>
          </div>
          <SelectButton
            v-model="selectedType"
            :options="typeOptions"
            option-label="label"
            option-value="value"
          />
        </div>

        <div class="kpi-grid diagnostics-kpi-grid">
          <MetricCard
            v-for="item in focusMetrics"
            :key="item.label"
            :label="item.label"
            :value="item.value"
            :meta="item.desc"
          />
        </div>
      </div>

      <!-- Combined metrics -->
      <div v-if="combinedMetrics.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.combinedMetrics')"
          :title="t('diag.combinedMetrics')"
          :description="t('diag.combinedDesc')"
        />
        <div class="kpi-grid">
          <MetricCard
            v-for="item in combinedMetrics"
            :key="item.label"
            :label="item.label"
            :value="item.value"
          />
        </div>
      </div>

      <div v-if="variantBenchmarkRows.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.variantBenchmarks')"
          :title="t('diag.variantBenchmarks')"
          :description="t('diag.variantBenchmarksDesc')"
        />

        <div v-if="variantBenchmarkCards.length" class="kpi-grid">
          <MetricCard
            v-for="item in variantBenchmarkCards"
            :key="item.label"
            :label="item.label"
            :value="item.value"
            :meta="item.meta"
          />
        </div>

        <DataTable
          :value="variantBenchmarkRows"
          size="small"
          striped-rows
          table-style="min-width: 100%"
        >
          <Column field="label" :header="t('diag.variant')" sortable />
          <Column :header="t('diag.sources')">
            <template #body="{ data }">
              <span class="muted source-cell">{{ variantSourceSummary(data.sources) }}</span>
            </template>
          </Column>
          <Column field="r2" header="R²" sortable>
            <template #body="{ data }">
              <Tag :value="formatMetric(data.r2, 3)" :severity="r2Severity(data.r2)" />
            </template>
          </Column>
          <Column field="mae" header="MAE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.mae) }}</template>
          </Column>
          <Column field="rmse" header="RMSE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.rmse) }}</template>
          </Column>
          <Column field="mape" header="MAPE" sortable>
            <template #body="{ data }">{{ formatMape(data.mape) }}</template>
          </Column>
          <Column field="delta_r2" :header="t('diag.deltaVsFullR2')" sortable>
            <template #body="{ data }">{{ formatSignedNumber(data.delta_r2, 3) }}</template>
          </Column>
          <Column field="delta_mae" :header="t('diag.deltaVsFullMae')" sortable>
            <template #body="{ data }">{{ formatSignedCurrency(data.delta_mae) }}</template>
          </Column>
          <Column :header="t('diag.variantRemovedFeatures')">
            <template #body="{ data }">
              <span class="muted source-cell">
                {{
                  data.removedFeatures.length ? data.removedFeatures.join(', ') : t('common.noData')
                }}
              </span>
            </template>
          </Column>
        </DataTable>
      </div>

      <div v-if="variantMatrixRows.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.variantMatrix')"
          :title="t('diag.variantMatrix')"
          :description="t('diag.variantMatrixDesc')"
        />

        <DataTable
          :value="variantMatrixRows"
          size="small"
          striped-rows
          table-style="min-width: 100%"
        >
          <Column field="label" :header="t('diag.variant')" sortable />
          <Column :header="t('diag.sources')">
            <template #body="{ data }">
              <span class="muted source-cell">{{ variantSourceSummary(data.sources) }}</span>
            </template>
          </Column>
          <Column field="globalR2" :header="t('diag.globalR2')" sortable>
            <template #body="{ data }">{{ formatMetric(data.globalR2, 3) }}</template>
          </Column>
          <Column field="combinedR2" :header="t('diag.routedR2')" sortable>
            <template #body="{ data }">{{ formatMetric(data.combinedR2, 3) }}</template>
          </Column>
          <Column field="globalMae" :header="t('diag.globalMae')" sortable>
            <template #body="{ data }">{{ formatCurrency(data.globalMae) }}</template>
          </Column>
          <Column field="combinedMae" :header="t('diag.routedMae')" sortable>
            <template #body="{ data }">{{ formatCurrency(data.combinedMae) }}</template>
          </Column>
          <Column field="perTypeCount" :header="t('diag.perTypeModels')" sortable>
            <template #body="{ data }">{{ formatNumber(data.perTypeCount) }}</template>
          </Column>
        </DataTable>
      </div>

      <div v-if="evBaselineCards.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.evBaseline')"
          :title="t('diag.evBaseline')"
          :description="t('diag.evBaselineDesc')"
        />

        <div class="kpi-grid">
          <MetricCard
            v-for="item in evBaselineCards"
            :key="item.label"
            :label="item.label"
            :value="item.value"
            :meta="item.meta"
          />
        </div>

        <div v-if="evBaseline?.coverage_by_source" class="coverage-source-list muted">
          <span
            v-for="(count, source) in evBaseline.coverage_by_source"
            :key="source"
            class="coverage-source-item"
          >
            {{ source }}: {{ formatNumber(count) }}
          </span>
        </div>

        <DataTable
          v-if="evBaselinePerTypeRows.length"
          :value="evBaselinePerTypeRows"
          size="small"
          striped-rows
          table-style="min-width: 100%"
        >
          <Column field="typeLabel" :header="t('diag.type')" sortable />
          <Column field="n" :header="t('diag.sampleCount')" sortable>
            <template #body="{ data }">{{ formatNumber(data.n) }}</template>
          </Column>
          <Column field="model_mae" :header="t('diag.modelMaeOnCoverage')" sortable>
            <template #body="{ data }">{{ formatCurrency(data.model_mae) }}</template>
          </Column>
          <Column field="mae" :header="t('diag.evBenchmarkMae')" sortable>
            <template #body="{ data }">{{ formatCurrency(data.mae) }}</template>
          </Column>
          <Column field="delta_mae" :header="t('diag.evMaeSaved')" sortable>
            <template #body="{ data }">
              <Tag
                :value="formatSignedCurrency(data.delta_mae)"
                :severity="data.delta_mae > 0 ? 'success' : 'danger'"
              />
            </template>
          </Column>
          <Column field="model_r2" :header="t('diag.modelR2OnCoverage')" sortable>
            <template #body="{ data }">
              <Tag :value="formatMetric(data.model_r2, 3)" :severity="r2Severity(data.model_r2)" />
            </template>
          </Column>
          <Column field="r2" :header="t('diag.evBenchmarkR2')" sortable>
            <template #body="{ data }">
              <Tag :value="formatMetric(data.r2, 3)" :severity="r2Severity(data.r2)" />
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Model details table -->
      <div class="card diagnostics-card">
        <PageHeader compact :eyebrow="t('diag.modelDetails')" :title="t('diag.modelDetails')" />
        <DataTable :value="modelDetailsRows" size="small" table-style="min-width: 100%">
          <Column field="key" :header="t('diag.property')" />
          <Column field="val" :header="t('diag.value')" />
        </DataTable>
      </div>

      <div v-if="scoreDriverCards.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.scoreDrivers')"
          :title="t('diag.scoreDrivers')"
          :description="t('diag.scoreDriversDesc')"
        />
        <div class="kpi-grid">
          <MetricCard
            v-for="item in scoreDriverCards"
            :key="item.label"
            :label="item.label"
            :value="item.value"
            :meta="item.meta"
          />
        </div>
      </div>

      <div v-if="segmentGroupOptions.length" class="card diagnostics-card">
        <div class="focus-head">
          <div>
            <h2 class="section-title">{{ t('diag.worstSegments') }}</h2>
            <p class="muted">{{ t('diag.worstSegmentsDesc') }}</p>
          </div>
          <Select
            v-model="selectedSegmentGroup"
            :options="segmentGroupOptions"
            option-label="label"
            option-value="value"
          />
        </div>

        <DataTable :value="segmentRows" size="small" striped-rows table-style="min-width: 100%">
          <Column field="segment" :header="t('diag.segment')" sortable />
          <Column field="n" :header="t('diag.testSamples')" sortable>
            <template #body="{ data }">{{ formatNumber(data.n) }}</template>
          </Column>
          <Column field="r2" header="R²" sortable>
            <template #body="{ data }">
              <Tag :value="formatMetric(data.r2, 3)" :severity="r2Severity(data.r2)" />
            </template>
          </Column>
          <Column field="mae" header="MAE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.mae) }}</template>
          </Column>
          <Column field="rmse" header="RMSE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.rmse) }}</template>
          </Column>
          <Column field="mape" header="MAPE" sortable>
            <template #body="{ data }">{{ formatMape(data.mape) }}</template>
          </Column>
        </DataTable>
      </div>

      <div v-if="filterRows.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.filterSummary')"
          :title="t('diag.filterSummary')"
          :description="t('diag.filterSummaryDesc')"
        />
        <DataTable :value="filterRows" size="small" striped-rows table-style="min-width: 100%">
          <Column field="groupLabel" :header="t('diag.flow')" sortable />
          <Column field="stageLabel" :header="t('diag.stage')" sortable />
          <Column field="rows" :header="t('diag.rowsKept')" sortable>
            <template #body="{ data }">{{ formatNumber(data.rows) }}</template>
          </Column>
          <Column field="dropped_since_previous" :header="t('diag.rowsDropped')" sortable>
            <template #body="{ data }">{{ formatNumber(data.dropped_since_previous) }}</template>
          </Column>
          <Column field="reports" :header="t('diag.yearsCovered')" sortable>
            <template #body="{ data }">{{ formatNumber(data.reports) }}</template>
          </Column>
        </DataTable>
      </div>

      <div v-if="enrichmentRows.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.datasetEnrichment')"
          :title="t('diag.datasetEnrichment')"
          :description="t('diag.datasetEnrichmentDesc')"
        />

        <p v-if="enrichmentSourcesMissing" class="muted">
          {{ t('diag.datasetEnrichmentMissingSourcesHint') }}
        </p>

        <div class="kpi-grid">
          <MetricCard
            :label="t('diag.exactAddressMatches')"
            :value="formatNumber(enrichmentTotals.rnExactAddress)"
          />
          <MetricCard
            :label="t('diag.regionIdsRecovered')"
            :value="formatNumber(enrichmentTotals.rnRegionId)"
          />
          <MetricCard
            :label="t('diag.evBuildingMatches')"
            :value="formatNumber(enrichmentTotals.evBuildingMatch)"
          />
          <MetricCard
            :label="t('diag.evParcelMatches')"
            :value="formatNumber(enrichmentTotals.evParcelMatch)"
          />
          <MetricCard
            :label="t('diag.knPolygonMatches')"
            :value="formatNumber(enrichmentTotals.knPolygonMatch)"
          />
          <MetricCard
            :label="t('diag.gjiVodovodMatches')"
            :value="formatNumber(enrichmentTotals.gjiVodovodNearby)"
          />
          <MetricCard
            :label="t('diag.gjiKanalizacijaMatches')"
            :value="formatNumber(enrichmentTotals.gjiKanalizacijaNearby)"
          />
          <MetricCard
            :label="t('diag.emvZoneMatches')"
            :value="formatNumber(enrichmentTotals.emvZoneMatch)"
          />
        </div>

        <DataTable :value="enrichmentRows" size="small" striped-rows table-style="min-width: 100%">
          <Column :header="t('diag.yearsCovered')" sortable>
            <template #body="{ data: row }">
              <Tag :value="enrichmentRunLabel(row.label)" severity="info" />
            </template>
          </Column>
          <Column :header="t('diag.sourceCoverage')">
            <template #body="{ data: row }">
              <div class="coverage-tags">
                <Tag
                  :value="t('diag.rnRegister')"
                  :severity="
                    enrichmentSeverity(
                      row.rnAvailable,
                      row.rnExactAddress > 0 || row.rnRegionId > 0,
                    )
                  "
                />
                <Tag
                  :value="t('diag.evBuildings')"
                  :severity="enrichmentSeverity(row.evBuildingAvailable, row.evBuildingMatch > 0)"
                />
                <Tag
                  :value="t('diag.evParcels')"
                  :severity="enrichmentSeverity(row.evParcelAvailable, row.evParcelMatch > 0)"
                />
                <Tag
                  :value="t('diag.knPolygons')"
                  :severity="enrichmentSeverity(row.knAvailable, row.knPolygonMatch > 0)"
                />
                <Tag
                  :value="t('diag.gjiInfrastructure')"
                  :severity="
                    enrichmentSeverity(
                      row.gjiAvailable,
                      row.gjiVodovodNearby > 0 || row.gjiKanalizacijaNearby > 0,
                    )
                  "
                />
                <Tag
                  :value="t('diag.emvZones')"
                  :severity="
                    enrichmentSeverity(
                      row.emvAvailable || row.emvSpatialEnabled,
                      row.emvZoneMatch > 0,
                    )
                  "
                />
              </div>
            </template>
          </Column>
          <Column field="rnExactAddress" :header="t('diag.exactAddressMatches')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.rnExactAddress) }}</template>
          </Column>
          <Column field="rnRegionId" :header="t('diag.regionIdsRecovered')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.rnRegionId) }}</template>
          </Column>
          <Column field="evBuildingMatch" :header="t('diag.evBuildingMatches')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.evBuildingMatch) }}</template>
          </Column>
          <Column field="evParcelMatch" :header="t('diag.evParcelMatches')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.evParcelMatch) }}</template>
          </Column>
          <Column field="knPolygonMatch" :header="t('diag.knPolygonMatches')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.knPolygonMatch) }}</template>
          </Column>
          <Column field="gjiVodovodNearby" :header="t('diag.gjiVodovodMatches')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.gjiVodovodNearby) }}</template>
          </Column>
          <Column field="gjiKanalizacijaNearby" :header="t('diag.gjiKanalizacijaMatches')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.gjiKanalizacijaNearby) }}</template>
          </Column>
          <Column field="emvZoneMatch" :header="t('diag.emvZoneMatches')" sortable>
            <template #body="{ data: row }">{{ formatNumber(row.emvZoneMatch) }}</template>
          </Column>
          <Column :header="t('diag.enrichmentSources')">
            <template #body="{ data: row }">
              <span class="muted source-cell">{{ enrichmentSourcesLabel(row) }}</span>
            </template>
          </Column>
        </DataTable>
      </div>

      <!-- Compare metrics charts -->
      <div class="card diagnostics-card compare-card">
        <div class="focus-head">
          <div>
            <h2 class="section-title">{{ t('diag.compareMetrics') }}</h2>
            <p class="muted">{{ t('diag.byPropertyType') }} / {{ t('diag.byRegion') }}</p>
          </div>
          <Select
            v-model="selectedMetric"
            :options="metricOptions"
            option-label="label"
            option-value="value"
          />
        </div>

        <div v-if="perTypeChart" class="chart-block">
          <h3>{{ t('diag.byPropertyType') }}</h3>
          <div class="chart-frame">
            <Bar :data="perTypeChart" :options="chartOptions" />
          </div>
        </div>

        <div v-if="perRegionChart">
          <h3>{{ t('diag.byRegion') }}</h3>
          <div class="chart-frame">
            <Bar :data="perRegionChart" :options="chartOptions" />
          </div>
        </div>
      </div>

      <!-- Feature importance -->
      <div v-if="featureHighlights.length" class="card diagnostics-card">
        <PageHeader
          compact
          :eyebrow="t('diag.topFeatures')"
          :title="t('diag.topFeatures')"
          :description="t('diag.topFeaturesDesc')"
        />
        <div class="feature-list">
          <div v-for="item in featureHighlights" :key="item.feature" class="feature-row">
            <div class="feature-copy">
              <strong>{{ item.label }}</strong>
              <small>{{ item.feature }}</small>
            </div>
            <div class="feature-bar">
              <span :style="{ width: `${Math.max(10, Math.round(item.importance * 100))}%` }" />
            </div>
            <strong>{{ formatMetric(item.importance) }}</strong>
          </div>
        </div>
      </div>

      <!-- Per-type metrics table -->
      <div v-if="model.info.per_type_metrics" class="card diagnostics-card">
        <PageHeader compact :eyebrow="t('diag.perTypeTable')" :title="t('diag.perTypeTable')" />
        <EmptyState
          v-if="!Object.keys(model.info.per_type_metrics).length"
          icon="📊"
          :message="t('empty.noResults')"
        />
        <DataTable
          v-else
          :value="perTypeRows"
          :row-class="perTypeRowClass"
          size="small"
          striped-rows
          table-style="min-width: 100%"
        >
          <Column field="typeLabel" :header="t('diag.type')" sortable />
          <Column field="mae" header="MAE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.mae) }}</template>
          </Column>
          <Column field="rmse" header="RMSE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.rmse) }}</template>
          </Column>
          <Column field="r2" header="R²" sortable>
            <template #body="{ data }">
              <Tag :value="formatMetric(data.r2)" :severity="r2Severity(data.r2)" />
            </template>
          </Column>
          <Column field="mape" header="MAPE" sortable>
            <template #body="{ data }">{{ formatMape(data.mape) }}</template>
          </Column>
          <Column field="n_train" :header="t('diag.trainSamples')" sortable>
            <template #body="{ data }">{{ formatNumber(data.n_train) }}</template>
          </Column>
          <Column field="n_test" :header="t('diag.testSamples')" sortable>
            <template #body="{ data }">{{ formatNumber(data.n_test) }}</template>
          </Column>
        </DataTable>
      </div>

      <!-- Per-region metrics table -->
      <div v-if="model.info.per_region_metrics" class="card diagnostics-card">
        <PageHeader compact :eyebrow="t('diag.perRegionTable')" :title="t('diag.perRegionTable')" />
        <EmptyState
          v-if="!Object.keys(model.info.per_region_metrics).length"
          icon="🗺️"
          :message="t('empty.noResults')"
        />
        <DataTable
          v-else
          :value="perRegionRows"
          size="small"
          striped-rows
          table-style="min-width: 100%"
        >
          <Column field="region" :header="t('diag.region')" sortable />
          <Column field="mae" header="MAE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.mae) }}</template>
          </Column>
          <Column field="rmse" header="RMSE" sortable>
            <template #body="{ data }">{{ formatCurrency(data.rmse) }}</template>
          </Column>
          <Column field="r2" header="R²" sortable>
            <template #body="{ data }">{{ formatMetric(data.r2) }}</template>
          </Column>
          <Column field="mape" header="MAPE" sortable>
            <template #body="{ data }">{{ formatMape(data.mape) }}</template>
          </Column>
        </DataTable>
      </div>
    </template>
  </div>
</template>

<style scoped>
  .diagnostics-page {
    display: grid;
    gap: 1rem;
  }

  .diagnostics-hero,
  .diagnostics-card {
    display: grid;
    gap: 1rem;
  }

  .focus-head {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .coverage-tags {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .coverage-source-list {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .coverage-source-item {
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface-muted);
  }

  .section-title,
  .focus-head h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.45rem;
    line-height: 1.04;
  }

  .diagnostics-kpi-grid {
    margin-top: 1rem;
  }

  .compare-card {
    align-items: start;
  }

  .chart-block {
    display: grid;
    gap: 0.8rem;
  }

  .chart-block + .chart-block {
    margin-top: 1.2rem;
  }

  .chart-frame {
    height: 300px;
  }

  .feature-list {
    display: grid;
    gap: 0.8rem;
  }

  .feature-row {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(140px, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
  }

  .feature-copy {
    display: grid;
    gap: 0.15rem;
  }

  .feature-copy small {
    color: var(--text-muted);
  }

  .feature-bar {
    height: 0.7rem;
    overflow: hidden;
    border-radius: 999px;
    background: var(--surface-muted);
  }

  .feature-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(
      90deg,
      var(--primary),
      color-mix(in srgb, var(--primary) 40%, white)
    );
  }

  .source-cell {
    display: inline-block;
    max-width: 28rem;
    white-space: normal;
    word-break: break-word;
  }

  :deep(.active-focus-row) {
    background: color-mix(in srgb, var(--primary) 8%, transparent);
  }

  @media (max-width: 860px) {
    .feature-row {
      grid-template-columns: 1fr;
    }
  }
</style>
