<script setup lang="ts">
  import { Bar } from 'vue-chartjs'
  import {
    BarElement,
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    Tooltip,
  } from 'chart.js'
  import type { ChartData, ChartOptions } from 'chart.js'

  ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

  definePageMeta({ middleware: ['admin'] })

  const { t } = useI18n()
  const model = useModelStore()

  // ---------- state ----------
  const selectedMetric = ref<string>('r2')
  const selectedType = ref<string>('all')

  const metrics = ['mae', 'rmse', 'r2', 'mape', 'median_ae'] as const
  type MetricKey = (typeof metrics)[number]

  interface MetricOption {
    label: string
    value: string
  }

  interface MetricSet {
    mae?: number | null
    rmse?: number | null
    r2?: number | null
    mape?: number | null
    median_ae?: number | null
    n_train?: number | null
    n_test?: number | null
  }

  interface KpiItem {
    label: string
    value: string
    desc?: string
  }

  interface StoryCard {
    label: string
    value: string
    meta: string
  }

  interface FeatureItem {
    feature: string
    label: string
    importance: number
  }

  // ---------- metric selector items ----------
  const metricOptions = computed<MetricOption[]>(() =>
    metrics.map((m) => ({ label: m.toUpperCase(), value: m })),
  )

  // ---------- helpers ----------
  function formatType(value: string): string {
    return getPropertyTypeLabel(value, t)
  }

  function formatMetric(value: number | null | undefined, digits = 4): string {
    return formatNumber(value, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  }

  function formatDuration(value: number | null | undefined): string {
    if (value == null || Number.isNaN(Number(value))) return '\u2014'
    return `${formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`
  }

  function r2Color(r2: number | null | undefined): 'success' | 'warning' | 'error' {
    if (r2 == null) return 'error'
    if (r2 > 0.7) return 'success'
    if (r2 > 0.4) return 'warning'
    return 'error'
  }

  // ---------- derived data ----------
  const availableTypes = computed<string[]>(() =>
    Object.keys((model.info as any)?.per_type_metrics || {}),
  )

  const selectedTypeMetrics = computed<MetricSet | null>(() => {
    if (selectedType.value === 'all') return (model.info as any)?.global_metrics || null
    return (model.info as any)?.per_type_metrics?.[selectedType.value] || null
  })

  const modelStoryCards = computed<StoryCard[]>(() => {
    if (!model.info) return []
    return [
      {
        label: t('diag.version'),
        value: model.info.version || '\u2014',
        meta: t('diag.modelDetails'),
      },
      {
        label: t('diag.trainedAt'),
        value: formatDateTime(model.info.trained_at),
        meta: formatDuration(model.info.duration_sec),
      },
      {
        label: t('diag.rows'),
        value: formatNumber(model.info.rows),
        meta: t('diag.trainRows'),
      },
      {
        label: t('diag.focusType'),
        value: selectedType.value === 'all' ? t('diag.allTypes') : formatType(selectedType.value),
        meta: selectedMetric.value.toUpperCase(),
      },
    ]
  })

  const focusMetrics = computed<KpiItem[]>(() => {
    const m = selectedTypeMetrics.value
    if (!m) return []
    return [
      { label: 'MAE', value: formatCurrency(m.mae), desc: t('diag.maeDesc') },
      { label: 'RMSE', value: formatCurrency(m.rmse), desc: t('diag.rmseDesc') },
      { label: 'R\u00B2', value: formatMetric(m.r2), desc: t('diag.r2Desc') },
      {
        label: 'MAPE',
        value:
          m.mape == null
            ? '\u2014'
            : formatPercent(m.mape, { scale: 0.01, minimumFractionDigits: 1 }),
        desc: t('diag.mapeDesc'),
      },
      {
        label: t('diag.medianError'),
        value: formatCurrency(m.median_ae),
        desc: t('diag.medianDesc'),
      },
      {
        label: t('diag.trainSamples'),
        value: formatNumber(m.n_train),
        desc:
          selectedType.value === 'all'
            ? t('diag.focusAllDesc')
            : t('diag.focusTypeDesc', { type: formatType(selectedType.value) }),
      },
      {
        label: t('diag.testSamples'),
        value: formatNumber(m.n_test),
        desc: t('diag.testRows'),
      },
    ]
  })

  const combinedMetrics = computed<KpiItem[]>(() => {
    const m = (model.diagnostics as any)?.combined_metrics as MetricSet | undefined
    if (!m) return []
    return [
      { label: 'MAE', value: formatCurrency(m.mae) },
      { label: 'RMSE', value: formatCurrency(m.rmse) },
      { label: 'R\u00B2', value: formatMetric(m.r2) },
      {
        label: 'MAPE',
        value:
          m.mape == null
            ? '\u2014'
            : formatPercent(m.mape, { scale: 0.01, minimumFractionDigits: 1 }),
      },
      { label: t('diag.medianError'), value: formatCurrency(m.median_ae) },
    ]
  })

  const featureHighlights = computed<FeatureItem[]>(() =>
    (model.importance as FeatureItem[]).slice(0, 8),
  )

  // ---------- charts ----------
  const perTypeChart = computed<ChartData<'bar'> | null>(() => {
    const ptm = (model.info as any)?.per_type_metrics as Record<string, MetricSet> | undefined
    if (!ptm) return null
    const labels = Object.keys(ptm)
    const data = labels.map((k) => (ptm[k]?.[selectedMetric.value as MetricKey] as number) ?? 0)
    return {
      labels: labels.map((l) => formatType(l)),
      datasets: [
        {
          label: selectedMetric.value.toUpperCase(),
          data,
          backgroundColor: labels.map((l) =>
            selectedType.value === 'all' || selectedType.value === l ? '#2563eb' : '#bfdbfe',
          ),
          borderRadius: 4,
        },
      ],
    }
  })

  const perRegionChart = computed<ChartData<'bar'> | null>(() => {
    const prm = (model.info as any)?.per_region_metrics as Record<string, MetricSet> | undefined
    if (!prm) return null
    const labels = Object.keys(prm)
    const data = labels.map((k) => (prm[k]?.[selectedMetric.value as MetricKey] as number) ?? 0)
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

  const chartOptions: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { beginAtZero: true } },
  }

  // ---------- per-type metrics table ----------
  const perTypeRows = computed(() => {
    const ptm = (model.info as any)?.per_type_metrics as Record<string, MetricSet> | undefined
    if (!ptm) return []
    return Object.entries(ptm).map(([key, m]) => ({
      _key: key,
      type: formatType(key),
      mae: formatCurrency(m.mae),
      rmse: formatCurrency(m.rmse),
      r2_raw: m.r2 ?? null,
      r2: formatMetric(m.r2),
      mape:
        m.mape == null
          ? '\u2014'
          : formatPercent(m.mape, { scale: 0.01, minimumFractionDigits: 1 }),
      n_train: formatNumber(m.n_train),
      n_test: formatNumber(m.n_test),
    }))
  })

  const perTypeColumns = computed(() => [
    { accessorKey: 'type', header: t('diag.type'), enableSorting: false },
    { accessorKey: 'mae', header: 'MAE', enableSorting: false },
    { accessorKey: 'rmse', header: 'RMSE', enableSorting: false },
    { accessorKey: 'r2', header: 'R\u00B2', enableSorting: false },
    { accessorKey: 'mape', header: 'MAPE', enableSorting: false },
    { accessorKey: 'n_train', header: t('diag.trainSamples'), enableSorting: false },
    { accessorKey: 'n_test', header: t('diag.testSamples'), enableSorting: false },
  ])

  // ---------- per-region metrics table ----------
  const perRegionRows = computed(() => {
    const prm = (model.info as any)?.per_region_metrics as Record<string, MetricSet> | undefined
    if (!prm) return []
    return Object.entries(prm).map(([key, m]) => ({
      _key: key,
      region: key,
      mae: formatCurrency(m.mae),
      rmse: formatCurrency(m.rmse),
      r2: formatMetric(m.r2),
      mape:
        m.mape == null
          ? '\u2014'
          : formatPercent(m.mape, { scale: 0.01, minimumFractionDigits: 1 }),
    }))
  })

  const perRegionColumns = computed(() => [
    { accessorKey: 'region', header: t('diag.region'), enableSorting: false },
    { accessorKey: 'mae', header: 'MAE', enableSorting: false },
    { accessorKey: 'rmse', header: 'RMSE', enableSorting: false },
    { accessorKey: 'r2', header: 'R\u00B2', enableSorting: false },
    { accessorKey: 'mape', header: 'MAPE', enableSorting: false },
  ])

  // ---------- lifecycle ----------
  await useAsyncData('admin-diagnostics', () =>
    Promise.all([model.fetchInfo(), model.fetchDiagnostics(), model.fetchImportance()]),
  )
</script>

<template>
  <div class="diagnostics-page">
    <!-- ========== HERO ========== -->
    <section class="card diagnostics-hero">
      <div>
        <p class="eyebrow">{{ t('nav.diagnostics') }}</p>
        <h1>{{ t('nav.diagnostics') }}</h1>
        <p class="muted">{{ t('layout.page.diagnostics') }}</p>
      </div>

      <div v-if="model.info" class="diagnostics-story-grid">
        <article v-for="item in modelStoryCards" :key="item.label" class="diagnostics-story-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.meta }}</small>
        </article>
      </div>
    </section>

    <!-- ========== NO MODEL STATE ========== -->
    <div v-if="!model.info" class="card">
      <UAlert
        :description="t('diag.noModel')"
        color="warning"
        variant="soft"
        icon="i-lucide-alert-triangle"
      />
    </div>

    <template v-else>
      <!-- ========== FOCUS TYPE SECTION ========== -->
      <section class="card diagnostics-section">
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
          <div class="focus-chips">
            <button
              type="button"
              class="focus-chip"
              :class="{ active: selectedType === 'all' }"
              @click="selectedType = 'all'"
            >
              {{ t('diag.allTypes') }}
            </button>
            <button
              v-for="type in availableTypes"
              :key="type"
              type="button"
              class="focus-chip"
              :class="{ active: selectedType === type }"
              @click="selectedType = type"
            >
              {{ formatType(type) }}
            </button>
          </div>
        </div>

        <div class="kpi-grid" style="margin-top: 1rem">
          <div v-for="item in focusMetrics" :key="item.label" class="kpi-card">
            <span class="kpi-label">{{ item.label }}</span>
            <span class="kpi-value">{{ item.value }}</span>
            <span class="muted" style="font-size: 11px">{{ item.desc }}</span>
          </div>
        </div>
      </section>

      <!-- ========== COMBINED METRICS ========== -->
      <section v-if="combinedMetrics.length" class="card diagnostics-section">
        <h2>{{ t('diag.combinedMetrics') }}</h2>
        <p class="muted" style="margin-bottom: 0.75rem">{{ t('diag.combinedDesc') }}</p>
        <div class="kpi-grid">
          <div v-for="item in combinedMetrics" :key="item.label" class="kpi-card">
            <span class="kpi-label">{{ item.label }}</span>
            <span class="kpi-value">{{ item.value }}</span>
          </div>
        </div>
      </section>

      <!-- ========== MODEL DETAILS TABLE ========== -->
      <section class="card diagnostics-section">
        <h2>{{ t('diag.modelDetails') }}</h2>
        <div class="table-wrap">
          <table>
            <tbody>
              <tr>
                <td class="muted">{{ t('diag.version') }}</td>
                <td>{{ model.info.version }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.trainedAt') }}</td>
                <td>{{ formatDateTime(model.info.trained_at) }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.rows') }}</td>
                <td>{{ formatNumber(model.info.rows) }}</td>
              </tr>
              <tr v-if="(model.diagnostics as any)?.train_rows">
                <td class="muted">{{ t('diag.trainRows') }}</td>
                <td>{{ formatNumber((model.diagnostics as any).train_rows) }}</td>
              </tr>
              <tr v-if="(model.diagnostics as any)?.test_rows">
                <td class="muted">{{ t('diag.testRows') }}</td>
                <td>{{ formatNumber((model.diagnostics as any).test_rows) }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.duration') }}</td>
                <td>{{ formatDuration(model.info.duration_sec) }}</td>
              </tr>
              <tr>
                <td class="muted">{{ t('diag.perTypeModels') }}</td>
                <td>{{ formatNumber(model.info.per_type_count) }}</td>
              </tr>
              <tr v-if="(model.diagnostics as any)?.model_type">
                <td class="muted">{{ t('diag.modelType') }}</td>
                <td>{{ (model.diagnostics as any).model_type }}</td>
              </tr>
              <tr v-if="(model.diagnostics as any)?.type_models_trained?.length">
                <td class="muted">{{ t('diag.trainedTypes') }}</td>
                <td>
                  {{
                    (model.diagnostics as any).type_models_trained
                      .map((type: string) => formatType(type))
                      .join(', ')
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- ========== CHARTS: BY TYPE / BY REGION ========== -->
      <section class="card diagnostics-section">
        <div class="focus-head">
          <div>
            <h2 style="margin: 0">{{ t('diag.compareMetrics') }}</h2>
            <p class="muted">{{ t('diag.byPropertyType') }} / {{ t('diag.byRegion') }}</p>
          </div>
          <USelectMenu
            v-model="selectedMetric"
            :items="metricOptions"
            value-key="value"
            class="metric-select"
          />
        </div>

        <div v-if="perTypeChart" class="chart-panel chart-panel-spaced">
          <h3>{{ t('diag.byPropertyType') }}</h3>
          <div class="chart-frame">
            <ClientOnly>
              <Bar :data="perTypeChart" :options="chartOptions" />
            </ClientOnly>
          </div>
        </div>

        <div v-if="perRegionChart" class="chart-panel">
          <h3>{{ t('diag.byRegion') }}</h3>
          <div class="chart-frame">
            <ClientOnly>
              <Bar :data="perRegionChart" :options="chartOptions" />
            </ClientOnly>
          </div>
        </div>
      </section>

      <!-- ========== FEATURE IMPORTANCE ========== -->
      <section v-if="featureHighlights.length" class="card diagnostics-section">
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
      </section>

      <!-- ========== PER-TYPE METRICS TABLE ========== -->
      <section v-if="(model.info as any).per_type_metrics" class="card diagnostics-section">
        <h2>{{ t('diag.perTypeTable') }}</h2>

        <p v-if="!Object.keys((model.info as any).per_type_metrics).length" class="muted">
          {{ t('empty.noResults') }}
        </p>
        <div v-else class="table-wrap">
          <UTable :columns="perTypeColumns" :data="perTypeRows">
            <template #r2-cell="{ row }">
              <UBadge
                :label="row.original.r2"
                :color="r2Color(row.original.r2_raw)"
                variant="soft"
              />
            </template>
          </UTable>
        </div>
      </section>

      <!-- ========== PER-REGION METRICS TABLE ========== -->
      <section v-if="(model.info as any).per_region_metrics" class="card diagnostics-section">
        <h2>{{ t('diag.perRegionTable') }}</h2>

        <p v-if="!Object.keys((model.info as any).per_region_metrics).length" class="muted">
          {{ t('empty.noResults') }}
        </p>
        <div v-else class="table-wrap">
          <UTable :columns="perRegionColumns" :data="perRegionRows" />
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .diagnostics-page {
    display: grid;
    gap: 1rem;
  }

  .card {
    padding: 1.25rem;
    border-radius: 1.5rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
    display: grid;
    gap: 1rem;
  }

  .diagnostics-hero h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.5rem, 2vw, 2rem);
  }

  .diagnostics-section h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  /* ---------- story cards ---------- */
  .diagnostics-story-grid {
    display: grid;
    gap: 0.8rem;
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .diagnostics-story-card {
    display: grid;
    gap: 0.25rem;
    padding: 0.95rem 1rem;
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

  .diagnostics-story-card span {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .diagnostics-story-card strong {
    font-size: 1rem;
  }

  .diagnostics-story-card small {
    color: var(--text-muted);
  }

  /* ---------- focus type chips ---------- */
  .focus-head {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
  }

  .focus-chips {
    display: flex;
    gap: 0.55rem;
    flex-wrap: wrap;
  }

  .focus-chip {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--surface-muted) 82%, transparent)
    );
    color: var(--text);
    padding: 0.45rem 0.8rem;
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 10px 18px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease,
      box-shadow 160ms ease;
  }

  .focus-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 14px 24px rgb(15 23 42 / 10%);
  }

  .focus-chip.active {
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border));
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--primary) 14%, transparent),
      color-mix(in srgb, var(--secondary) 11%, transparent)
    );
    color: var(--primary-strong);
  }

  /* ---------- metric selector ---------- */
  .metric-select {
    min-width: 9rem;
  }

  /* ---------- chart panels ---------- */
  .chart-panel {
    display: grid;
    gap: 0.7rem;
    padding: 1rem;
    border-radius: 1.25rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--surface-muted) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 14px 24px rgb(15 23 42 / 6%);
  }

  .chart-panel-spaced {
    margin-bottom: 1rem;
  }

  .chart-frame {
    height: 300px;
  }

  /* ---------- feature importance ---------- */
  .feature-list {
    display: grid;
    gap: 0.8rem;
  }

  .feature-row {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(140px, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
    padding: 0.9rem 1rem;
    border-radius: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
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
    background: color-mix(in srgb, var(--ui-bg-muted) 90%, transparent);
  }

  .feature-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--primary) 86%, white 6%),
      color-mix(in srgb, var(--secondary) 20%, var(--primary) 80%)
    );
  }

  /* ---------- responsive ---------- */
  @media (max-width: 1100px) {
    .diagnostics-story-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .diagnostics-story-grid,
    .feature-row {
      grid-template-columns: 1fr;
    }
  }
</style>
