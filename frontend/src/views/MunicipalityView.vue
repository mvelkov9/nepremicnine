<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tabs from 'primevue/tabs'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import FilterBar from '../components/FilterBar.vue'
  import FilterField from '../components/FilterField.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import PageHeader from '../components/PageHeader.vue'
  import PropertyTypePieChart from '../components/charts/PropertyTypePieChart.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import type { ExplorerResponse, TransactionRecord } from '../types/api'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber, formatPercent } from '../utils/format'
  import { useFormat } from '../composables/useFormat'
  import MunicipalityHeroPanel from '../features/municipality/MunicipalityHeroPanel.vue'

  interface MunicipalityOverview {
    earliest_year?: number | string | null
    latest_year?: number | string | null
    count?: number | null
    median_price?: number | null
    avg_area?: number | null
    median_price_per_m2?: number | null
  }

  interface MunicipalityMarketPosition {
    region_rank_by_price_per_m2?: number | null
    region_rank_by_activity?: number | null
  }

  interface MunicipalityTrendPoint {
    year: number | string
    count?: number | null
    median_price?: number | null
    median_price_per_m2?: number | null
  }

  interface MunicipalityMixPoint {
    property_type: string
    count: number
    share: number
  }

  interface MunicipalityRelatedItem {
    slug: string
    municipality: string
    region?: string | null
    count?: number | null
    median_price_per_m2?: number | null
  }

  interface MunicipalityDetail {
    municipality: string
    slug?: string
    region?: string | null
    overview?: MunicipalityOverview | null
    market_position?: MunicipalityMarketPosition | null
    year_trend?: MunicipalityTrendPoint[]
    property_type_mix?: MunicipalityMixPoint[]
    related_municipalities?: MunicipalityRelatedItem[]
  }

  interface TransactionsPageEvent {
    page: number
    rows: number
  }

  function emptyTransactions(): ExplorerResponse<TransactionRecord> {
    return {
      items: [],
      total: 0,
      page: 1,
      page_size: 12,
      pages: 0,
      filters: {},
      sort: 'recent',
      order: 'desc',
    }
  }

  const { t } = useI18n()
  const { formatType } = useFormat()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()
  const workbench = useWorkbenchStore()
  const viewerQuery = useViewerQueryState({
    tab: 'overview',
    property_type: '',
    year: '',
    search: '',
  })

  const loading = ref(false)
  const error = ref('')
  const transactionsError = ref('')
  const transactions = ref<ExplorerResponse<TransactionRecord>>(emptyTransactions())
  let municipalityLoadToken = 0
  let transactionsLoadToken = 0

  const detail = computed<MunicipalityDetail | null>(
    () => stats.municipalityDetail as MunicipalityDetail | null,
  )

  const pageTitle = computed(() => detail.value?.municipality || t('municipality.pageTitle'))
  const pageDescription = computed(() =>
    detail.value?.region
      ? t('municipality.heroBody', { region: detail.value.region })
      : t('municipality.pageDescription'),
  )

  const activeTab = computed({
    get: () =>
      ['overview', 'transactions', 'type_mix', 'benchmarks'].includes(viewerQuery.state.tab)
        ? viewerQuery.state.tab
        : 'overview',
    set: (tab: string) => viewerQuery.patchState({ tab: tab || 'overview' }),
  })

  const coverageWindow = computed(() => {
    const from = detail.value?.overview?.earliest_year
    const to = detail.value?.overview?.latest_year
    if (!from && !to) return '-'
    if (from && to) return t('municipality.coverageWindow', { from, to })
    return String(from || to)
  })

  const regionRank = computed(
    () => detail.value?.market_position?.region_rank_by_price_per_m2 ?? '-',
  )

  const selectedFilterCount = computed(
    () =>
      [viewerQuery.state.property_type, viewerQuery.state.year, viewerQuery.state.search].filter(
        Boolean,
      ).length,
  )

  const selectedFilterTag = computed(() =>
    selectedFilterCount.value > 0
      ? t('dashboard.activeFilterCount', { count: selectedFilterCount.value })
      : t('dashboard.noActiveFilters'),
  )

  const propertyTypeOptions = computed(() => [
    { label: t('market.allPropertyTypes'), value: '' },
    ...((detail.value?.property_type_mix || []) as MunicipalityMixPoint[]).map((item) => ({
      label: formatType(item.property_type),
      value: item.property_type,
    })),
  ])

  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: '' },
    ...((detail.value?.year_trend || []) as MunicipalityTrendPoint[]).map((item) => ({
      label: String(item.year),
      value: String(item.year),
    })),
  ])

  const heroMetrics = computed(() => [
    {
      label: t('dashboard.transactions'),
      value: formatNumber(detail.value?.overview?.count),
      meta: coverageWindow.value,
      tone: 'default' as const,
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(detail.value?.overview?.median_price),
      meta: `${formatNumber(detail.value?.overview?.avg_area, { maximumFractionDigits: 1 })} m²`,
      tone: 'warm' as const,
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(detail.value?.overview?.median_price_per_m2),
      meta: detail.value?.region || '-',
      tone: 'success' as const,
    },
  ])

  const yearTrendRows = computed(() =>
    (detail.value?.year_trend || []).map((item) => ({
      year: item.year,
      count: item.count,
      median_price: item.median_price,
      median_price_per_m2: item.median_price_per_m2,
    })),
  )
  const transactionState = computed<ExplorerResponse<TransactionRecord>>(
    () => transactions.value || emptyTransactions(),
  )
  const transactionRows = computed(() => transactionState.value.items || [])

  function shareStyle(share: number | null | undefined) {
    return { width: `${Math.max(10, Math.round((share || 0) * 100))}%` }
  }

  async function loadTransactions(
    municipalityRequestToken = municipalityLoadToken,
    transactionRequestToken = ++transactionsLoadToken,
  ) {
    transactionsError.value = ''
    try {
      const data = await stats.fetchMunicipalityTransactions(String(route.params.slug), {
        property_type: viewerQuery.state.property_type || undefined,
        year: viewerQuery.state.year || undefined,
        search: viewerQuery.state.search || undefined,
        page: transactionState.value.page,
        page_size: transactionState.value.page_size,
        sort: 'recent',
        order: 'desc',
      })
      if (
        municipalityRequestToken !== municipalityLoadToken ||
        transactionRequestToken !== transactionsLoadToken
      ) {
        return
      }
      transactions.value = data || emptyTransactions()
    } catch (err) {
      if (
        municipalityRequestToken !== municipalityLoadToken ||
        transactionRequestToken !== transactionsLoadToken
      ) {
        return
      }
      transactions.value = emptyTransactions()
      transactionsError.value = getApiErrorMessage(err, t)
    }
  }

  async function loadMunicipality() {
    const requestToken = ++municipalityLoadToken
    const transactionRequestToken = ++transactionsLoadToken
    loading.value = true
    error.value = ''
    try {
      await Promise.all([
        stats.fetchMunicipalityDetail(String(route.params.slug)),
        loadTransactions(requestToken, transactionRequestToken),
      ])
    } catch (err) {
      if (requestToken !== municipalityLoadToken) return
      stats.resetMunicipalityDetail()
      transactions.value = emptyTransactions()
      transactionsError.value = ''
      error.value = getApiErrorMessage(err, t)
    } finally {
      if (requestToken === municipalityLoadToken) {
        loading.value = false
      }
    }
  }

  function openPrediction(transaction: TransactionRecord | null = null) {
    router.push({
      name: 'prediction',
      query: {
        municipality: detail.value?.municipality || '',
        property_type: transaction?.property_type || 'stanovanje',
        size_m2: transaction?.size_m2 ?? detail.value?.overview?.avg_area ?? '',
        year_built: transaction?.year_built || '',
        price_eur: transaction?.price_eur || '',
      },
    })
  }

  function openMap() {
    router.push({
      name: 'map',
      query: {
        municipality: detail.value?.municipality || '',
        region: detail.value?.region || '',
        property_type: viewerQuery.state.property_type || '',
        year: viewerQuery.state.year || '',
      },
    })
  }

  function openTransactionsExplorer() {
    router.push({
      path: '/trg',
      query: {
        tab: 'transactions',
        municipality: detail.value?.municipality || '',
        property_type: viewerQuery.state.property_type || undefined,
        year: viewerQuery.state.year || undefined,
        search: viewerQuery.state.search || undefined,
      },
    })
  }

  function onTransactionsPage(event: TransactionsPageEvent) {
    transactions.value.page = event.page + 1
    transactions.value.page_size = event.rows
    void loadTransactions()
  }

  async function addMunicipalityToWatchlist() {
    if (!detail.value?.slug) return
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: detail.value.slug,
      display_label: detail.value.municipality,
      metadata: { link: `/obcine/${detail.value.slug}`, region: detail.value.region },
    })
  }

  function addMunicipalityToCompare() {
    if (!detail.value?.slug) return
    workbench.addCompareItem({
      id: `municipality:${detail.value.slug}`,
      entity_type: 'municipality',
      label: detail.value.municipality,
      slug: detail.value.slug,
      region: detail.value.region,
      metadata: { source: 'municipality-detail' },
    })
    workbench.rememberMunicipality({
      id: `municipality:${detail.value.slug}`,
      entity_type: 'municipality',
      label: detail.value.municipality,
      slug: detail.value.slug,
      region: detail.value.region,
    })
  }

  watch(
    () => route.params.slug,
    () => {
      transactions.value.page = 1
      void loadMunicipality()
    },
    { immediate: true },
  )

  watch(
    () => [viewerQuery.state.property_type, viewerQuery.state.year, viewerQuery.state.search],
    () => {
      transactions.value.page = 1
      void loadTransactions()
    },
  )
</script>

<template>
  <div class="municipality-page">
    <div v-if="loading" class="state-frame" aria-busy="true">
      <LoadingSpinner :label="t('common.loading')" />
    </div>

    <div v-else-if="error" class="state-frame state-frame-stack" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
      <div class="state-frame-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="loadMunicipality"
        />
      </div>
    </div>

    <template v-else-if="detail">
      <PageHeader
        :eyebrow="t('municipality.pageEyebrow')"
        :title="pageTitle"
        :description="pageDescription"
      >
        <template #actions>
          <SavedWorkspaceMenu
            page="municipality"
            :state="{
              page: 'municipality',
              filters: {
                slug: detail.slug,
                property_type: viewerQuery.state.property_type || undefined,
                year: viewerQuery.state.year || undefined,
                search: viewerQuery.state.search || undefined,
              },
              tab: viewerQuery.state.tab,
            }"
          />
          <Button
            icon="pi pi-calculator"
            :label="t('municipality.openPrediction')"
            @click="openPrediction()"
          />
          <Button
            icon="pi pi-map"
            severity="secondary"
            outlined
            :label="t('municipality.openMap')"
            @click="openMap"
          />
          <Button
            icon="pi pi-bookmark"
            severity="secondary"
            text
            :label="t('workbench.watch')"
            @click="addMunicipalityToWatchlist"
          />
          <Button
            icon="pi pi-plus-circle"
            severity="secondary"
            text
            :label="t('workbench.compare')"
            @click="addMunicipalityToCompare"
          />
        </template>
      </PageHeader>

      <MunicipalityHeroPanel
        :municipality="detail.municipality"
        :region="detail.region || '-'"
        :coverage-window="coverageWindow"
        :region-rank="regionRank"
        :rank-label="t('municipality.regionStanding')"
        :headline="t('municipality.regionComparison')"
        :summary="t('municipality.heroBody', { region: detail.region || '-' })"
        :featured-label="t('dashboard.pricePerM2')"
        :featured-value="formatCurrency(detail.overview?.median_price_per_m2)"
        :featured-meta="
          t('municipality.activityRankLabel', {
            count: detail.market_position?.region_rank_by_activity ?? '-',
          })
        "
        :hero-metrics="heroMetrics"
      />

      <SectionPanel :eyebrow="t('common.explore')" :title="t('dashboard.activeFilters')" compact>
        <template #actions>
          <Tag
            :severity="selectedFilterCount > 0 ? 'contrast' : 'secondary'"
            :value="selectedFilterTag"
          />
        </template>

        <FilterBar :columns="3">
          <FilterField :label="t('market.selectPropertyType')">
            <Select
              v-model="viewerQuery.state.property_type"
              :options="propertyTypeOptions"
              option-label="label"
              option-value="value"
            />
          </FilterField>
          <FilterField :label="t('map.year')">
            <Select
              v-model="viewerQuery.state.year"
              :options="yearOptions"
              option-label="label"
              option-value="value"
            />
          </FilterField>
          <FilterField :label="t('common.search')">
            <InputText v-model="viewerQuery.state.search" :placeholder="t('common.search')" />
          </FilterField>
        </FilterBar>
      </SectionPanel>

      <SectionPanel
        :eyebrow="t('common.explore')"
        :title="t('municipality.latestTransactions')"
        compact
      >
        <template #actions>
          <div class="explore-actions">
            <Button
              icon="pi pi-table"
              severity="secondary"
              outlined
              :label="t('market.tabTransactions')"
              @click="openTransactionsExplorer"
            />
            <Button
              icon="pi pi-chart-line"
              severity="secondary"
              outlined
              :label="t('municipality.openPrediction')"
              @click="openPrediction()"
            />
          </div>
        </template>
        <p class="section-note">
          {{ t('municipality.heroBody', { region: detail.region || '-' }) }}
        </p>
      </SectionPanel>

      <Tabs v-model:value="activeTab" class="municipality-tabs">
        <TabList>
          <Tab value="overview">{{ t('common.overview') }}</Tab>
          <Tab value="transactions">{{ t('market.tabTransactions') }}</Tab>
          <Tab value="type_mix">{{ t('municipality.propertyMix') }}</Tab>
          <Tab value="benchmarks">{{ t('common.compare') }}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel value="overview">
            <section class="tab-grid">
              <SectionPanel
                :eyebrow="t('municipality.trendChart')"
                :title="t('municipality.yearTrend')"
                compact
              >
                <TrendLineChart
                  v-if="yearTrendRows.length"
                  :data="yearTrendRows"
                  metric="median_price"
                />
                <EmptyState v-else :message="t('common.noData')" />
              </SectionPanel>

              <SectionPanel
                :eyebrow="t('municipality.relatedMarkets')"
                :title="t('municipality.nearbyBenchmarks')"
                compact
              >
                <div v-if="detail.related_municipalities?.length" class="related-list">
                  <RouterLink
                    v-for="item in detail.related_municipalities"
                    :key="item.slug"
                    :to="`/obcine/${item.slug}`"
                    class="related-card"
                  >
                    <div class="related-copy">
                      <strong>{{ item.municipality }}</strong>
                      <small>{{ item.region || '-' }}</small>
                    </div>
                    <Tag
                      severity="success"
                      :value="`${formatCurrency(item.median_price_per_m2)}/m²`"
                    />
                  </RouterLink>
                </div>
                <EmptyState v-else :message="t('common.noData')" />
              </SectionPanel>
            </section>
          </TabPanel>

          <TabPanel value="transactions">
            <SectionPanel
              :eyebrow="t('municipality.recentTransactions')"
              :title="t('municipality.latestTransactions')"
              compact
            >
              <EmptyState
                v-if="transactionsError && !transactionRows.length"
                icon="pi pi-exclamation-triangle"
                :message="transactionsError"
              />
              <DataTable
                v-else-if="transactionRows.length"
                :value="transactionRows"
                lazy
                paginator
                :rows="transactionState.page_size"
                :first="(transactionState.page - 1) * transactionState.page_size"
                :total-records="transactionState.total"
                size="small"
                striped-rows
                responsive-layout="scroll"
                table-style="min-width: 100%"
                @page="onTransactionsPage"
              >
                <Column field="property_type" :header="t('predict.propertyType')">
                  <template #body="{ data }">
                    {{ formatType(data.property_type) }}
                  </template>
                </Column>
                <Column field="size_m2" :header="t('predict.size')">
                  <template #body="{ data }">
                    {{ formatNumber(data.size_m2, { maximumFractionDigits: 1 }) }} m²
                  </template>
                </Column>
                <Column field="price_eur" :header="t('dashboard.medianPrice')">
                  <template #body="{ data }">{{ formatCurrency(data.price_eur) }}</template>
                </Column>
                <Column field="price_per_m2" :header="t('dashboard.pricePerM2')">
                  <template #body="{ data }">{{ formatCurrency(data.price_per_m2) }}</template>
                </Column>
                <Column field="year" :header="t('map.year')">
                  <template #body="{ data }">{{ data.year || '-' }}</template>
                </Column>
                <Column :header="t('common.actions')">
                  <template #body="{ data }">
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-calculator"
                      :label="t('municipality.useForPrediction')"
                      @click="openPrediction(data)"
                    />
                  </template>
                </Column>
              </DataTable>
              <EmptyState v-else :message="t('common.noData')" />
            </SectionPanel>
          </TabPanel>

          <TabPanel value="type_mix">
            <section class="tab-grid">
              <SectionPanel
                :eyebrow="t('municipality.propertyChart')"
                :title="t('municipality.propertyMix')"
                compact
              >
                <PropertyTypePieChart
                  v-if="detail.property_type_mix?.length"
                  :items="detail.property_type_mix"
                />
                <EmptyState v-else :message="t('common.noData')" />
              </SectionPanel>

              <SectionPanel
                :eyebrow="t('municipality.regionComparison')"
                :title="t('municipality.regionComparison')"
                compact
              >
                <div v-if="detail.property_type_mix?.length" class="mix-list">
                  <div
                    v-for="item in detail.property_type_mix"
                    :key="item.property_type"
                    class="mix-row"
                  >
                    <div class="mix-copy">
                      <strong>{{ formatType(item.property_type) }}</strong>
                      <small>{{ formatPercent(item.share) }}</small>
                    </div>
                    <div class="mix-bar"><span :style="shareStyle(item.share)"></span></div>
                  </div>
                </div>
                <EmptyState v-else :message="t('common.noData')" />
              </SectionPanel>
            </section>
          </TabPanel>

          <TabPanel value="benchmarks">
            <section class="tab-grid">
              <SectionPanel
                :eyebrow="t('municipality.regionComparison')"
                :title="t('municipality.nearbyBenchmarks')"
                compact
              >
                <div class="benchmark-grid">
                  <article class="benchmark-card">
                    <span>{{ t('municipality.regionStanding') }}</span>
                    <strong
                      >#{{ detail.market_position?.region_rank_by_price_per_m2 ?? '-' }}</strong
                    >
                    <small>{{ detail.region || '-' }}</small>
                  </article>
                  <article class="benchmark-card">
                    <span>{{ t('regions.mostActive') }}</span>
                    <strong>#{{ detail.market_position?.region_rank_by_activity ?? '-' }}</strong>
                    <small>{{ t('dashboard.transactions') }}</small>
                  </article>
                </div>
              </SectionPanel>

              <SectionPanel
                :eyebrow="t('municipality.relatedMarkets')"
                :title="t('municipality.nearbyBenchmarks')"
                compact
              >
                <DataTable
                  :value="detail.related_municipalities || []"
                  size="small"
                  striped-rows
                  responsive-layout="scroll"
                  table-style="min-width: 100%"
                >
                  <Column field="municipality" :header="t('dashboard.municipality')">
                    <template #body="{ data }">
                      <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                        {{ data.municipality }}
                      </RouterLink>
                    </template>
                  </Column>
                  <Column field="region" :header="t('map.region')" />
                  <Column field="count" :header="t('dashboard.transactions')">
                    <template #body="{ data }">{{ formatNumber(data.count) }}</template>
                  </Column>
                  <Column field="median_price_per_m2" :header="t('dashboard.pricePerM2')">
                    <template #body="{ data }">
                      {{ formatCurrency(data.median_price_per_m2) }}
                    </template>
                  </Column>
                </DataTable>
              </SectionPanel>
            </section>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </template>
  </div>
</template>

<style scoped>
  .municipality-page,
  .tab-grid,
  .related-list,
  .mix-list,
  .benchmark-grid {
    display: grid;
    gap: var(--space-grid);
  }

  .municipality-page {
    gap: var(--space-section);
  }

  .state-frame {
    display: grid;
    place-items: center;
    min-height: 28rem;
    padding: 1.2rem;
    border-radius: calc(var(--radius-lg) + 0.15rem);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 12%, transparent),
        transparent 35%
      ),
      var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  .state-frame-stack {
    gap: 0.9rem;
  }

  .state-frame-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.75rem;
  }

  .explore-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .section-note {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.6;
  }

  .tab-grid {
    grid-template-columns: minmax(0, 1.35fr) minmax(0, 0.95fr);
  }

  .related-list {
    gap: 0.75rem;
  }

  .related-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.95rem 1rem;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 96%, transparent),
        transparent 120%
      ),
      var(--surface-soft);
    text-decoration: none;
    color: inherit;
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-sm);
  }

  .related-card:hover,
  .related-card:focus-visible {
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border) 66%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      var(--shadow-md);
    outline: none;
  }

  .related-copy {
    display: grid;
    gap: 0.2rem;
  }

  .related-copy small,
  .mix-copy small,
  .benchmark-card small {
    color: var(--text-muted);
  }

  .mix-row {
    display: grid;
    gap: 0.45rem;
  }

  .mix-copy {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }

  .mix-bar {
    height: 0.72rem;
    overflow: hidden;
    border-radius: 999px;
    background: var(--surface-muted);
  }

  .mix-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--primary), var(--secondary));
  }

  .benchmark-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .benchmark-card {
    padding: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: var(--radius-sm);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card-strong) 94%, transparent),
        transparent 120%
      ),
      var(--surface-soft);
  }

  .benchmark-card span {
    display: block;
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .benchmark-card strong {
    display: block;
    margin-top: 0.35rem;
    font-size: 1.4rem;
    line-height: 1.1;
    letter-spacing: -0.04em;
  }

  .municipality-tabs {
    display: grid;
    gap: 1rem;
  }

  .municipality-tabs :deep(.p-tablist) {
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--primary) 24%);
    border-radius: calc(var(--radius-lg) + 0.1rem);
    background: var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  .municipality-tabs :deep(.p-tab) {
    min-height: 2.8rem;
    border-radius: var(--radius-sm);
  }

  .table-link {
    color: inherit;
    text-decoration: none;
  }

  @media (max-width: 980px) {
    .tab-grid,
    .benchmark-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .related-card {
      flex-direction: column;
      align-items: stretch;
    }

    .explore-actions {
      width: 100%;
    }

    .explore-actions :deep(.p-button),
    .explore-actions > * {
      flex: 1 1 220px;
    }
  }
</style>
