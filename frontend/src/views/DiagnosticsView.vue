<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
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
  import Button from 'primevue/button'
  import DataTable from 'primevue/datatable'
  import Column from 'primevue/column'
  import Skeleton from 'primevue/skeleton'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tabs from 'primevue/tabs'
  import AdminRunDetailPanel from '../components/admin/AdminRunDetailPanel.vue'
  import AdminWorkspaceHero from '../components/admin/AdminWorkspaceHero.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useChartColors } from '../composables/useChartColors'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import { adminWorkspaceLinks } from '../constants/adminWorkspace'
  import EmptyState from '../components/EmptyState.vue'
  import MetricCard from '../components/MetricCard.vue'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { buildGursEnrichmentRows, summarizeGursEnrichment } from '../utils/enrichmentSummary'
  import { useFormat } from '../composables/useFormat'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import PageHeader from '../components/PageHeader.vue'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

  const { t } = useI18n()
  const { formatType } = useFormat()
  const { colors } = useChartColors()
  const model = useModelStore()
  const dataStore = useDataStore()
  const workbench = useWorkbenchStore()
  const diagnosticsCoreLoaded = ref(false)
  const diagnosticsImportanceLoaded = ref(false)
  const diagnosticsImportanceLoading = ref(false)
  const diagnosticsTrainingRunsLoaded = ref(false)
  const diagnosticsTrainingRunsLoading = ref(false)
  const diagnosticsTrainingRunsError = ref('')
  const diagnosticsTrainingDatasetLoaded = ref(false)
  const diagnosticsTrainingDatasetLoading = ref(false)
  const diagnosticsTrainingDatasetError = ref('')

  interface DiagnosticsMetricSummary {
    mae?: number | null
    rmse?: number | null
    r2?: number | null
    mape?: number | null
    median_ae?: number | null
    n_train?: number | null
    n_test?: number | null
  }

  interface DiagnosticsTypeMetric extends DiagnosticsMetricSummary {
    n_train?: number | null
    n_test?: number | null
  }

  interface DiagnosticsRegionMetric extends DiagnosticsMetricSummary {}

  interface DiagnosticsSegmentRow {
    segment: string
    n: number
    r2: number
    mae: number
    rmse: number
    mape?: number | null
  }

  interface DiagnosticsVariantSources {
    rn?: boolean
    ev?: boolean
    emv?: boolean
  }

  interface DiagnosticsSummaryCard {
    label: string
    value: string
    meta?: string
    tone?: 'default' | 'success' | 'warning'
  }

  interface DiagnosticsKeyValueRow {
    key: string
    val: string
  }

  interface DiagnosticsModelInfo {
    version: string
    trained_at: string
    rows: number
    duration_sec?: number | null
    per_type_count: number
    source_csv_path?: string | null
    global_metrics?: DiagnosticsMetricSummary | null
    per_type_metrics?: Record<string, DiagnosticsTypeMetric>
    per_region_metrics?: Record<string, DiagnosticsRegionMetric>
  }

  interface DiagnosticsVariantRow {
    key: string
    label: string
    sources: DiagnosticsVariantSources
    mae?: number | null
    rmse?: number | null
    r2?: number | null
    mape?: number | null
    delta_r2?: number | null
    delta_mae?: number | null
    removedFeatures: string[]
  }

  interface DiagnosticsVariantMatrixRow {
    key: string
    label: string
    sources: DiagnosticsVariantSources
    globalR2?: number | null
    globalMae?: number | null
    combinedR2?: number | null
    combinedMae?: number | null
    perTypeCount: number
  }

  interface DiagnosticsEvBaselineTypeRow {
    n: number
    mae: number
    rmse: number
    r2: number
    model_mae: number
    model_r2: number
  }

  interface DiagnosticsEvBaselineSummary {
    benchmark_metrics: DiagnosticsMetricSummary
    model_metrics_on_coverage: DiagnosticsMetricSummary
    coverage_rows: number
    coverage_ratio?: number | null
    coverage_by_source?: Record<string, number>
    delta_vs_model?: DiagnosticsMetricSummary | null
    per_type_metrics?: Record<string, DiagnosticsEvBaselineTypeRow>
  }

  interface DiagnosticsFilterStage {
    stage: string
    rows: number
    dropped_since_previous: number
    reports: number
  }

  interface DiagnosticsScoreDriverCard {
    label: string
    value: string
    meta: string
  }

  interface DiagnosticsContextChip {
    label: string
    value: string
    tone?: 'accent' | 'success' | 'warning'
  }

  const viewerQuery = useViewerQueryState({
    metric: 'r2',
    property_type: 'all',
    segment_group: 'property_type',
    training_run: '',
    diagnostics_tab: 'overview',
    diagnostics_benchmark_tab: 'variants',
    diagnostics_quality_tab: 'filters',
    diagnostics_insights_tab: 'compare',
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
  const diagnosticsTab = computed({
    get: () => {
      const value = viewerQuery.state.diagnostics_tab
      return ['overview', 'benchmarks', 'quality', 'insights', 'history'].includes(value)
        ? value
        : 'overview'
    },
    set: (value: string) => {
      void viewerQuery.patchState({ diagnostics_tab: value })
    },
  })
  const diagnosticsBenchmarkTab = computed({
    get: () => {
      const value = viewerQuery.state.diagnostics_benchmark_tab
      return ['variants', 'drivers', 'segments'].includes(value) ? value : 'variants'
    },
    set: (value: string) => {
      void viewerQuery.patchState({ diagnostics_benchmark_tab: value })
    },
  })
  const diagnosticsQualityTab = computed({
    get: () => {
      const value = viewerQuery.state.diagnostics_quality_tab
      return ['filters', 'enrichment'].includes(value) ? value : 'filters'
    },
    set: (value: string) => {
      void viewerQuery.patchState({ diagnostics_quality_tab: value })
    },
  })
  const diagnosticsInsightsTab = computed({
    get: () => {
      const value = viewerQuery.state.diagnostics_insights_tab
      return ['compare', 'features', 'types', 'regions'].includes(value) ? value : 'compare'
    },
    set: (value: string) => {
      void viewerQuery.patchState({ diagnostics_insights_tab: value })
    },
  })
  const metrics = ['mae', 'rmse', 'r2', 'mape', 'median_ae'] as const

  function formatMetric(value: number | string | null | undefined, digits = 4) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    return formatNumber(value, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  }

  function formatDuration(value: number | string | null | undefined) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    return `${formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }

  function humanizeStage(stage: string | null | undefined) {
    if (!stage) return '—'
    const label = t('prepare.unknownYear')
    switch (stage) {
      case 'queued':
        return t('prepare.stageQueued')
      case 'initializing':
        return t('prepare.stageInitializing')
      case 'loading_sources':
        return t('prepare.stageLoadingSources')
      case 'loading_pair':
        return t('prepare.stageLoadingPair', { label })
      case 'building_rows':
        return t('prepare.stageBuildingRows', { label })
      case 'enriching_buildings':
        return t('prepare.stageEnrichingBuildings', { label })
      case 'enriching_land':
        return t('prepare.stageEnrichingLand', { label })
      case 'finalizing_pair':
        return t('prepare.stageFinalizingPair', { label })
      case 'merging_outputs':
        return t('prepare.stageMergingOutputs')
      case 'spatial_enrichment_merged':
        return t('prepare.stageSpatialEnrichmentMerged', { rows: '...' })
      case 'completed':
        return t('prepare.stageCompleted')
      case 'error':
        return t('prepare.stageError')
      default:
        return String(stage)
          .replace(/_/g, ' ')
          .replace(/\b\w/g, (char) => char.toUpperCase())
    }
  }

  function segmentGroupLabel(group: string) {
    const labels: Record<string, string> = {
      property_type: t('diag.byPropertyType'),
      sale_type: t('diag.saleTypeSegments'),
      transaction_year: t('diag.yearSegments'),
      parcel_land_type: t('diag.parcelLandTypeSegments'),
    }
    return labels[group] || group
  }

  function formatSegmentLabel(group: string, segment: string) {
    if (group === 'property_type') return formatType(segment)
    if (group === 'sale_type') {
      const normalized = String(segment).trim()
      if (normalized === '1') return t('diag.saleTypeOpenMarket')
      if (normalized === '2') return t('diag.saleTypeAuction')
      return normalized || '—'
    }
    if (group === 'parcel_land_type') {
      const key = `diag.landType${String(segment).trim()}`
      const translated = t(key)
      if (translated !== key) return translated
      if (segment === 'unknown') return t('common.noData')
      return segment
    }
    return segment
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

  const selectedTypeMetrics = computed<DiagnosticsMetricSummary | null>(() => {
    if (selectedType.value === 'all') return model.info?.global_metrics || null
    return model.info?.per_type_metrics?.[selectedType.value] || null
  })
  const selectedTrainingRun = computed(() => workbench.selectedTrainingRun)
  const diagnosticsFocusDescription = computed(() =>
    selectedType.value === 'all'
      ? t('diag.focusAllDesc')
      : t('diag.focusTypeDesc', { type: formatType(selectedType.value) }),
  )
  const diagnosticsTabLabel = computed(() => {
    if (diagnosticsTab.value === 'benchmarks') return t('diag.variantBenchmarks')
    if (diagnosticsTab.value === 'quality') return t('diag.datasetEnrichment')
    if (diagnosticsTab.value === 'insights') return t('diag.topFeatures')
    if (diagnosticsTab.value === 'history') return t('model.trainingHistory')
    return t('common.overview')
  })
  const diagnosticsControlChips = computed<DiagnosticsContextChip[]>(() => {
    const chips: DiagnosticsContextChip[] = [
      {
        label: t('nav.diagnostics'),
        value: diagnosticsTabLabel.value,
        tone: 'accent',
      },
      {
        label: t('diag.focusType'),
        value: selectedType.value === 'all' ? t('diag.allTypes') : formatType(selectedType.value),
      },
      {
        label: t('diag.compareMetrics'),
        value: selectedMetric.value.toUpperCase(),
      },
    ]

    if (segmentGroupOptions.value.length) {
      chips.push({
        label: t('diag.worstSegments'),
        value: segmentGroupLabel(selectedSegmentGroup.value),
      })
    }

    return chips
  })

  const focusMetrics = computed<DiagnosticsSummaryCard[]>(() => {
    const metricsData = selectedTypeMetrics.value
    if (!metricsData) return []
    return [
      { label: 'MAE', value: formatCurrency(metricsData.mae), meta: t('diag.maeDesc') },
      { label: 'RMSE', value: formatCurrency(metricsData.rmse), meta: t('diag.rmseDesc') },
      { label: 'R²', value: formatMetric(metricsData.r2), meta: t('diag.r2Desc') },
      {
        label: 'MAPE',
        value:
          metricsData.mape == null
            ? '—'
            : formatPercent(metricsData.mape, { scale: 0.01, minimumFractionDigits: 1 }),
        meta: t('diag.mapeDesc'),
      },
      {
        label: t('diag.medianError'),
        value: formatCurrency(metricsData.median_ae),
        meta: t('diag.medianDesc'),
      },
      {
        label: t('diag.trainSamples'),
        value: formatNumber(metricsData.n_train),
        meta:
          selectedType.value === 'all'
            ? t('diag.focusAllDesc')
            : t('diag.focusTypeDesc', { type: formatType(selectedType.value) }),
      },
      {
        label: t('diag.testSamples'),
        value: formatNumber(metricsData.n_test),
        meta: t('diag.testRows'),
      },
    ]
  })

  const featureHighlights = computed(() => model.importance.slice(0, 8))

  function getChartPalette() {
    return {
      primary: colors.value.chart1 || colors.value.primary,
      primarySoft: colors.value.chart2 || colors.value.secondary || colors.value.primary,
      success: colors.value.chart3 || colors.value.success,
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

  const chartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: colors.value.surface,
        titleColor: colors.value.text,
        bodyColor: colors.value.textMuted,
        borderColor: colors.value.border,
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        ticks: {
          color: colors.value.textMuted,
        },
        grid: {
          display: false,
        },
        border: {
          color: colors.value.border,
        },
      },
      y: {
        beginAtZero: true,
        ticks: {
          color: colors.value.textMuted,
        },
        grid: {
          color: colors.value.border,
        },
        border: {
          color: colors.value.border,
        },
      },
    },
  }))

  const combinedMetrics = computed<DiagnosticsSummaryCard[]>(() => {
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

  const variantBenchmarkCards = computed<DiagnosticsSummaryCard[]>(() => {
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

  const variantBenchmarkRows = computed<DiagnosticsVariantRow[]>(() => {
    const variants = variantBenchmarks.value
    if (!variants) return []

    return Object.entries(variants).map(([key, variant]) => {
      const typedVariant = variant as {
        label?: string
        enabled_sources?: DiagnosticsVariantSources
        metrics?: DiagnosticsMetricSummary
        delta_vs_full_global?: DiagnosticsMetricSummary
        removed_features?: unknown
      }

      return {
        key,
        label: typedVariant.label || key,
        sources: typedVariant.enabled_sources || {},
        mae: typedVariant.metrics?.mae,
        rmse: typedVariant.metrics?.rmse,
        r2: typedVariant.metrics?.r2,
        mape: typedVariant.metrics?.mape,
        delta_r2: typedVariant.delta_vs_full_global?.r2,
        delta_mae: typedVariant.delta_vs_full_global?.mae,
        removedFeatures: Array.isArray(typedVariant.removed_features)
          ? typedVariant.removed_features.filter((item): item is string => typeof item === 'string')
          : [],
      }
    })
  })

  const variantMatrixRows = computed<DiagnosticsVariantMatrixRow[]>(() => {
    const variants = variantMatrix.value
    if (!variants) return []

    return Object.entries(variants).map(([key, variant]) => {
      const typedVariant = variant as {
        label?: string
        enabled_sources?: DiagnosticsVariantSources
        global_metrics?: DiagnosticsMetricSummary
        combined_metrics?: DiagnosticsMetricSummary
        per_type_count?: number | null
      }

      return {
        key,
        label: typedVariant.label || key,
        sources: typedVariant.enabled_sources || {},
        globalR2: typedVariant.global_metrics?.r2,
        globalMae: typedVariant.global_metrics?.mae,
        combinedR2: typedVariant.combined_metrics?.r2,
        combinedMae: typedVariant.combined_metrics?.mae,
        perTypeCount: typedVariant.per_type_count ?? 0,
      }
    })
  })

  const evBaseline = computed<DiagnosticsEvBaselineSummary | null>(
    () => model.diagnostics?.ev_baseline_metrics || null,
  )

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

  const diagnosticsBenchmarkChips = computed<DiagnosticsContextChip[]>(() => [
    {
      label: t('diag.variantBenchmarks'),
      value: formatNumber(variantBenchmarkRows.value.length),
      tone: 'accent',
    },
    {
      label: t('diag.focusType'),
      value: selectedType.value === 'all' ? t('diag.allTypes') : formatType(selectedType.value),
    },
    {
      label: t('diag.compareMetrics'),
      value: selectedMetric.value.toUpperCase(),
    },
  ])

  const variantSpotlightCards = computed<DiagnosticsSummaryCard[]>(() => {
    if (!variantBenchmarkRows.value.length) return []

    const bestR2 = [...variantBenchmarkRows.value]
      .filter((row) => row.r2 != null)
      .sort((left, right) => Number(right.r2 ?? -Infinity) - Number(left.r2 ?? -Infinity))[0]

    const lowestMae = [...variantBenchmarkRows.value]
      .filter((row) => row.mae != null)
      .sort((left, right) => Number(left.mae ?? Infinity) - Number(right.mae ?? Infinity))[0]

    const broadestSources = [...variantBenchmarkRows.value].sort(
      (left, right) => countEnabledSources(right.sources) - countEnabledSources(left.sources),
    )[0]

    const cards: DiagnosticsSummaryCard[] = []

    if (bestR2) {
      cards.push({
        label: t('diag.globalR2'),
        value: formatMetric(bestR2.r2, 3),
        meta: `${bestR2.label} · ${variantSourceSummary(bestR2.sources)}`,
        tone: 'success',
      })
    }

    if (lowestMae) {
      cards.push({
        label: t('diag.globalMae'),
        value: formatCurrency(lowestMae.mae),
        meta: `${lowestMae.label} · ${variantSourceSummary(lowestMae.sources)}`,
        tone: 'success',
      })
    }

    if (broadestSources) {
      cards.push({
        label: t('diag.sources'),
        value: variantSourceSummary(broadestSources.sources),
        meta: broadestSources.label,
      })
    }

    return cards
  })

  const evBaselinePerTypeRows = computed<
    Array<
      DiagnosticsEvBaselineTypeRow & { propertyType: string; typeLabel: string; delta_mae: number }
    >
  >(() => {
    const rows = evBaseline.value?.per_type_metrics
    if (!rows) return []
    return Object.entries(rows).map(([propertyType, metricsData]) => {
      const typedMetrics = metricsData as DiagnosticsEvBaselineTypeRow
      return {
        propertyType,
        typeLabel: formatType(propertyType),
        n: typedMetrics.n,
        mae: typedMetrics.mae,
        rmse: typedMetrics.rmse,
        r2: typedMetrics.r2,
        model_mae: typedMetrics.model_mae,
        model_r2: typedMetrics.model_r2,
        delta_mae: typedMetrics.mae - typedMetrics.model_mae,
      }
    })
  })

  const diagnosticsSummaryCards = computed<DiagnosticsSummaryCard[]>(() => [
    {
      label: t('diag.globalR2'),
      value:
        model.info?.global_metrics?.r2 != null
          ? formatMetric(model.info.global_metrics.r2, 3)
          : '—',
      meta: t('diag.globalR2Desc'),
      tone: 'success' as const,
    },
    {
      label: t('diag.globalMae'),
      value:
        model.info?.global_metrics?.mae != null
          ? formatCurrency(model.info.global_metrics.mae)
          : '—',
      meta: t('diag.globalMaeDesc'),
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

  const modelDetailsRows = computed<DiagnosticsKeyValueRow[]>(() => {
    if (!model.info) return []
    const rows: DiagnosticsKeyValueRow[] = [
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

  const perTypeRows = computed<
    Array<DiagnosticsTypeMetric & { propertyType: string; typeLabel: string }>
  >(() => {
    const ptm = model.info?.per_type_metrics
    if (!ptm) return []
    return Object.entries(ptm).map(([propertyType, metricsData]) => {
      const typedMetrics = metricsData as DiagnosticsTypeMetric
      return {
        propertyType,
        typeLabel: formatType(propertyType),
        mae: typedMetrics.mae,
        rmse: typedMetrics.rmse,
        r2: typedMetrics.r2,
        mape: typedMetrics.mape,
        n_train: typedMetrics.n_train,
        n_test: typedMetrics.n_test,
      }
    })
  })

  function perTypeRowClass(data: { propertyType: string }) {
    return selectedType.value === data.propertyType ? 'active-focus-row' : ''
  }

  const perRegionRows = computed<Array<DiagnosticsRegionMetric & { region: string }>>(() => {
    const prm = model.info?.per_region_metrics
    if (!prm) return []
    return Object.entries(prm).map(([region, metricsData]) => {
      const typedMetrics = metricsData as DiagnosticsRegionMetric
      return {
        region,
        mae: typedMetrics.mae,
        rmse: typedMetrics.rmse,
        r2: typedMetrics.r2,
        mape: typedMetrics.mape,
      }
    })
  })

  const diagnosticsInsightsChips = computed<DiagnosticsContextChip[]>(() => [
    {
      label: t('diag.topFeatures'),
      value: formatNumber(featureHighlights.value.length),
      tone: 'accent',
    },
    {
      label: t('diag.perTypeTable'),
      value: formatNumber(perTypeRows.value.length),
    },
    {
      label: t('diag.perRegionTable'),
      value: formatNumber(perRegionRows.value.length),
    },
  ])

  const preparationMetadata = computed(
    () =>
      model.diagnostics?.data_preparation ||
      dataStore.trainingDataset?.preparation_metadata ||
      null,
  )

  const filterRows = computed<
    Array<{
      group: string
      groupLabel: string
      stage: string
      stageLabel: string
      rows: number
      dropped_since_previous: number
      reports: number
    }>
  >(() => {
    const summary = preparationMetadata.value?.filter_summary
    if (!summary) return []
    return Object.entries(summary).flatMap(([group, stages]) =>
      (Array.isArray(stages) ? stages : []).map((stage) => {
        const typedStage = stage as DiagnosticsFilterStage
        return {
          group,
          groupLabel: group === 'building' ? t('diag.buildingFlow') : t('diag.landFlow'),
          stage: typedStage.stage,
          stageLabel: humanizeStage(typedStage.stage),
          rows: typedStage.rows,
          dropped_since_previous: typedStage.dropped_since_previous,
          reports: typedStage.reports,
        }
      }),
    )
  })

  const filterOverviewCards = computed<DiagnosticsSummaryCard[]>(() => {
    if (!filterRows.value.length) return []

    const buildingStages = filterRows.value.filter((row) => row.group === 'building')
    const landStages = filterRows.value.filter((row) => row.group === 'land')
    const lastBuildingStage = buildingStages[buildingStages.length - 1]
    const lastLandStage = landStages[landStages.length - 1]
    const biggestDrop = [...filterRows.value].sort(
      (left, right) => right.dropped_since_previous - left.dropped_since_previous,
    )[0]

    const cards: DiagnosticsSummaryCard[] = []

    if (buildingStages.length) {
      cards.push({
        label: t('diag.buildingFlow'),
        value: formatNumber(lastBuildingStage?.rows || 0),
        meta: t('diag.rowsKept'),
        tone: 'success',
      })
    }

    if (landStages.length) {
      cards.push({
        label: t('diag.landFlow'),
        value: formatNumber(lastLandStage?.rows || 0),
        meta: t('diag.rowsKept'),
        tone: 'success',
      })
    }

    if (biggestDrop) {
      cards.push({
        label: t('diag.rowsDropped'),
        value: formatNumber(biggestDrop.dropped_since_previous),
        meta: `${biggestDrop.groupLabel} · ${biggestDrop.stageLabel}`,
        tone: 'warning',
      })
    }

    cards.push({
      label: t('diag.stage'),
      value: formatNumber(filterRows.value.length),
      meta: t('diag.filterSummary'),
    })

    return cards
  })

  const enrichmentRows = computed(() =>
    buildGursEnrichmentRows(
      preparationMetadata.value?.reports,
      preparationMetadata.value?.enrichment_summary,
    ),
  )

  const enrichmentTotals = computed(() => summarizeGursEnrichment(enrichmentRows.value))

  const enrichmentSourceCards = computed<DiagnosticsSummaryCard[]>(() => {
    if (!enrichmentRows.value.length) return []

    const totalRuns = enrichmentRows.value.length
    const buildCard = (
      label: string,
      totalMatches: number,
      availableRuns: number,
      matchedRuns: number,
    ): DiagnosticsSummaryCard => ({
      label,
      value: formatNumber(totalMatches),
      meta: `${formatNumber(matchedRuns)} / ${formatNumber(totalRuns)} ${t('diag.yearsCovered')}`,
      tone: matchedRuns > 0 ? 'success' : availableRuns > 0 ? 'warning' : 'default',
    })

    return [
      buildCard(
        t('diag.rnRegister'),
        enrichmentTotals.value.rnExactAddress + enrichmentTotals.value.rnRegionId,
        enrichmentRows.value.filter((row) => row.rnAvailable).length,
        enrichmentRows.value.filter((row) => row.rnExactAddress > 0 || row.rnRegionId > 0).length,
      ),
      buildCard(
        t('diag.evBuildings'),
        enrichmentTotals.value.evBuildingMatch,
        enrichmentRows.value.filter((row) => row.evBuildingAvailable).length,
        enrichmentRows.value.filter((row) => row.evBuildingMatch > 0).length,
      ),
      buildCard(
        t('diag.evParcels'),
        enrichmentTotals.value.evParcelMatch,
        enrichmentRows.value.filter((row) => row.evParcelAvailable).length,
        enrichmentRows.value.filter((row) => row.evParcelMatch > 0).length,
      ),
      buildCard(
        t('diag.knPolygons'),
        enrichmentTotals.value.knPolygonMatch,
        enrichmentRows.value.filter((row) => row.knAvailable).length,
        enrichmentRows.value.filter((row) => row.knPolygonMatch > 0).length,
      ),
      buildCard(
        t('diag.gjiInfrastructure'),
        enrichmentTotals.value.gjiVodovodNearby + enrichmentTotals.value.gjiKanalizacijaNearby,
        enrichmentRows.value.filter((row) => row.gjiAvailable).length,
        enrichmentRows.value.filter(
          (row) => row.gjiVodovodNearby > 0 || row.gjiKanalizacijaNearby > 0,
        ).length,
      ),
      buildCard(
        t('diag.emvZones'),
        enrichmentTotals.value.emvZoneMatch,
        enrichmentRows.value.filter((row) => row.emvAvailable || row.emvSpatialEnabled).length,
        enrichmentRows.value.filter((row) => row.emvZoneMatch > 0).length,
      ),
    ]
  })

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

  const diagnosticsQualityChips = computed<DiagnosticsContextChip[]>(() => [
    {
      label: t('diag.filterSummary'),
      value: formatNumber(filterRows.value.length),
      tone: 'accent',
    },
    {
      label: t('diag.datasetEnrichment'),
      value: formatNumber(enrichmentRows.value.length),
    },
    {
      label: t('diag.yearsCovered'),
      value: Array.isArray(preparationMetadata.value?.reports)
        ? formatNumber(preparationMetadata.value.reports.length)
        : t('common.noData'),
    },
  ])

  const segmentRows = computed(
    () => model.diagnostics?.segment_diagnostics?.[selectedSegmentGroup.value] || [],
  )

  const scoreDriverCards = computed<DiagnosticsScoreDriverCard[]>(() => {
    const diagnostics = model.diagnostics?.segment_diagnostics || {}
    const cards: DiagnosticsScoreDriverCard[] = []
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
        value: `${formatSegmentLabel('sale_type', saleType.segment)} · R² ${formatMetric(saleType.r2, 3)}`,
        meta: `${t('diag.testSamples')}: ${formatNumber(saleType.n)}`,
      })
    }
    const landType = diagnostics.parcel_land_type?.[0]
    if (landType) {
      cards.push({
        label: t('diag.worstParcelLandType'),
        value: `${formatSegmentLabel('parcel_land_type', landType.segment)} · R² ${formatMetric(landType.r2, 3)}`,
        meta: `${t('diag.testSamples')}: ${formatNumber(landType.n)}`,
      })
    }
    return cards
  })

  function r2Severity(value: number | null | undefined) {
    if (value > 0.7) return 'success'
    if (value > 0.4) return 'warn'
    return 'danger'
  }

  function formatMape(mape: number | string | null | undefined) {
    return mape == null ? '—' : formatPercent(mape, { scale: 0.01, minimumFractionDigits: 1 })
  }

  function formatSignedNumber(value: number | string | null | undefined, digits = 2) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    const sign = Number(value) > 0 ? '+' : ''
    return `${sign}${formatMetric(value, digits)}`
  }

  function formatSignedCurrency(value: number | string | null | undefined) {
    if (value == null || Number.isNaN(Number(value))) return '—'
    const sign = Number(value) > 0 ? '+' : ''
    return `${sign}${formatCurrency(value)}`
  }

  function countEnabledSources(sources?: DiagnosticsVariantSources | null) {
    return (
      Number(Boolean(sources?.rn)) + Number(Boolean(sources?.ev)) + Number(Boolean(sources?.emv))
    )
  }

  function variantSourceSummary(sources?: DiagnosticsVariantSources | null) {
    const labels = []
    if (sources?.rn) labels.push('RN')
    if (sources?.ev) labels.push('EV')
    if (sources?.emv) labels.push('EMV')
    return labels.length ? labels.join(' + ') : t('diag.etnOnly')
  }

  function enrichmentRunLabel(label: string) {
    return label === 'single' ? t('diag.currentRun') : String(label)
  }

  function enrichmentSeverity(
    available: boolean | null | undefined,
    matched: boolean | null | undefined,
  ) {
    if (matched) return 'success'
    if (available) return 'warn'
    return 'contrast'
  }

  function enrichmentSourcesLabel(row: { matchedSources: string[]; sources: string[] }) {
    if (row.matchedSources.length) return row.matchedSources.join(', ')
    if (row.sources.length) {
      return t('diag.detectedOnlySources', { sources: row.sources.join(', ') })
    }
    return t('common.noData')
  }

  async function ensureDiagnosticsCoreLoaded(force = false) {
    if (!force && diagnosticsCoreLoaded.value) return
    await Promise.allSettled([model.fetchInfo(force), model.fetchDiagnostics(force)])
    diagnosticsCoreLoaded.value = true
    if (
      segmentGroupOptions.value.length &&
      !segmentGroupOptions.value.some((item) => item.value === selectedSegmentGroup.value)
    ) {
      selectedSegmentGroup.value = segmentGroupOptions.value[0].value
    }
  }

  async function ensureDiagnosticsImportanceLoaded(force = false) {
    if (!force && (diagnosticsImportanceLoaded.value || diagnosticsImportanceLoading.value)) return
    diagnosticsImportanceLoading.value = true
    try {
      await model.fetchImportance(force)
      diagnosticsImportanceLoaded.value = true
    } finally {
      diagnosticsImportanceLoading.value = false
    }
  }

  async function ensureDiagnosticsTrainingRunsLoaded(force = false) {
    if (diagnosticsTrainingRunsLoading.value) return
    if (!force && diagnosticsTrainingRunsLoaded.value) return
    diagnosticsTrainingRunsLoading.value = true
    diagnosticsTrainingRunsError.value = ''
    try {
      await workbench.fetchTrainingRuns(force)
      diagnosticsTrainingRunsLoaded.value = true
    } catch (error) {
      diagnosticsTrainingRunsLoaded.value = false
      diagnosticsTrainingRunsError.value = getApiErrorMessage(error, t)
    } finally {
      diagnosticsTrainingRunsLoading.value = false
    }
  }

  async function ensureDiagnosticsTrainingDatasetLoaded(force = false) {
    if (diagnosticsTrainingDatasetLoading.value) return
    if (!force && diagnosticsTrainingDatasetLoaded.value) return
    diagnosticsTrainingDatasetLoading.value = true
    diagnosticsTrainingDatasetError.value = ''
    try {
      await dataStore.fetchTrainingDataset(force)
      diagnosticsTrainingDatasetLoaded.value = true
    } catch (error) {
      diagnosticsTrainingDatasetLoaded.value = false
      diagnosticsTrainingDatasetError.value = getApiErrorMessage(error, t)
    } finally {
      diagnosticsTrainingDatasetLoading.value = false
    }
  }

  async function ensureOverviewRunDetail(force = false) {
    await ensureDiagnosticsTrainingRunsLoaded(force)
    const initialTrainingRunId = selectedTrainingRunId.value || workbench.trainingRuns[0]?.id
    if (!initialTrainingRunId) return

    if (
      force ||
      selectedTrainingRunId.value !== initialTrainingRunId ||
      selectedTrainingRun.value?.id !== initialTrainingRunId
    ) {
      await loadTrainingRunDetail(initialTrainingRunId)
    }
  }

  async function loadActiveDiagnosticsTabData(force = false) {
    if (diagnosticsTab.value === 'overview' || diagnosticsTab.value === 'history') {
      await ensureOverviewRunDetail(force)
      return
    }

    if (diagnosticsTab.value === 'quality' && !model.diagnostics?.data_preparation) {
      await ensureDiagnosticsTrainingDatasetLoaded(force)
      return
    }

    if (diagnosticsTab.value === 'insights' && diagnosticsInsightsTab.value === 'features') {
      await ensureDiagnosticsImportanceLoaded(force)
    }
  }

  async function bootstrapDiagnosticsPage(force = false) {
    await ensureDiagnosticsCoreLoaded(force)
    await loadActiveDiagnosticsTabData(force)
  }

  onMounted(async () => {
    await bootstrapDiagnosticsPage()
  })

  watch([diagnosticsTab, diagnosticsInsightsTab], () => {
    void loadActiveDiagnosticsTabData()
  })

  async function loadTrainingRunDetail(jobId: string) {
    if (!jobId) return
    if (selectedTrainingRunId.value !== jobId) {
      selectedTrainingRunId.value = jobId
      return
    }
    await workbench.fetchTrainingRunDetail(jobId)
  }

  watch(
    () => selectedTrainingRunId.value,
    (jobId, previousJobId) => {
      if (!jobId || jobId === previousJobId) return
      void workbench.fetchTrainingRunDetail(jobId)
    },
  )
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
        <Button
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="() => void bootstrapDiagnosticsPage(true)"
        />
        <Button
          :as="RouterLink"
          to="/admin/dokaz"
          class="hero-link"
          severity="secondary"
          outlined
          icon="pi pi-chart-line"
          :label="t('nav.benchmark')"
        />
        <SavedWorkspaceMenu
          page="diagnostics"
          :state="{
            page: 'diagnostics',
            filters: {
              metric: selectedMetric,
              property_type: selectedType,
              segment_group: selectedSegmentGroup,
              training_run: selectedTrainingRunId,
              diagnostics_tab: diagnosticsTab,
              diagnostics_benchmark_tab: diagnosticsBenchmarkTab,
              diagnostics_quality_tab: diagnosticsQualityTab,
              diagnostics_insights_tab: diagnosticsInsightsTab,
            },
          }"
        />
      </template>
    </AdminWorkspaceHero>

    <div
      v-if="model.loading && !model.info"
      class="card diagnostics-card diagnostics-loading"
      aria-busy="true"
    >
      <div class="diagnostics-loading-grid">
        <Skeleton width="42%" height="1rem" />
        <Skeleton width="70%" height="0.95rem" />
        <Skeleton width="100%" height="8rem" border-radius="var(--radius-sm)" />
        <div class="kpi-grid">
          <Skeleton
            v-for="idx in 4"
            :key="idx"
            width="100%"
            height="5.6rem"
            border-radius="var(--radius-sm)"
          />
        </div>
      </div>
    </div>

    <div v-else-if="!model.info" class="card diagnostics-card state-card-stack" role="alert">
      <EmptyState icon="pi pi-chart-bar" :message="t('diag.noModel')" />
      <div class="state-card-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="() => void bootstrapDiagnosticsPage(true)"
        />
      </div>
    </div>

    <template v-else>
      <section class="card diagnostics-card diagnostics-command-deck">
        <PageHeader
          compact
          :eyebrow="t('nav.diagnostics')"
          :title="t('diag.focusType')"
          :description="diagnosticsFocusDescription"
        >
          <template #meta>
            <div class="context-chip-strip">
              <span
                v-for="chip in diagnosticsControlChips"
                :key="`${chip.label}-${chip.value}`"
                class="context-chip"
                :class="chip.tone ? `is-${chip.tone}` : ''"
              >
                <span>{{ chip.label }}</span>
                <strong>{{ chip.value }}</strong>
              </span>
            </div>
          </template>

          <template #actions>
            <div class="diagnostics-deck-actions">
              <div class="field-inline">
                <span>{{ t('diag.focusType') }}</span>
                <Select
                  v-model="selectedType"
                  :options="typeOptions"
                  option-label="label"
                  option-value="value"
                  class="focus-type-select"
                />
              </div>

              <div class="field-inline">
                <span>{{ t('diag.compareMetrics') }}</span>
                <Select
                  v-model="selectedMetric"
                  :options="metricOptions"
                  option-label="label"
                  option-value="value"
                />
              </div>

              <div v-if="segmentGroupOptions.length" class="field-inline">
                <span>{{ t('diag.worstSegments') }}</span>
                <Select
                  v-model="selectedSegmentGroup"
                  :options="segmentGroupOptions"
                  option-label="label"
                  option-value="value"
                />
              </div>
            </div>
          </template>
        </PageHeader>
      </section>

      <Tabs v-model:value="diagnosticsTab" class="diagnostics-tabs">
        <TabList>
          <Tab value="overview">{{ t('common.overview') }}</Tab>
          <Tab value="benchmarks">{{ t('diag.variantBenchmarks') }}</Tab>
          <Tab value="quality">{{ t('diag.datasetEnrichment') }}</Tab>
          <Tab value="insights">{{ t('diag.topFeatures') }}</Tab>
          <Tab value="history">{{ t('model.trainingHistory') }}</Tab>
        </TabList>

        <TabPanels>
          <TabPanel value="overview">
            <section class="diagnostics-summary-grid">
              <SectionPanel
                class="diagnostics-panel diagnostics-focus-panel"
                :eyebrow="t('diag.focusType')"
                :title="t('diag.focusType')"
                :description="diagnosticsFocusDescription"
              >
                <template #actions>
                  <Select
                    v-model="selectedType"
                    :options="typeOptions"
                    option-label="label"
                    option-value="value"
                    class="focus-type-select"
                  />
                </template>

                <div class="kpi-grid diagnostics-kpi-grid">
                  <MetricCard
                    v-for="item in focusMetrics"
                    :key="item.label"
                    :label="item.label"
                    :value="item.value"
                    :meta="item.meta"
                    :tone="item.tone"
                  />
                </div>
              </SectionPanel>
            </section>

            <section class="diagnostics-report-grid diagnostics-report-grid--wide">
              <SectionPanel
                v-if="combinedMetrics.length"
                class="diagnostics-panel"
                :eyebrow="t('diag.combinedMetrics')"
                :title="t('diag.combinedMetrics')"
                :description="t('diag.combinedDesc')"
              >
                <div class="kpi-grid">
                  <MetricCard
                    v-for="item in combinedMetrics"
                    :key="item.label"
                    :label="item.label"
                    :value="item.value"
                    :meta="item.meta"
                    :tone="item.tone"
                  />
                </div>
              </SectionPanel>

              <SectionPanel
                class="diagnostics-panel"
                :eyebrow="t('diag.modelDetails')"
                :title="t('diag.modelDetails')"
              >
                <DataTable :value="modelDetailsRows" size="small" table-style="min-width: 100%">
                  <Column field="key" :header="t('diag.property')" />
                  <Column field="val" :header="t('diag.value')" />
                </DataTable>
              </SectionPanel>
            </section>
          </TabPanel>

          <TabPanel value="benchmarks">
            <section class="card diagnostics-card diagnostics-section-intro">
              <div class="diagnostics-section-copy">
                <p class="diagnostics-section-eyebrow">{{ t('nav.benchmark') }}</p>
                <h2>{{ t('diag.variantBenchmarks') }}</h2>
                <p>{{ t('diag.variantBenchmarksDesc') }}</p>
              </div>

              <div class="context-chip-strip">
                <span
                  v-for="chip in diagnosticsBenchmarkChips"
                  :key="`benchmark-${chip.label}-${chip.value}`"
                  class="context-chip"
                  :class="chip.tone ? `is-${chip.tone}` : ''"
                >
                  <span>{{ chip.label }}</span>
                  <strong>{{ chip.value }}</strong>
                </span>
              </div>
            </section>

            <Tabs v-model:value="diagnosticsBenchmarkTab" class="diagnostics-subtabs">
              <TabList>
                <Tab value="variants">{{ t('diag.variantBenchmarks') }}</Tab>
                <Tab value="drivers">{{ t('diag.scoreDrivers') }}</Tab>
                <Tab value="segments">{{ t('diag.worstSegments') }}</Tab>
              </TabList>
              <TabPanels>
                <TabPanel value="variants">
                  <section class="diagnostics-benchmark-grid">
                    <div v-if="variantBenchmarkRows.length" class="card diagnostics-card">
                      <PageHeader
                        compact
                        :eyebrow="t('diag.variantBenchmarks')"
                        :title="t('diag.variantBenchmarks')"
                        :description="t('diag.variantBenchmarksDesc')"
                      />

                      <div
                        v-if="variantSpotlightCards.length"
                        class="kpi-grid diagnostics-kpi-grid"
                      >
                        <MetricCard
                          v-for="item in variantSpotlightCards"
                          :key="`${item.label}-${item.value}`"
                          :label="item.label"
                          :value="item.value"
                          :meta="item.meta"
                          :tone="item.tone"
                        />
                      </div>

                      <div v-if="variantBenchmarkCards.length" class="kpi-grid">
                        <MetricCard
                          v-for="item in variantBenchmarkCards"
                          :key="item.label"
                          :label="item.label"
                          :value="item.value"
                          :meta="item.meta"
                        />
                      </div>

                      <details class="diagnostics-fold">
                        <summary>
                          {{ t('diag.variantBenchmarks') }} ·
                          {{ formatNumber(variantBenchmarkRows.length) }}
                        </summary>

                        <div class="diagnostics-fold-body">
                          <DataTable
                            :value="variantBenchmarkRows"
                            striped-rows
                            table-style="min-width: 100%"
                          >
                            <Column field="label" :header="t('diag.variant')" sortable />
                            <Column :header="t('diag.sources')">
                              <template #body="{ data }">
                                <span class="muted source-cell">{{
                                  variantSourceSummary(data.sources)
                                }}</span>
                              </template>
                            </Column>
                            <Column field="r2" header="R²" sortable>
                              <template #body="{ data }">
                                <Tag
                                  :value="formatMetric(data.r2, 3)"
                                  :severity="r2Severity(data.r2)"
                                />
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
                              <template #body="{ data }">
                                {{ formatSignedNumber(data.delta_r2, 3) }}
                              </template>
                            </Column>
                            <Column field="delta_mae" :header="t('diag.deltaVsFullMae')" sortable>
                              <template #body="{ data }">
                                {{ formatSignedCurrency(data.delta_mae) }}
                              </template>
                            </Column>
                            <Column :header="t('diag.variantRemovedFeatures')">
                              <template #body="{ data }">
                                <span class="muted source-cell">
                                  {{
                                    data.removedFeatures.length
                                      ? data.removedFeatures.join(', ')
                                      : t('common.noData')
                                  }}
                                </span>
                              </template>
                            </Column>
                          </DataTable>
                        </div>
                      </details>
                    </div>

                    <div
                      v-if="variantMatrixRows.length"
                      class="card diagnostics-card benchmark-full"
                    >
                      <PageHeader
                        compact
                        :eyebrow="t('diag.variantMatrix')"
                        :title="t('diag.variantMatrix')"
                        :description="t('diag.variantMatrixDesc')"
                      />

                      <details class="diagnostics-fold">
                        <summary>
                          {{ t('diag.variantMatrix') }} ·
                          {{ formatNumber(variantMatrixRows.length) }}
                        </summary>

                        <div class="diagnostics-fold-body">
                          <DataTable
                            :value="variantMatrixRows"
                            striped-rows
                            table-style="min-width: 100%"
                          >
                            <Column field="label" :header="t('diag.variant')" sortable />
                            <Column :header="t('diag.sources')">
                              <template #body="{ data }">
                                <span class="muted source-cell">{{
                                  variantSourceSummary(data.sources)
                                }}</span>
                              </template>
                            </Column>
                            <Column field="globalR2" :header="t('diag.globalR2')" sortable>
                              <template #body="{ data }">
                                {{ formatMetric(data.globalR2, 3) }}
                              </template>
                            </Column>
                            <Column field="combinedR2" :header="t('diag.routedR2')" sortable>
                              <template #body="{ data }">
                                {{ formatMetric(data.combinedR2, 3) }}
                              </template>
                            </Column>
                            <Column field="globalMae" :header="t('diag.globalMae')" sortable>
                              <template #body="{ data }">
                                {{ formatCurrency(data.globalMae) }}
                              </template>
                            </Column>
                            <Column field="combinedMae" :header="t('diag.routedMae')" sortable>
                              <template #body="{ data }">
                                {{ formatCurrency(data.combinedMae) }}
                              </template>
                            </Column>
                            <Column field="perTypeCount" :header="t('diag.perTypeModels')" sortable>
                              <template #body="{ data }">
                                {{ formatNumber(data.perTypeCount) }}
                              </template>
                            </Column>
                          </DataTable>
                        </div>
                      </details>
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
                          {{ variantSourceSummary({ [source]: true }) }}: {{ formatNumber(count) }}
                        </span>
                      </div>

                      <details v-if="evBaselinePerTypeRows.length" class="diagnostics-fold">
                        <summary>
                          {{ t('diag.perTypeTable') }} ·
                          {{ formatNumber(evBaselinePerTypeRows.length) }}
                        </summary>

                        <div class="diagnostics-fold-body">
                          <DataTable
                            :value="evBaselinePerTypeRows"
                            size="small"
                            striped-rows
                            table-style="min-width: 100%"
                          >
                            <Column field="typeLabel" :header="t('diag.type')" sortable />
                            <Column field="n" :header="t('diag.sampleCount')" sortable>
                              <template #body="{ data }">{{ formatNumber(data.n) }}</template>
                            </Column>
                            <Column
                              field="model_mae"
                              :header="t('diag.modelMaeOnCoverage')"
                              sortable
                            >
                              <template #body="{ data }">
                                {{ formatCurrency(data.model_mae) }}
                              </template>
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
                                <Tag
                                  :value="formatMetric(data.model_r2, 3)"
                                  :severity="r2Severity(data.model_r2)"
                                />
                              </template>
                            </Column>
                            <Column field="r2" :header="t('diag.evBenchmarkR2')" sortable>
                              <template #body="{ data }">
                                <Tag
                                  :value="formatMetric(data.r2, 3)"
                                  :severity="r2Severity(data.r2)"
                                />
                              </template>
                            </Column>
                          </DataTable>
                        </div>
                      </details>
                    </div>

                    <div
                      v-if="
                        !variantBenchmarkRows.length &&
                        !variantMatrixRows.length &&
                        !evBaselineCards.length
                      "
                      class="card diagnostics-card"
                    >
                      <EmptyState icon="pi pi-chart-line" :message="t('common.noData')" />
                    </div>
                  </section>
                </TabPanel>

                <TabPanel value="drivers">
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
                  <div v-else class="card diagnostics-card">
                    <EmptyState icon="pi pi-sliders-h" :message="t('common.noData')" />
                  </div>
                </TabPanel>

                <TabPanel value="segments">
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

                    <DataTable
                      :value="segmentRows"
                      size="small"
                      striped-rows
                      table-style="min-width: 100%"
                    >
                      <Column field="segment" :header="t('diag.segment')" sortable>
                        <template #body="{ data }">
                          {{ formatSegmentLabel(selectedSegmentGroup, data.segment) }}
                        </template>
                      </Column>
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
                  <div v-else class="card diagnostics-card">
                    <EmptyState icon="pi pi-filter" :message="t('common.noData')" />
                  </div>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </TabPanel>

          <TabPanel value="quality">
            <div
              v-if="diagnosticsTrainingDatasetError && !preparationMetadata"
              class="card diagnostics-card state-card-stack diagnostics-quality-state"
              role="alert"
            >
              <EmptyState
                icon="pi pi-exclamation-triangle"
                :message="diagnosticsTrainingDatasetError"
              />
              <div class="state-card-actions">
                <Button
                  size="small"
                  severity="secondary"
                  outlined
                  icon="pi pi-refresh"
                  :label="t('common.retry')"
                  @click="() => void ensureDiagnosticsTrainingDatasetLoaded(true)"
                />
              </div>
            </div>

            <section class="card diagnostics-card diagnostics-section-intro">
              <div class="diagnostics-section-copy">
                <p class="diagnostics-section-eyebrow">{{ t('diag.filterSummary') }}</p>
                <h2>{{ t('diag.datasetEnrichment') }}</h2>
                <p>{{ t('diag.datasetEnrichmentDesc') }}</p>
              </div>

              <div class="context-chip-strip">
                <span
                  v-for="chip in diagnosticsQualityChips"
                  :key="`quality-${chip.label}-${chip.value}`"
                  class="context-chip"
                  :class="chip.tone ? `is-${chip.tone}` : ''"
                >
                  <span>{{ chip.label }}</span>
                  <strong>{{ chip.value }}</strong>
                </span>
              </div>
            </section>

            <Tabs v-model:value="diagnosticsQualityTab" class="diagnostics-subtabs">
              <TabList>
                <Tab value="filters">{{ t('diag.filterSummary') }}</Tab>
                <Tab value="enrichment">{{ t('diag.datasetEnrichment') }}</Tab>
              </TabList>
              <TabPanels>
                <TabPanel value="filters">
                  <div v-if="filterRows.length" class="card diagnostics-card">
                    <PageHeader
                      compact
                      :eyebrow="t('diag.filterSummary')"
                      :title="t('diag.filterSummary')"
                      :description="t('diag.filterSummaryDesc')"
                    />

                    <div v-if="filterOverviewCards.length" class="kpi-grid diagnostics-kpi-grid">
                      <MetricCard
                        v-for="item in filterOverviewCards"
                        :key="`${item.label}-${item.value}`"
                        :label="item.label"
                        :value="item.value"
                        :meta="item.meta"
                        :tone="item.tone"
                      />
                    </div>

                    <details class="diagnostics-fold">
                      <summary>
                        {{ t('diag.filterSummary') }} · {{ formatNumber(filterRows.length) }}
                      </summary>

                      <div class="diagnostics-fold-body">
                        <DataTable
                          :value="filterRows"
                          size="small"
                          striped-rows
                          table-style="min-width: 100%"
                        >
                          <Column field="groupLabel" :header="t('diag.flow')" sortable />
                          <Column field="stageLabel" :header="t('diag.stage')" sortable />
                          <Column field="rows" :header="t('diag.rowsKept')" sortable>
                            <template #body="{ data }">{{ formatNumber(data.rows) }}</template>
                          </Column>
                          <Column
                            field="dropped_since_previous"
                            :header="t('diag.rowsDropped')"
                            sortable
                          >
                            <template #body="{ data }">
                              {{ formatNumber(data.dropped_since_previous) }}
                            </template>
                          </Column>
                          <Column field="reports" :header="t('diag.yearsCovered')" sortable>
                            <template #body="{ data }">{{ formatNumber(data.reports) }}</template>
                          </Column>
                        </DataTable>
                      </div>
                    </details>
                  </div>
                  <div v-else class="card diagnostics-card">
                    <EmptyState icon="pi pi-list-check" :message="t('common.noData')" />
                  </div>
                </TabPanel>

                <TabPanel value="enrichment">
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

                    <div v-if="enrichmentSourceCards.length" class="kpi-grid diagnostics-kpi-grid">
                      <MetricCard
                        v-for="item in enrichmentSourceCards"
                        :key="`${item.label}-${item.value}`"
                        :label="item.label"
                        :value="item.value"
                        :meta="item.meta"
                        :tone="item.tone"
                      />
                    </div>

                    <details class="diagnostics-fold">
                      <summary>
                        {{ t('diag.yearsCovered') }} · {{ formatNumber(enrichmentRows.length) }}
                      </summary>

                      <div class="diagnostics-fold-body">
                        <DataTable
                          :value="enrichmentRows"
                          size="small"
                          striped-rows
                          table-style="min-width: 100%"
                        >
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
                                  :severity="
                                    enrichmentSeverity(
                                      row.evBuildingAvailable,
                                      row.evBuildingMatch > 0,
                                    )
                                  "
                                />
                                <Tag
                                  :value="t('diag.evParcels')"
                                  :severity="
                                    enrichmentSeverity(row.evParcelAvailable, row.evParcelMatch > 0)
                                  "
                                />
                                <Tag
                                  :value="t('diag.knPolygons')"
                                  :severity="
                                    enrichmentSeverity(row.knAvailable, row.knPolygonMatch > 0)
                                  "
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
                          <Column
                            field="rnExactAddress"
                            :header="t('diag.exactAddressMatches')"
                            sortable
                          >
                            <template #body="{ data: row }">
                              {{ formatNumber(row.rnExactAddress) }}
                            </template>
                          </Column>
                          <Column
                            field="rnRegionId"
                            :header="t('diag.regionIdsRecovered')"
                            sortable
                          >
                            <template #body="{ data: row }">
                              {{ formatNumber(row.rnRegionId) }}
                            </template>
                          </Column>
                          <Column
                            field="evBuildingMatch"
                            :header="t('diag.evBuildingMatches')"
                            sortable
                          >
                            <template #body="{ data: row }">
                              {{ formatNumber(row.evBuildingMatch) }}
                            </template>
                          </Column>
                          <Column
                            field="evParcelMatch"
                            :header="t('diag.evParcelMatches')"
                            sortable
                          >
                            <template #body="{ data: row }">
                              {{ formatNumber(row.evParcelMatch) }}
                            </template>
                          </Column>
                          <Column
                            field="knPolygonMatch"
                            :header="t('diag.knPolygonMatches')"
                            sortable
                          >
                            <template #body="{ data: row }">
                              {{ formatNumber(row.knPolygonMatch) }}
                            </template>
                          </Column>
                          <Column
                            field="gjiVodovodNearby"
                            :header="t('diag.gjiVodovodMatches')"
                            sortable
                          >
                            <template #body="{ data: row }">
                              {{ formatNumber(row.gjiVodovodNearby) }}
                            </template>
                          </Column>
                          <Column
                            field="gjiKanalizacijaNearby"
                            :header="t('diag.gjiKanalizacijaMatches')"
                            sortable
                          >
                            <template #body="{ data: row }">
                              {{ formatNumber(row.gjiKanalizacijaNearby) }}
                            </template>
                          </Column>
                          <Column field="emvZoneMatch" :header="t('diag.emvZoneMatches')" sortable>
                            <template #body="{ data: row }">
                              {{ formatNumber(row.emvZoneMatch) }}
                            </template>
                          </Column>
                          <Column :header="t('diag.enrichmentSources')">
                            <template #body="{ data: row }">
                              <span class="muted source-cell">{{
                                enrichmentSourcesLabel(row)
                              }}</span>
                            </template>
                          </Column>
                        </DataTable>
                      </div>
                    </details>
                  </div>
                  <div v-else class="card diagnostics-card">
                    <EmptyState icon="pi pi-database" :message="t('common.noData')" />
                  </div>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </TabPanel>

          <TabPanel value="insights">
            <section class="card diagnostics-card diagnostics-section-intro">
              <div class="diagnostics-section-copy">
                <p class="diagnostics-section-eyebrow">{{ t('diag.compareMetrics') }}</p>
                <h2>{{ t('diag.topFeatures') }}</h2>
                <p>{{ t('diag.topFeaturesDesc') }}</p>
              </div>

              <div class="context-chip-strip">
                <span
                  v-for="chip in diagnosticsInsightsChips"
                  :key="`insights-${chip.label}-${chip.value}`"
                  class="context-chip"
                  :class="chip.tone ? `is-${chip.tone}` : ''"
                >
                  <span>{{ chip.label }}</span>
                  <strong>{{ chip.value }}</strong>
                </span>
              </div>
            </section>

            <Tabs v-model:value="diagnosticsInsightsTab" class="diagnostics-subtabs">
              <TabList>
                <Tab value="compare">{{ t('diag.compareMetrics') }}</Tab>
                <Tab value="features">{{ t('diag.topFeatures') }}</Tab>
                <Tab value="types">{{ t('diag.perTypeTable') }}</Tab>
                <Tab value="regions">{{ t('diag.perRegionTable') }}</Tab>
              </TabList>
              <TabPanels>
                <TabPanel value="compare">
                  <div class="card diagnostics-card compare-card">
                    <div class="focus-head">
                      <div>
                        <h2 class="section-title">{{ t('diag.compareMetrics') }}</h2>
                        <p class="muted">
                          {{ t('diag.byPropertyType') }} / {{ t('diag.byRegion') }}
                        </p>
                      </div>
                      <Select
                        v-model="selectedMetric"
                        :options="metricOptions"
                        option-label="label"
                        option-value="value"
                      />
                    </div>

                    <div class="compare-chart-grid">
                      <div v-if="perTypeChart" class="chart-block">
                        <h3>{{ t('diag.byPropertyType') }}</h3>
                        <div class="chart-frame">
                          <Bar :data="perTypeChart" :options="chartOptions" />
                        </div>
                      </div>

                      <div v-if="perRegionChart" class="chart-block">
                        <h3>{{ t('diag.byRegion') }}</h3>
                        <div class="chart-frame">
                          <Bar :data="perRegionChart" :options="chartOptions" />
                        </div>
                      </div>
                    </div>
                  </div>
                </TabPanel>

                <TabPanel value="features">
                  <div
                    v-if="diagnosticsImportanceLoading"
                    class="card diagnostics-card"
                    aria-busy="true"
                  >
                    <Skeleton width="36%" height="1rem" />
                    <Skeleton width="68%" height="0.95rem" />
                    <Skeleton
                      v-for="idx in 6"
                      :key="`feature-skeleton-${idx}`"
                      width="100%"
                      height="2.5rem"
                      border-radius="var(--radius-sm)"
                    />
                  </div>
                  <div v-else-if="featureHighlights.length" class="card diagnostics-card">
                    <PageHeader
                      compact
                      :eyebrow="t('diag.topFeatures')"
                      :title="t('diag.topFeatures')"
                      :description="t('diag.topFeaturesDesc')"
                    />
                    <div class="feature-list">
                      <div
                        v-for="item in featureHighlights"
                        :key="item.feature"
                        class="feature-row"
                      >
                        <div class="feature-copy">
                          <strong>{{ item.label }}</strong>
                          <small>{{ item.feature }}</small>
                        </div>
                        <div class="feature-bar">
                          <span
                            :style="{
                              width: `${Math.max(10, Math.round(item.importance * 100))}%`,
                            }"
                          />
                        </div>
                        <strong>{{ formatMetric(item.importance) }}</strong>
                      </div>
                    </div>
                  </div>
                  <div v-else class="card diagnostics-card">
                    <EmptyState icon="pi pi-chart-bar" :message="t('common.noData')" />
                  </div>
                </TabPanel>

                <TabPanel value="types">
                  <div v-if="model.info.per_type_metrics" class="card diagnostics-card">
                    <PageHeader
                      compact
                      :eyebrow="t('diag.perTypeTable')"
                      :title="t('diag.perTypeTable')"
                    />
                    <EmptyState
                      v-if="!Object.keys(model.info.per_type_metrics).length"
                      icon="pi pi-chart-bar"
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
                  <div v-else class="card diagnostics-card">
                    <EmptyState icon="pi pi-chart-bar" :message="t('empty.noResults')" />
                  </div>
                </TabPanel>

                <TabPanel value="regions">
                  <div v-if="model.info.per_region_metrics" class="card diagnostics-card">
                    <PageHeader
                      compact
                      :eyebrow="t('diag.perRegionTable')"
                      :title="t('diag.perRegionTable')"
                    />
                    <EmptyState
                      v-if="!Object.keys(model.info.per_region_metrics).length"
                      icon="pi pi-map"
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
                  <div v-else class="card diagnostics-card">
                    <EmptyState icon="pi pi-map" :message="t('empty.noResults')" />
                  </div>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </TabPanel>

          <TabPanel value="history">
            <section class="diagnostics-history-grid">
              <AdminRunDetailPanel
                :eyebrow="t('nav.model')"
                :title="t('workbench.recentTrainingRuns')"
                :description="t('workbench.trainingRunDetailHint')"
                run-type="training"
                :runs="workbench.trainingRuns.slice(0, 8)"
                :selected-run-id="selectedTrainingRunId"
                :selected-run="selectedTrainingRun"
                :loading="workbench.trainingRunDetailLoading || diagnosticsTrainingRunsLoading"
                :error="workbench.trainingRunDetailError || diagnosticsTrainingRunsError"
                @select="loadTrainingRunDetail"
              />
            </section>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>
  </div>
</template>

<style scoped>
  .hero-link {
    text-decoration: none;
  }

  .diagnostics-page {
    display: grid;
    gap: var(--space-section);
    --page-accent: var(--primary);
    --page-accent-2: var(--accent);
  }

  .diagnostics-tabs {
    display: grid;
    gap: var(--space-section);
  }

  .diagnostics-tabs :deep(.p-tablist) {
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 62%, var(--page-accent) 38%);
    background: color-mix(in srgb, var(--surface-soft) 84%, var(--page-accent) 16%);
    padding: 0.35rem;
  }

  .diagnostics-tabs :deep(.p-tab) {
    border-radius: calc(var(--radius-sm) - 2px);
    min-height: 2.6rem;
    font-weight: 700;
  }

  .diagnostics-subtabs {
    display: grid;
    gap: 1rem;
  }

  .diagnostics-subtabs :deep(.p-tablist) {
    padding: 0.3rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--page-accent) 28%);
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--surface-soft) 90%, var(--page-accent) 10%);
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .diagnostics-subtabs :deep(.p-tab) {
    min-height: 2.4rem;
    border-radius: calc(var(--radius-sm) - 6px);
    font-weight: 700;
  }

  .diagnostics-subtabs :deep(.p-tabpanels) {
    padding-top: 0.1rem;
  }

  .diagnostics-fold {
    display: grid;
    gap: 0.65rem;
  }

  .diagnostics-fold-body {
    display: grid;
    gap: 0.9rem;
  }

  .diagnostics-fold > summary {
    list-style: none;
    cursor: pointer;
    user-select: none;
    padding: 0.8rem 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--page-accent) 40%);
    background:
      linear-gradient(
        130deg,
        color-mix(in srgb, var(--page-accent) 11%, transparent),
        transparent 52%
      ),
      var(--surface-subtle);
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-soft);
  }

  .diagnostics-fold > summary::-webkit-details-marker {
    display: none;
  }

  .diagnostics-fold[open] > summary {
    border-color: color-mix(in srgb, var(--border) 52%, var(--page-accent) 48%);
    color: var(--text);
  }

  .diagnostics-summary-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-section);
    align-items: start;
  }

  .diagnostics-report-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-section);
    align-items: start;
  }

  .diagnostics-report-grid--wide {
    grid-template-columns: 1fr;
  }

  .diagnostics-panel {
    display: grid;
    gap: 1rem;
  }

  .diagnostics-command-deck {
    gap: 1rem;
  }

  .diagnostics-focus-panel {
    min-width: 0;
  }

  .diagnostics-section-intro {
    grid-template-columns: minmax(0, 1.2fr) minmax(18rem, 0.95fr);
    align-items: start;
  }

  .diagnostics-section-copy {
    display: grid;
    gap: 0.45rem;
    min-width: 0;
  }

  .diagnostics-section-copy h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.4rem, 2vw, 1.95rem);
    line-height: 1.02;
    letter-spacing: -0.04em;
  }

  .diagnostics-section-copy p {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.55;
  }

  .diagnostics-section-eyebrow {
    display: inline-flex;
    width: fit-content;
    align-items: center;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--page-accent) 20%, var(--border) 80%);
    background: color-mix(in srgb, var(--surface-card-strong) 92%, var(--page-accent) 8%);
    color: color-mix(in srgb, var(--page-accent) 78%, var(--text) 22%);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .diagnostics-primary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: var(--space-section);
    align-items: start;
  }

  .diagnostics-primary-grid > .focus-card {
    order: -1;
  }

  .diagnostics-benchmark-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-section);
    align-items: start;
  }

  .diagnostics-history-grid {
    display: grid;
    gap: var(--space-section);
  }

  .benchmark-full {
    grid-column: 1 / -1;
  }

  .diagnostics-hero,
  .diagnostics-card {
    display: grid;
    gap: 0.9rem;
  }

  .diagnostics-loading,
  .diagnostics-loading-grid {
    display: grid;
    gap: 0.9rem;
  }

  .diagnostics-card {
    padding: clamp(1.05rem, 1.5vw, 1.45rem);
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--page-accent) 40%);
    background:
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--page-accent) 9%, transparent),
        transparent 48%
      ),
      var(--surface-panel);
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

  .focus-type-select {
    min-width: 14rem;
  }

  .diagnostics-deck-actions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
    gap: 0.8rem;
    align-items: end;
    width: min(100%, 52rem);
  }

  .diagnostics-deck-note {
    margin: 0;
    color: var(--text-soft);
    font-size: 0.9rem;
  }

  .diagnostics-deck-note--error {
    color: color-mix(in srgb, var(--danger) 72%, var(--text) 28%);
  }

  .diagnostics-quality-state {
    margin-bottom: 1rem;
  }

  .diagnostics-card :deep(.p-datatable-wrapper) {
    overflow-x: auto;
  }

  .diagnostics-benchmark-grid :deep(.p-datatable),
  .diagnostics-report-grid :deep(.p-datatable) {
    min-width: 100%;
  }

  .diagnostics-benchmark-grid :deep(.p-datatable-table) {
    min-width: 58rem;
  }

  .diagnostics-report-grid :deep(.p-datatable-table) {
    min-width: 36rem;
  }

  .diagnostics-card :deep(.p-datatable-table) {
    width: 100%;
  }

  .diagnostics-card :deep(.p-datatable-thead > tr > th) {
    white-space: nowrap;
  }

  .focus-head {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .focus-head > div {
    min-width: 0;
  }

  .focus-head :deep(.p-select) {
    max-width: 100%;
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
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--page-accent-2) 40%);
    border-radius: 999px;
    background: color-mix(in srgb, var(--surface-muted) 82%, var(--page-accent-2) 18%);
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

  .compare-chart-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
    gap: 1rem;
  }

  .chart-block {
    display: grid;
    gap: 0.8rem;
    padding-top: 0.75rem;
    border-top: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
  }

  .chart-block:first-child {
    padding-top: 0;
    border-top: 0;
  }

  .chart-frame {
    height: clamp(240px, 32vw, 320px);
  }

  .feature-list {
    display: grid;
    gap: 0.8rem;
  }

  .feature-row {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(120px, 1fr) auto;
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
      var(--page-accent),
      color-mix(in srgb, var(--page-accent-2) 58%, var(--surface-strong))
    );
  }

  .source-cell {
    display: inline-block;
    max-width: 28rem;
    white-space: normal;
    word-break: break-word;
  }

  .diagnostics-command-deck :deep(.page-header-actions) {
    justify-content: flex-start;
  }

  :deep(.active-focus-row) {
    background: color-mix(in srgb, var(--primary) 8%, transparent);
  }

  @media (max-width: 860px) {
    .diagnostics-summary-grid,
    .diagnostics-report-grid,
    .diagnostics-benchmark-grid,
    .diagnostics-section-intro,
    .compare-chart-grid,
    .feature-row {
      grid-template-columns: 1fr;
    }

    .focus-head {
      align-items: stretch;
    }

    .focus-head :deep(.p-select) {
      width: 100%;
    }

    .focus-type-select {
      min-width: 0;
      width: 100%;
    }

    .diagnostics-deck-actions {
      width: 100%;
      grid-template-columns: 1fr;
    }

    .diagnostics-tabs :deep(.p-tablist) {
      overflow-x: auto;
      overscroll-behavior-x: contain;
    }

    .diagnostics-tabs :deep(.p-tab) {
      flex: 0 0 auto;
      white-space: nowrap;
    }

    .chart-frame {
      height: 260px;
    }
  }
</style>
