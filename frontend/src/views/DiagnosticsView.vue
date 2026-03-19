<script setup lang="ts">
  import { computed, onMounted, ref } from 'vue'
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
  import EmptyState from '../components/EmptyState.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import { useDataStore } from '../stores/data'
  import { useModelStore } from '../stores/model'
  import { formatCurrency, formatDateTime, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

  const { t } = useI18n()
  const model = useModelStore()
  const dataStore = useDataStore()

  const selectedMetric = ref('r2')
  const selectedType = ref('all')
  const selectedSegmentGroup = ref('property_type')
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

  const metricOptions = computed(() =>
    metrics.map((m) => ({ label: m.toUpperCase(), value: m })),
  )

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

  const perTypeChart = computed(() => {
    const ptm = model.info?.per_type_metrics
    if (!ptm) return null
    const labels = Object.keys(ptm)
    const data = labels.map((k) => ptm[k]?.[selectedMetric.value] ?? 0)
    return {
      labels: labels.map((label) => formatType(label)),
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: labels.map((label) =>
            selectedType.value === 'all' || selectedType.value === label ? '#2563eb' : '#bfdbfe',
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
    return {
      labels,
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: '#22c55e',
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
    () => model.diagnostics?.data_preparation || dataStore.trainingDataset?.preparation_metadata || null,
  )

  const filterRows = computed(() => {
    const summary = preparationMetadata.value?.filter_summary
    if (!summary) return []
    return Object.entries(summary).flatMap(([group, stages]) =>
      (stages || []).map((stage) => ({
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

  onMounted(async () => {
    await Promise.all([
      model.fetchInfo(),
      model.fetchDiagnostics(),
      model.fetchImportance(),
      dataStore.fetchTrainingDataset(),
    ])
    if (segmentGroupOptions.value.length && !segmentGroupOptions.value.some((item) => item.value === selectedSegmentGroup.value)) {
      selectedSegmentGroup.value = segmentGroupOptions.value[0].value
    }
  })
</script>

<template>
  <div>
    <PageHeader :title="t('nav.diagnostics')" />

    <div v-if="!model.info" class="card">
      <p class="muted">{{ t('diag.noModel') }}</p>
    </div>

    <template v-else>
      <!-- Focus type selector + KPI cards -->
      <div class="card" style="margin-bottom: 1.5rem">
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
            optionLabel="label"
            optionValue="value"
          />
        </div>

        <div class="kpi-grid" style="margin-top: 1rem">
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
      <div v-if="combinedMetrics.length" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.combinedMetrics') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.combinedDesc') }}</p>
        <div class="kpi-grid">
          <MetricCard
            v-for="item in combinedMetrics"
            :key="item.label"
            :label="item.label"
            :value="item.value"
          />
        </div>
      </div>

      <!-- Model details table -->
      <div class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.modelDetails') }}</h2>
        <DataTable :value="modelDetailsRows" size="small" table-style="min-width: 100%">
          <Column field="key" :header="t('diag.property')" />
          <Column field="val" :header="t('diag.value')" />
        </DataTable>
      </div>

      <div v-if="scoreDriverCards.length" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.scoreDrivers') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.scoreDriversDesc') }}</p>
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

      <div v-if="segmentGroupOptions.length" class="card" style="margin-bottom: 1.5rem">
        <div class="focus-head">
          <div>
            <h2 style="margin: 0">{{ t('diag.worstSegments') }}</h2>
            <p class="muted">{{ t('diag.worstSegmentsDesc') }}</p>
          </div>
          <Select
            v-model="selectedSegmentGroup"
            :options="segmentGroupOptions"
            optionLabel="label"
            optionValue="value"
          />
        </div>

        <DataTable
          :value="segmentRows"
          size="small"
          striped-rows
          table-style="min-width: 100%"
        >
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

      <div v-if="filterRows.length" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.filterSummary') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.filterSummaryDesc') }}</p>
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

      <!-- Compare metrics charts -->
      <div class="card" style="margin-bottom: 1.5rem">
        <div class="focus-head">
          <div>
            <h2 style="margin: 0">{{ t('diag.compareMetrics') }}</h2>
            <p class="muted">{{ t('diag.byPropertyType') }} / {{ t('diag.byRegion') }}</p>
          </div>
          <Select
            v-model="selectedMetric"
            :options="metricOptions"
            optionLabel="label"
            optionValue="value"
          />
        </div>

        <div v-if="perTypeChart" style="margin-bottom: 2rem">
          <h3>{{ t('diag.byPropertyType') }}</h3>
          <div style="height: 300px">
            <Bar :data="perTypeChart" :options="chartOptions" />
          </div>
        </div>

        <div v-if="perRegionChart">
          <h3>{{ t('diag.byRegion') }}</h3>
          <div style="height: 300px">
            <Bar :data="perRegionChart" :options="chartOptions" />
          </div>
        </div>
      </div>

      <!-- Feature importance -->
      <div v-if="featureHighlights.length" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.topFeatures') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.topFeaturesDesc') }}</p>
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
      <div v-if="model.info.per_type_metrics" class="card" style="margin-bottom: 1.5rem">
        <h2>{{ t('diag.perTypeTable') }}</h2>
        <EmptyState
          v-if="!Object.keys(model.info.per_type_metrics).length"
          icon="📊"
          :message="t('empty.noResults')"
        />
        <DataTable
          v-else
          :value="perTypeRows"
          :rowClass="perTypeRowClass"
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
      <div v-if="model.info.per_region_metrics" class="card">
        <h2>{{ t('diag.perRegionTable') }}</h2>
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
  .focus-head {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
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
    background: linear-gradient(90deg, var(--primary), #7dd3fc);
  }

  :deep(.active-focus-row) {
    background: color-mix(in srgb, var(--primary) 8%, transparent);
  }
</style>
