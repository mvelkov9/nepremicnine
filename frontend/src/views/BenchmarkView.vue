<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useDebounceFn } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import type { DataTableSortEvent } from 'primevue/datatable'
  import IconField from 'primevue/iconfield'
  import InputIcon from 'primevue/inputicon'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tag from 'primevue/tag'
  import Tabs from 'primevue/tabs'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import BenchmarkSegmentSection from '../components/benchmark/BenchmarkSegmentSection.vue'
  import { useExport } from '../composables/useExport'
  import { useFilterOptions } from '../composables/useFilterOptions'
  import { useFormat } from '../composables/useFormat'
  import { useServerTableState } from '../composables/useServerTableState'
  import api from '../composables/useApi'
  import { useAuthStore } from '../stores/auth'
  import { useReferenceDataStore } from '../stores/referenceData'
  import type { BenchmarkProofRow, BenchmarkSummaryResponse, ServerTableResult } from '../types/api'
  import { getApiErrorMessage } from '../utils/apiError'
  import { readQueryTab } from '../utils/routeQuery'
  import { formatCurrency, formatNumber, formatPercent } from '../utils/format'

  const benchmarkTabs = ['snapshot', 'methodology', 'proof'] as const

  const { t } = useI18n()
  const { formatType } = useFormat()
  const route = useRoute()
  const router = useRouter()
  const auth = useAuthStore()
  const referenceData = useReferenceDataStore()
  const { exportToCSV } = useExport()
  const { propertyTypeOptions } = useFilterOptions()

  const summary = ref<BenchmarkSummaryResponse | null>(null)
  const summaryLoading = ref(true)
  const summaryError = ref('')
  const proofRows = ref<ServerTableResult<BenchmarkProofRow>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 25,
    pages: 0,
    filters: {},
    sort: 'improvement_eur',
    order: 'desc',
  })
  const proofLoading = ref(false)
  const proofError = ref('')
  const searchInput = ref('')
  const proofRequestId = ref(0)
  const benchmarkTab = ref<'snapshot' | 'methodology' | 'proof'>(
    readQueryTab(route.query.tab, benchmarkTabs, 'snapshot'),
  )

  function syncBenchmarkTabFromRoute(query = route.query) {
    const allowedTabs = auth.isAdmin
      ? benchmarkTabs
      : benchmarkTabs.filter((tab) => tab !== 'proof')
    const nextTab = readQueryTab(query.tab, allowedTabs, 'snapshot')
    if (benchmarkTab.value !== nextTab) {
      benchmarkTab.value = nextTab
    }
  }

  function syncBenchmarkTabToRoute(tab: string) {
    const allowedTabs = auth.isAdmin
      ? benchmarkTabs
      : benchmarkTabs.filter((value) => value !== 'proof')
    const nextTab = readQueryTab(tab, allowedTabs, 'snapshot')
    const currentTab = readQueryTab(route.query.tab, allowedTabs, 'snapshot')
    if (currentTab === nextTab) return
    void router.replace({ query: { ...route.query, tab: nextTab } })
  }

  const table = useServerTableState(
    {
      page: '1',
      page_size: '25',
      sort: 'improvement_eur',
      order: 'desc',
      search: '',
      property_type: '',
      winner: '',
    },
    { filterKeys: ['property_type', 'winner'] },
  )

  const isUnavailable = computed(
    () => summary.value?.status === 'unavailable' || summary.value?.status === 'error',
  )

  const winTotal = computed(() => {
    const w = summary.value?.winners
    if (!w) return 0
    return w.model + w.gurs + w.tie
  })

  const winRate = computed(() => {
    if (!winTotal.value || !summary.value?.winners) return null
    return summary.value.winners.model / winTotal.value
  })

  const methodologyLabel = computed(() => {
    if (!summary.value?.methodology) return ''
    if (summary.value.methodology === 'shared_gurs_coverage_holdout') {
      return t('benchmark.sharedCoverageTitle')
    }
    return summary.value.methodology
  })

  const summaryCards = computed(() => {
    if (!summary.value) return []
    const s = summary.value
    const imp = s.improvement_vs_gurs
    return [
      {
        label: t('benchmark.coverageTitle'),
        value: formatNumber(s.coverage_rows),
        meta: t('benchmark.coverageMeta'),
      },
      {
        label: t('benchmark.avgGainTitle'),
        value: formatCurrency(imp?.avg_gain_eur),
        meta: t('benchmark.avgGainMeta'),
        tone: (imp?.avg_gain_eur ?? 0) > 0 ? ('success' as const) : undefined,
      },
      {
        label: t('benchmark.winRateTitle'),
        value:
          winRate.value != null ? formatPercent(winRate.value, { minimumFractionDigits: 1 }) : '-',
        meta: t('benchmark.winRateMeta'),
        tone: (winRate.value ?? 0) > 0.5 ? ('success' as const) : undefined,
      },
      {
        label: t('benchmark.maeLeadTitle'),
        value: formatCurrency(imp?.mae),
        meta: t('benchmark.maeLeadMeta'),
        tone: (imp?.mae ?? 0) > 0 ? ('success' as const) : undefined,
      },
    ]
  })

  const heroStory = computed(() => {
    if (!summary.value) return ''

    const pieces: string[] = []
    const imp = summary.value.improvement_vs_gurs

    if (winRate.value != null) {
      pieces.push(
        `${t('benchmark.winRateTitle')}: ${formatPercent(winRate.value, { minimumFractionDigits: 1 })}`,
      )
    }

    if (imp?.avg_gain_eur != null) {
      pieces.push(`${t('benchmark.avgGainTitle')}: ${formatCurrency(imp.avg_gain_eur)}`)
    }

    if (imp?.mae != null) {
      pieces.push(`${t('benchmark.maeLeadTitle')}: ${formatCurrency(imp.mae)}`)
    }

    return pieces.join(' · ')
  })

  const comparisonCards = computed(() => {
    if (!summary.value) return []

    const s = summary.value
    const m = s.model_metrics
    const g = s.gurs_metrics

    return [
      {
        title: t('benchmark.ourModel'),
        badge: methodologyLabel.value || t('benchmark.sharedCoverageTitle'),
        severity: 'success' as const,
        metrics: [
          { label: 'MAE', value: formatCurrency(m?.mae) },
          { label: 'RMSE', value: formatCurrency(m?.rmse) },
          { label: 'Median AE', value: formatCurrency(m?.median_ae) },
          {
            label: 'MAPE',
            value:
              m?.mape != null
                ? formatPercent(m.mape, { scale: 0.01, minimumFractionDigits: 1 })
                : '-',
          },
          {
            label: 'R²',
            value:
              m?.r2 != null
                ? formatNumber(m.r2, { minimumFractionDigits: 4, maximumFractionDigits: 4 })
                : '-',
          },
        ],
      },
      {
        title: t('benchmark.gursBaseline'),
        badge: t('benchmark.methodologyTitle'),
        severity: 'danger' as const,
        metrics: [
          { label: 'MAE', value: formatCurrency(g?.mae) },
          { label: 'RMSE', value: formatCurrency(g?.rmse) },
          { label: 'Median AE', value: formatCurrency(g?.median_ae) },
          {
            label: 'MAPE',
            value:
              g?.mape != null
                ? formatPercent(g.mape, { scale: 0.01, minimumFractionDigits: 1 })
                : '-',
          },
          {
            label: 'R²',
            value:
              g?.r2 != null
                ? formatNumber(g.r2, { minimumFractionDigits: 4, maximumFractionDigits: 4 })
                : '-',
          },
        ],
      },
    ]
  })

  const heroFacts = computed(() => {
    if (!summary.value) return []

    return [
      {
        label: t('benchmark.coverageTitle'),
        value: formatNumber(summary.value.coverage_rows),
      },
      {
        label: t('benchmark.winRateTitle'),
        value:
          winRate.value != null ? formatPercent(winRate.value, { minimumFractionDigits: 1 }) : '-',
      },
      {
        label: t('benchmark.avgGainTitle'),
        value: formatCurrency(summary.value.improvement_vs_gurs?.avg_gain_eur),
      },
    ]
  })

  const winnerOptions = computed(() => [
    { label: t('benchmark.allWinners'), value: '' },
    { label: t('benchmark.winner.model'), value: 'model' },
    { label: t('benchmark.winner.gurs'), value: 'gurs' },
    { label: t('benchmark.winner.tie'), value: 'tie' },
  ])

  function winnerSeverity(winner: string) {
    if (winner === 'model') return 'success'
    if (winner === 'gurs') return 'danger'
    return 'info'
  }

  function winnerLabel(winner: string) {
    if (winner === 'model') return t('benchmark.winner.model')
    if (winner === 'gurs') return t('benchmark.winner.gurs')
    return t('benchmark.winner.tie')
  }

  function saleTypeLabel(value: string | number | null | undefined) {
    const normalized = String(value ?? '').trim()
    if (normalized === '1') return t('benchmark.saleTypeOpenMarket')
    if (normalized === '2') return t('benchmark.saleTypeAuction')
    return normalized || '-'
  }

  const debouncedSearchSync = useDebounceFn((value: string) => {
    applySearch(value)
  }, 260)

  const selectedPropertyType = computed({
    get: () => table.state.property_type || '',
    set: (value: string) => onPropertyTypeChange(value),
  })

  const selectedWinner = computed({
    get: () => table.state.winner || '',
    set: (value: string) => onWinnerChange(value),
  })

  const selectedPageSize = computed({
    get: () => String(table.pageSize.value),
    set: (value: number | string) => onPageSizeChange(value),
  })

  const proofSummary = computed(() => {
    const total = proofRows.value.total || proofRows.value.items.length
    const start = total ? (table.page.value - 1) * table.pageSize.value + 1 : 0
    const end = total ? start + proofRows.value.items.length - 1 : 0
    return {
      total,
      start,
      end,
      page: table.page.value,
      pageSize: table.pageSize.value,
    }
  })

  function emptyProofRows(): ServerTableResult<BenchmarkProofRow> {
    return {
      items: [],
      total: 0,
      page: table.page.value,
      page_size: table.pageSize.value,
      pages: 0,
      filters: {},
      sort: table.sort.value,
      order: table.order.value,
    }
  }

  watch(
    () => table.search.value,
    (value) => {
      if (value !== searchInput.value) searchInput.value = value
    },
    { immediate: true },
  )

  watch(searchInput, (value) => {
    debouncedSearchSync(value)
  })

  watch(
    () => route.query.tab,
    () => {
      syncBenchmarkTabFromRoute(route.query)
    },
  )

  watch(benchmarkTab, (tab) => {
    syncBenchmarkTabToRoute(tab)
  })

  watch(
    () => [
      table.state.page,
      table.state.page_size,
      table.state.sort,
      table.state.order,
      table.state.search,
      table.state.property_type,
      table.state.winner,
    ],
    () => {
      if (auth.isAdmin) void fetchProofRows()
    },
  )

  function onPage(event: { page: number; rows: number }) {
    if (event.rows !== table.pageSize.value) {
      onPageSizeChange(event.rows)
      return
    }
    table.page.value = event.page + 1
    table.pageSize.value = event.rows
  }

  function onSort(event: DataTableSortEvent) {
    if (event.sortField) {
      table.sort.value = String(event.sortField)
      table.order.value = event.sortOrder === 1 ? 'asc' : 'desc'
    }
  }

  function applySearch(value: string) {
    table.patchState({ search: value, page: '1' })
  }

  function onPropertyTypeChange(value: string) {
    table.patchState({ property_type: value, page: '1' })
  }

  function onWinnerChange(value: string) {
    table.patchState({ winner: value, page: '1' })
  }

  function onPageSizeChange(value: number | string) {
    const next = Math.max(Number.parseInt(String(value), 10) || 25, 1)
    table.patchState({ page_size: String(next), page: '1' })
  }

  async function fetchSummary() {
    summaryLoading.value = true
    summaryError.value = ''
    try {
      const { data } = await api.get<BenchmarkSummaryResponse>('/api/model/benchmark/gurs-summary')
      summary.value = data
    } catch (err) {
      summaryError.value = getApiErrorMessage(err, t)
    } finally {
      summaryLoading.value = false
    }
  }

  async function fetchProofRows() {
    const requestId = ++proofRequestId.value
    proofLoading.value = true
    proofError.value = ''
    try {
      const { data } = await api.get<ServerTableResult<BenchmarkProofRow>>(
        '/api/model/benchmark/gurs-transactions',
        { params: table.toParams() },
      )
      if (requestId !== proofRequestId.value) return
      proofRows.value = data
    } catch (err) {
      if (requestId !== proofRequestId.value) return
      proofRows.value = emptyProofRows()
      proofError.value = getApiErrorMessage(err, t)
    } finally {
      if (requestId !== proofRequestId.value) return
      proofLoading.value = false
    }
  }

  function exportProof() {
    exportToCSV(
      proofRows.value.items as unknown as Record<string, unknown>[],
      `benchmark-proof-page-${proofSummary.value.page}`,
    )
  }

  onMounted(async () => {
    syncBenchmarkTabFromRoute(route.query)
    try {
      await referenceData.ensureLoaded()
    } catch {
      // Keep benchmark rendering even if shared reference data refresh fails.
    }
    await fetchSummary()
    if (auth.isAdmin) await fetchProofRows()
  })
</script>

<template>
  <div class="benchmark-page">
    <PageHeader
      :eyebrow="t('benchmark.kicker')"
      :title="t('benchmark.title')"
      :description="t('benchmark.body')"
    />

    <LoadingSpinner v-if="summaryLoading" :label="t('common.loading')" />

    <template v-else-if="summaryError">
      <div class="state-card state-card-stack" role="alert">
        <EmptyState icon="pi pi-exclamation-triangle" :message="summaryError" />
        <div class="state-card-actions">
          <Button
            icon="pi pi-refresh"
            severity="secondary"
            outlined
            :label="t('common.retry')"
            @click="fetchSummary"
          />
        </div>
      </div>
    </template>

    <template v-else-if="isUnavailable">
      <EmptyState
        icon="pi pi-info-circle"
        :message="summary?.detail || t('benchmark.unavailableBody')"
      />
      <div v-if="auth.isAdmin" class="benchmark-actions">
        <Button
          :as="RouterLink"
          to="/admin/diagnostics"
          :label="t('benchmark.openDiagnostics')"
          icon="pi pi-chart-bar"
        />
        <Button
          :as="RouterLink"
          to="/admin/model"
          :label="t('benchmark.openModelWorkbench')"
          icon="pi pi-cog"
          severity="secondary"
          outlined
        />
      </div>
    </template>

    <template v-else-if="summary && !summary.coverage_rows">
      <EmptyState icon="pi pi-inbox" :message="summary.detail || t('benchmark.emptyBody')" />
    </template>

    <template v-else-if="summary">
      <section class="hero-shell benchmark-hero" aria-label="benchmark summary">
        <div class="benchmark-hero-grid">
          <div class="benchmark-hero-copy">
            <div class="benchmark-hero-tags">
              <Tag
                :value="methodologyLabel || t('benchmark.sharedCoverageTitle')"
                severity="info"
              />
              <Tag
                :value="`${formatNumber(summary.coverage_rows)} ${t('map.transactions').toLowerCase()}`"
                severity="success"
              />
            </div>

            <div class="benchmark-hero-story">
              <p class="benchmark-hero-kicker">
                {{ methodologyLabel || t('benchmark.sharedCoverageTitle') }}
              </p>
              <p class="benchmark-hero-note">
                {{ heroStory || summary.detail || t('benchmark.sharedCoverageBody') }}
              </p>
            </div>

            <dl class="benchmark-hero-facts">
              <div v-for="fact in heroFacts" :key="fact.label">
                <dt>{{ fact.label }}</dt>
                <dd>{{ fact.value }}</dd>
              </div>
            </dl>
          </div>

          <div class="benchmark-hero-summary">
            <MetricCard
              v-for="card in summaryCards"
              :key="card.label"
              :label="card.label"
              :value="card.value"
              :meta="card.meta"
              :tone="card.tone || 'default'"
            />
          </div>
        </div>
      </section>

      <Tabs v-model:value="benchmarkTab" class="benchmark-tabs">
        <TabList>
          <Tab value="snapshot">{{ t('common.overview') }}</Tab>
          <Tab value="methodology">{{ t('benchmark.methodologyTitle') }}</Tab>
          <Tab v-if="auth.isAdmin" value="proof">{{ t('benchmark.adminTitle') }}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel value="snapshot">
            <div class="benchmark-sections">
              <SectionPanel
                class="benchmark-section benchmark-section-wide"
                :eyebrow="t('benchmark.modelHeadline')"
                :title="t('benchmark.errorCardsTitle')"
              >
                <p class="benchmark-section-intro muted">
                  {{ heroStory || summary.detail || t('benchmark.sharedCoverageBody') }}
                </p>

                <div class="benchmark-comparison-grid">
                  <article
                    v-for="card in comparisonCards"
                    :key="card.title"
                    class="benchmark-comparison-card"
                    :class="`tone-${card.severity}`"
                  >
                    <div class="benchmark-comparison-head">
                      <p class="eyebrow subtle">{{ card.badge }}</p>
                      <Tag :value="card.title" :severity="card.severity" />
                    </div>

                    <dl class="benchmark-comparison-metrics">
                      <div v-for="metric in card.metrics" :key="metric.label">
                        <dt>{{ metric.label }}</dt>
                        <dd>{{ metric.value }}</dd>
                      </div>
                    </dl>
                  </article>
                </div>
              </SectionPanel>

              <SectionPanel
                v-if="summary.winners"
                class="benchmark-section"
                :eyebrow="t('benchmark.modelHeadline')"
                :title="t('benchmark.winnerBreakdownTitle')"
              >
                <div class="benchmark-winner-grid">
                  <article class="benchmark-winner-summary">
                    <p class="eyebrow subtle">{{ t('benchmark.modelHeadline') }}</p>
                    <strong>{{
                      winRate != null ? formatPercent(winRate, { minimumFractionDigits: 1 }) : '-'
                    }}</strong>
                    <span>{{ t('benchmark.modelWins') }}</span>
                    <small>{{
                      heroStory || summary.detail || t('benchmark.sharedCoverageBody')
                    }}</small>
                  </article>

                  <div class="winner-grid">
                    <div class="winner-card winner-model">
                      <strong>{{ formatNumber(summary.winners.model) }}</strong>
                      <span>{{ t('benchmark.modelWins') }}</span>
                      <small v-if="winTotal">{{
                        formatPercent(summary.winners.model / winTotal, {
                          minimumFractionDigits: 1,
                        })
                      }}</small>
                    </div>
                    <div class="winner-card winner-gurs">
                      <strong>{{ formatNumber(summary.winners.gurs) }}</strong>
                      <span>{{ t('benchmark.gursWins') }}</span>
                      <small v-if="winTotal">{{
                        formatPercent(summary.winners.gurs / winTotal, { minimumFractionDigits: 1 })
                      }}</small>
                    </div>
                    <div v-if="summary.winners.tie > 0" class="winner-card winner-tie">
                      <strong>{{ formatNumber(summary.winners.tie) }}</strong>
                      <span>{{ t('benchmark.ties') }}</span>
                      <small v-if="winTotal">{{
                        formatPercent(summary.winners.tie / winTotal, { minimumFractionDigits: 1 })
                      }}</small>
                    </div>
                  </div>
                </div>
              </SectionPanel>

              <div class="segment-panels">
                <BenchmarkSegmentSection
                  v-if="summary.top_regions?.length"
                  :eyebrow="t('benchmark.segmentRegions')"
                  :title="t('benchmark.bestRegionsTitle')"
                  kind="region"
                  :items="summary.top_regions"
                />

                <BenchmarkSegmentSection
                  v-if="summary.top_property_types?.length"
                  :eyebrow="t('benchmark.segmentTypes')"
                  :title="t('benchmark.bestTypesTitle')"
                  kind="type"
                  :items="summary.top_property_types"
                />

                <BenchmarkSegmentSection
                  v-if="summary.top_years?.length"
                  :eyebrow="t('benchmark.segmentYears')"
                  :title="t('benchmark.bestYearsTitle')"
                  kind="year"
                  :items="summary.top_years"
                />
              </div>
            </div>
          </TabPanel>

          <TabPanel value="methodology">
            <div class="benchmark-sections">
              <SectionPanel
                class="benchmark-section benchmark-methodology"
                :eyebrow="t('benchmark.methodologyTitle')"
                :title="t('benchmark.sharedCoverageTitle')"
              >
                <div class="benchmark-methodology-grid">
                  <article class="benchmark-methodology-story">
                    <p class="muted">{{ t('benchmark.sharedCoverageBody') }}</p>
                  </article>
                  <article class="benchmark-methodology-aside">
                    <span>{{ t('benchmark.methodologySharedCoverage') }}</span>
                    <strong>{{ methodologyLabel || t('benchmark.sharedCoverageTitle') }}</strong>
                    <small>{{ summary.detail || t('benchmark.sharedCoverageBody') }}</small>
                  </article>
                </div>
              </SectionPanel>
            </div>
          </TabPanel>

          <TabPanel v-if="auth.isAdmin" value="proof">
            <div class="benchmark-sections">
              <SectionPanel
                class="benchmark-section benchmark-proof"
                :eyebrow="t('benchmark.adminKicker')"
                :title="t('benchmark.adminTitle')"
              >
                <template #actions>
                  <Button
                    icon="pi pi-download"
                    :label="t('benchmark.exportCurrentPage')"
                    severity="secondary"
                    outlined
                    size="small"
                    :disabled="!proofRows.items.length"
                    @click="exportProof"
                  />
                </template>

                <div class="benchmark-proof-meta">
                  <p class="muted proof-summary">
                    {{
                      proofSummary.total
                        ? `${formatNumber(proofSummary.start)}-${formatNumber(proofSummary.end)} / ${formatNumber(proofSummary.total)} ${t('map.transactions').toLowerCase()}`
                        : t('benchmark.emptyBody')
                    }}
                  </p>
                  <p class="benchmark-proof-note muted">
                    {{ t('benchmark.sharedCoverageBody') }}
                  </p>
                </div>

                <div class="benchmark-proof-toolbar">
                  <IconField class="search-field">
                    <InputIcon class="pi pi-search" />
                    <InputText
                      v-model="searchInput"
                      :placeholder="t('benchmark.searchPlaceholder')"
                    />
                  </IconField>

                  <Select
                    :model-value="selectedPropertyType"
                    @update:model-value="onPropertyTypeChange"
                    :options="propertyTypeOptions"
                    option-label="label"
                    option-value="value"
                    class="toolbar-select"
                  />

                  <Select
                    :model-value="selectedWinner"
                    @update:model-value="onWinnerChange"
                    :options="winnerOptions"
                    option-label="label"
                    option-value="value"
                    class="toolbar-select"
                  />

                  <Select
                    :model-value="selectedPageSize"
                    @update:model-value="onPageSizeChange"
                    :options="['10', '25', '50', '100']"
                    class="toolbar-select rows-select"
                  />
                </div>

                <div v-if="proofError" class="state-card state-card-stack" role="alert">
                  <EmptyState icon="pi pi-exclamation-triangle" :message="proofError" />
                  <div class="state-card-actions">
                    <Button
                      icon="pi pi-refresh"
                      severity="secondary"
                      outlined
                      :label="t('common.retry')"
                      :disabled="proofLoading"
                      @click="fetchProofRows"
                    />
                  </div>
                </div>
                <div v-else class="proof-table-shell">
                  <DataTable
                    :value="proofRows.items"
                    :loading="proofLoading"
                    lazy
                    paginator
                    striped-rows
                    responsive-layout="scroll"
                    row-hover
                    :rows="table.pageSize.value"
                    :first="(table.page.value - 1) * table.pageSize.value"
                    :total-records="proofRows.total"
                    :sort-field="table.sort.value"
                    :sort-order="table.order.value === 'asc' ? 1 : -1"
                    @page="onPage"
                    @sort="onSort"
                  >
                    <template #empty>
                      <EmptyState icon="pi pi-inbox" :message="t('benchmark.emptyBody')" />
                    </template>

                    <Column field="municipality" :header="t('map.municipality')" sortable />
                    <Column field="region" :header="t('map.region')" sortable />

                    <Column field="property_type" :header="t('predict.propertyType')" sortable>
                      <template #body="{ data }">{{ formatType(data.property_type) }}</template>
                    </Column>

                    <Column field="transaction_year" :header="t('map.year')" sortable />

                    <Column field="vrsta_kupoprodajnega_posla" :header="t('benchmark.saleType')">
                      <template #body="{ data }">
                        {{ saleTypeLabel(data.vrsta_kupoprodajnega_posla) }}
                      </template>
                    </Column>

                    <Column field="price_eur" :header="t('benchmark.actualPrice')" sortable>
                      <template #body="{ data }">{{ formatCurrency(data.price_eur) }}</template>
                    </Column>

                    <Column field="model_price_eur" :header="t('benchmark.modelPrice')" sortable>
                      <template #body="{ data }">
                        {{ formatCurrency(data.model_price_eur) }}
                      </template>
                    </Column>

                    <Column field="gurs_price_eur" :header="t('benchmark.gursPrice')" sortable>
                      <template #body="{ data }">
                        {{ formatCurrency(data.gurs_price_eur) }}
                      </template>
                    </Column>

                    <Column field="model_abs_error" :header="t('benchmark.modelError')" sortable>
                      <template #body="{ data }">
                        {{ formatCurrency(data.model_abs_error) }}
                      </template>
                    </Column>

                    <Column field="gurs_abs_error" :header="t('benchmark.gursError')" sortable>
                      <template #body="{ data }">
                        {{ formatCurrency(data.gurs_abs_error) }}
                      </template>
                    </Column>

                    <Column field="improvement_eur" :header="t('benchmark.improvement')" sortable>
                      <template #body="{ data }">
                        <span
                          :class="{
                            'text-success': data.improvement_eur > 0,
                            'text-danger': data.improvement_eur < 0,
                          }"
                        >
                          {{ data.improvement_eur > 0 ? '+' : ''
                          }}{{ formatCurrency(data.improvement_eur) }}
                        </span>
                      </template>
                    </Column>

                    <Column field="winner" :header="t('benchmark.winnerColumn')" sortable>
                      <template #body="{ data }">
                        <Tag
                          :value="winnerLabel(data.winner)"
                          :severity="winnerSeverity(data.winner)"
                        />
                      </template>
                    </Column>
                  </DataTable>
                </div>
              </SectionPanel>
            </div>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>
  </div>
</template>

<style scoped>
  .benchmark-page {
    display: grid;
    gap: var(--space-section);
    --page-accent: var(--primary);
    --page-accent-2: var(--accent);
  }

  .benchmark-hero {
    display: grid;
    gap: 1rem;
    padding: 1.15rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 56%, var(--page-accent) 44%);
    background:
      radial-gradient(
        circle at 10% -20%,
        color-mix(in srgb, var(--page-accent) 17%, transparent),
        transparent 46%
      ),
      radial-gradient(
        circle at 92% -34%,
        color-mix(in srgb, var(--page-accent-2) 14%, transparent),
        transparent 50%
      ),
      var(--surface-hero);
    box-shadow: var(--hero-shadow);
  }

  .benchmark-hero-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.15rem;
    align-items: start;
  }

  .benchmark-hero-copy {
    display: grid;
    gap: 1rem;
    min-width: 0;
  }

  .benchmark-hero-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
  }

  .benchmark-hero-story {
    display: grid;
    gap: 0.5rem;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background:
      linear-gradient(
        140deg,
        color-mix(in srgb, var(--page-accent-2) 12%, transparent),
        transparent 48%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 130%
      ),
      var(--surface-panel-muted);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .benchmark-hero-kicker {
    margin: 0;
    color: color-mix(in srgb, var(--primary) 72%, var(--text) 28%);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .benchmark-hero-note {
    margin: 0;
    max-width: 68ch;
    color: var(--text-muted);
    line-height: 1.62;
  }

  .benchmark-hero-facts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.75rem;
    margin: 0;
  }

  .benchmark-hero-facts div {
    display: grid;
    gap: 0.25rem;
    padding: 0.8rem 0.85rem;
    border-radius: calc(var(--radius-sm) - 2px);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background: var(--surface-subtle);
  }

  .benchmark-hero-facts dt {
    color: var(--text-soft);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .benchmark-hero-facts dd {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .benchmark-hero-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    gap: var(--space-grid, 1rem);
    align-content: start;
  }

  .benchmark-sections {
    display: grid;
    gap: var(--space-section);
  }

  .benchmark-tabs {
    display: grid;
    gap: var(--space-section);
  }

  .benchmark-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--page-accent) 40%);
    background:
      linear-gradient(
        130deg,
        color-mix(in srgb, var(--page-accent-2) 12%, transparent),
        transparent 55%
      ),
      var(--surface-subtle);
  }

  .benchmark-tabs :deep(.p-tab) {
    min-height: 2.6rem;
    border-radius: calc(var(--radius-sm) - 2px);
    font-weight: 700;
  }

  .benchmark-section {
    display: grid;
    gap: 0.9rem;
  }

  .benchmark-section-wide {
    max-width: none;
  }

  .benchmark-section-intro {
    margin: 0;
    max-width: 72ch;
  }

  .benchmark-comparison-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
    gap: var(--space-grid, 1rem);
  }

  .benchmark-comparison-card {
    display: grid;
    gap: 0.85rem;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background:
      linear-gradient(
        140deg,
        color-mix(in srgb, var(--page-accent) 10%, transparent),
        transparent 52%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 130%
      ),
      var(--surface-panel-muted);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .benchmark-comparison-card.tone-success {
    border-color: color-mix(in srgb, var(--success) 28%, var(--border) 72%);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--success) 10%, transparent), transparent 32%),
      var(--surface-panel-muted);
  }

  .benchmark-comparison-card.tone-danger {
    border-color: color-mix(in srgb, var(--danger) 28%, var(--border) 72%);
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--danger) 10%, transparent), transparent 32%),
      var(--surface-panel-muted);
  }

  .benchmark-comparison-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .benchmark-comparison-head .eyebrow {
    margin: 0;
  }

  .benchmark-comparison-metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(8.2rem, 1fr));
    gap: 0.7rem;
    margin: 0;
  }

  .benchmark-comparison-metrics div {
    display: grid;
    gap: 0.2rem;
    padding: 0.75rem 0.8rem;
    border-radius: calc(var(--radius-sm) - 2px);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--content-border-strong) 24%);
    background: var(--surface-subtle);
  }

  .benchmark-comparison-metrics dt {
    color: var(--text-soft);
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .benchmark-comparison-metrics dd {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .benchmark-winner-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
    align-items: stretch;
  }

  .benchmark-winner-summary {
    display: grid;
    align-content: start;
    gap: 0.45rem;
    padding: 1.1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--page-accent) 16%, transparent),
        transparent 30%
      ),
      radial-gradient(
        circle at bottom left,
        color-mix(in srgb, var(--page-accent-2) 12%, transparent),
        transparent 28%
      ),
      var(--surface-panel-muted);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .benchmark-winner-summary strong {
    font-family: var(--font-display);
    font-size: clamp(2rem, 4vw, 2.8rem);
    line-height: 0.94;
    letter-spacing: -0.06em;
  }

  .benchmark-winner-summary span {
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--text-soft);
  }

  .benchmark-winner-summary small {
    color: var(--text-muted);
    line-height: 1.5;
  }

  .winner-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: var(--space-grid, 1rem);
  }

  .benchmark-methodology-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
    align-items: stretch;
  }

  .benchmark-methodology-story {
    display: grid;
    align-content: start;
    gap: 0.4rem;
  }

  .benchmark-methodology-aside {
    display: grid;
    gap: 0.35rem;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--primary) 22%);
    background: var(--surface-subtle);
    box-shadow: var(--shadow-sm);
  }

  .benchmark-methodology-aside span {
    color: var(--text-soft);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .benchmark-methodology-aside strong {
    font-size: 1rem;
    letter-spacing: -0.02em;
  }

  .benchmark-methodology-aside small {
    color: var(--text-muted);
    line-height: 1.5;
  }

  .benchmark-proof-meta {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.75rem;
    align-items: start;
    margin-bottom: 0.2rem;
  }

  .proof-summary {
    margin: 0;
    max-width: 60ch;
  }

  .benchmark-proof-note {
    margin: 0;
    justify-self: end;
    max-width: 34ch;
    text-align: right;
  }

  .benchmark-proof-toolbar {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) repeat(3, minmax(10rem, 1fr));
    gap: 0.75rem;
    align-items: stretch;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background:
      linear-gradient(
        120deg,
        color-mix(in srgb, var(--page-accent-2) 10%, transparent),
        transparent 52%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 130%
      ),
      var(--surface-panel-muted);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .benchmark-proof-toolbar :deep(.p-iconfield) {
    width: 100%;
    min-width: 0;
  }

  .search-field,
  .toolbar-select,
  .rows-select {
    width: 100%;
    min-width: 0;
  }

  .benchmark-proof-toolbar .toolbar-select {
    flex: 1 1 10rem;
  }

  .proof-table-shell {
    overflow-x: auto;
    border-radius: var(--radius-md);
  }

  .proof-table-shell :deep(.p-datatable) {
    min-width: 70rem;
  }

  .proof-table-shell :deep(.p-datatable .p-datatable-thead > tr > th) {
    background: var(--surface-subtle);
    color: var(--text);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .proof-table-shell :deep(.p-datatable .p-datatable-tbody > tr > td) {
    border-color: color-mix(in srgb, var(--border) 84%, var(--content-border-strong) 16%);
  }

  .winner-card {
    display: grid;
    gap: 0.25rem;
    justify-items: center;
    padding: var(--space-panel-sm, 1rem);
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background:
      linear-gradient(
        140deg,
        color-mix(in srgb, var(--page-accent) 8%, transparent),
        transparent 55%
      ),
      var(--surface-subtle);
    box-shadow: var(--shadow-sm);
    text-align: center;
  }

  .winner-card strong {
    font-size: clamp(1.4rem, 3vw, 1.8rem);
  }

  .winner-card small {
    color: var(--text-muted);
  }

  .winner-model {
    border-color: color-mix(in srgb, var(--success) 28%, var(--border) 72%);
    background: color-mix(in srgb, var(--surface-subtle) 88%, var(--success) 12%);
  }

  .winner-gurs {
    border-color: color-mix(in srgb, var(--danger) 28%, var(--border) 72%);
    background: color-mix(in srgb, var(--surface-subtle) 88%, var(--danger) 12%);
  }

  .segment-panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: var(--space-grid, 1rem);
    align-items: start;
  }

  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }

  .state-card-actions {
    display: flex;
    justify-content: flex-start;
  }

  .benchmark-actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .benchmark-actions a {
    text-decoration: none;
  }

  .text-success {
    color: var(--success);
  }

  .text-danger {
    color: var(--danger);
  }

  @media (max-width: 1100px) {
    .benchmark-hero-facts {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .benchmark-proof-toolbar {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .benchmark-proof-toolbar :deep(.p-iconfield) {
      grid-column: 1 / -1;
    }
  }

  @media (max-width: 768px) {
    .benchmark-tabs :deep(.p-tablist) {
      overflow-x: auto;
      overscroll-behavior-x: contain;
    }

    .benchmark-tabs :deep(.p-tab) {
      flex: 0 0 auto;
      white-space: nowrap;
    }

    .benchmark-hero-summary,
    .benchmark-hero-facts,
    .segment-panels,
    .winner-grid,
    .benchmark-proof-toolbar {
      grid-template-columns: 1fr;
    }

    .benchmark-proof-meta {
      grid-template-columns: 1fr;
    }

    .benchmark-proof-note {
      justify-self: start;
      text-align: left;
    }

    .benchmark-hero-tags {
      gap: 0.45rem;
    }

    .benchmark-comparison-metrics {
      grid-template-columns: 1fr;
    }
  }
</style>
