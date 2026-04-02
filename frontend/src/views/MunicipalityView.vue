<script setup lang="ts">
  import { computed, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import TabPanel from 'primevue/tabpanel'
  import TabView from 'primevue/tabview'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PropertyTypePieChart from '../components/charts/PropertyTypePieChart.vue'
  import TrendLineChart from '../components/charts/TrendLineChart.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
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
  const transactions = ref<any>({ items: [], total: 0, page: 1, page_size: 12 })

  const tabIndexMap: Record<string, number> = {
    overview: 0,
    transactions: 1,
    type_mix: 2,
    benchmarks: 3,
  }
  const tabNames = ['overview', 'transactions', 'type_mix', 'benchmarks']
  const activeTab = computed({
    get: () => tabIndexMap[viewerQuery.state.tab] ?? 0,
    set: (index: number) => viewerQuery.patchState({ tab: tabNames[index] || 'overview' }),
  })

  const detail = computed(() => stats.municipalityDetail)
  const propertyTypeOptions = computed(() => [
    { label: t('market.allPropertyTypes'), value: '' },
    ...((detail.value?.property_type_mix || []) as any[]).map((item) => ({
      label: getPropertyTypeLabel(item.property_type, t),
      value: item.property_type,
    })),
  ])
  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: '' },
    ...((detail.value?.year_trend || []) as any[]).map((item) => ({
      label: String(item.year),
      value: String(item.year),
    })),
  ])

  const heroMetrics = computed(() => [
    {
      label: t('dashboard.transactions'),
      value: formatNumber(detail.value?.overview?.count),
      meta: t('municipality.coverageWindow', {
        from: detail.value?.overview?.earliest_year || '-',
        to: detail.value?.overview?.latest_year || '-',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(detail.value?.overview?.median_price),
      meta: `${formatNumber(detail.value?.overview?.avg_area, { maximumFractionDigits: 1 })} m²`,
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(detail.value?.overview?.median_price_per_m2),
      meta: detail.value?.region || '-',
      tone: 'success',
    },
  ])

  const yearTrendRows = computed(() =>
    (detail.value?.year_trend || []).map((item: any) => ({
      year: item.year,
      count: item.count,
      median_price: item.median_price,
      median_price_per_m2: item.median_price_per_m2,
    })),
  )

  function shareStyle(share: number | null | undefined) {
    return { width: `${Math.max(10, Math.round((share || 0) * 100))}%` }
  }

  async function loadTransactions() {
    const { data } = await stats.fetchMunicipalityTransactions(String(route.params.slug), {
      property_type: viewerQuery.state.property_type || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
      page: transactions.value.page,
      page_size: transactions.value.page_size,
      sort: 'recent',
      order: 'desc',
    })
    transactions.value = data
  }

  async function loadMunicipality() {
    loading.value = true
    error.value = ''
    try {
      await Promise.all([
        stats.fetchMunicipalityDetail(String(route.params.slug)),
        loadTransactions(),
      ])
    } catch (err) {
      stats.resetMunicipalityDetail()
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  function openPrediction(transaction: any = null) {
    router.push({
      name: 'prediction',
      query: {
        municipality: detail.value?.municipality || '',
        property_type: transaction?.property_type || 'stanovanje',
        size_m2: transaction?.size_m2 || detail.value?.overview?.avg_area || '',
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

  function onTransactionsPage(event: any) {
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
    <div v-if="loading" class="state-card">
      <LoadingSpinner :label="t('common.loading')" />
    </div>

    <p v-else-if="error" class="state-card error-text">{{ error }}</p>

    <template v-else-if="detail">
      <section class="municipality-hero">
        <div>
          <span class="eyebrow">{{ t('municipality.pageEyebrow') }}</span>
          <h1>{{ detail.municipality }}</h1>
          <p>{{ t('municipality.heroBody', { region: detail.region || '-' }) }}</p>

          <div class="hero-actions">
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
            <RouterLink
              :to="{
                path: '/trg',
                query: {
                  tab: 'transactions',
                  municipality: detail.municipality,
                  property_type: viewerQuery.state.property_type || undefined,
                  year: viewerQuery.state.year || undefined,
                  search: viewerQuery.state.search || undefined,
                },
              }"
              class="hero-link"
            >
              <Button
                icon="pi pi-table"
                severity="secondary"
                outlined
                :label="t('market.tabTransactions')"
              />
            </RouterLink>
          </div>
        </div>

        <div class="hero-side">
          <MetricCard
            v-for="card in heroMetrics"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :meta="card.meta"
            :tone="card.tone || 'default'"
          />

          <article class="metric-card accent">
            <span>{{ t('municipality.regionStanding') }}</span>
            <strong>#{{ detail.market_position?.region_rank_by_price_per_m2 || '-' }}</strong>
            <p>
              {{
                t('municipality.activityRankLabel', {
                  count: detail.market_position?.region_rank_by_activity || '-',
                })
              }}
            </p>
          </article>
        </div>
      </section>

      <section class="panel">
        <div class="filter-grid">
          <label class="field-inline">
            <span>{{ t('market.selectPropertyType') }}</span>
            <Select
              v-model="viewerQuery.state.property_type"
              :options="propertyTypeOptions"
              option-label="label"
              option-value="value"
            />
          </label>
          <label class="field-inline">
            <span>{{ t('map.year') }}</span>
            <Select
              v-model="viewerQuery.state.year"
              :options="yearOptions"
              option-label="label"
              option-value="value"
            />
          </label>
          <label class="field-inline search-field">
            <span>{{ t('common.search') }}</span>
            <InputText v-model="viewerQuery.state.search" :placeholder="t('common.search')" />
          </label>
        </div>
      </section>

      <TabView v-model:active-index="activeTab">
        <TabPanel value="0" :header="t('common.overview')">
          <section class="content-grid">
            <article class="panel">
              <div class="panel-head">
                <div>
                  <span class="eyebrow subtle">{{ t('municipality.trendChart') }}</span>
                  <h2>{{ t('municipality.yearTrend') }}</h2>
                </div>
              </div>
              <TrendLineChart
                v-if="yearTrendRows.length"
                :data="yearTrendRows"
                metric="median_price"
              />
              <EmptyState v-else :message="t('common.noData')" />
            </article>

            <article class="panel">
              <div class="panel-head">
                <div>
                  <span class="eyebrow subtle">{{ t('municipality.relatedMarkets') }}</span>
                  <h2>{{ t('municipality.nearbyBenchmarks') }}</h2>
                </div>
              </div>
              <div v-if="detail.related_municipalities?.length" class="related-list">
                <RouterLink
                  v-for="item in detail.related_municipalities"
                  :key="item.slug"
                  :to="`/obcine/${item.slug}`"
                  class="related-card"
                >
                  <div>
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
            </article>
          </section>
        </TabPanel>

        <TabPanel value="1" :header="t('market.tabTransactions')">
          <section class="tab-content">
            <section class="panel">
              <DataTable
                :value="transactions.items"
                lazy
                paginator
                :rows="transactions.page_size"
                :first="(transactions.page - 1) * transactions.page_size"
                :total-records="transactions.total"
                size="small"
                striped-rows
                responsive-layout="scroll"
                table-style="min-width: 100%"
                @page="onTransactionsPage"
              >
                <Column field="property_type" :header="t('predict.propertyType')">
                  <template #body="{ data }">
                    {{ getPropertyTypeLabel(data.property_type, t) }}
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
                <Column field="price_per_m2" header="€/m²">
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
            </section>
          </section>
        </TabPanel>

        <TabPanel value="2" :header="t('municipality.propertyMix')">
          <section class="content-grid">
            <article class="panel">
              <div class="panel-head">
                <div>
                  <span class="eyebrow subtle">{{ t('municipality.propertyChart') }}</span>
                  <h2>{{ t('municipality.propertyMix') }}</h2>
                </div>
              </div>
              <PropertyTypePieChart
                v-if="detail.property_type_mix?.length"
                :items="detail.property_type_mix"
              />
              <EmptyState v-else :message="t('common.noData')" />
            </article>

            <article class="panel">
              <div v-if="detail.property_type_mix?.length" class="mix-list">
                <div
                  v-for="item in detail.property_type_mix"
                  :key="item.property_type"
                  class="mix-row"
                >
                  <div class="mix-copy">
                    <strong>{{ getPropertyTypeLabel(item.property_type, t) }}</strong>
                    <small>{{ formatPercent(item.share) }}</small>
                  </div>
                  <div class="mix-bar"><span :style="shareStyle(item.share)"></span></div>
                </div>
              </div>
              <EmptyState v-else :message="t('common.noData')" />
            </article>
          </section>
        </TabPanel>

        <TabPanel value="3" :header="t('common.compare')">
          <section class="tab-content">
            <section class="panel">
              <div class="panel-head">
                <div>
                  <span class="eyebrow subtle">{{ t('municipality.relatedMarkets') }}</span>
                  <h2>{{ t('municipality.nearbyBenchmarks') }}</h2>
                </div>
              </div>
              <div class="benchmark-grid">
                <article class="benchmark-card">
                  <span>{{ t('municipality.regionStanding') }}</span>
                  <strong>#{{ detail.market_position?.region_rank_by_price_per_m2 || '-' }}</strong>
                  <small>{{ detail.region || '-' }}</small>
                </article>
                <article class="benchmark-card">
                  <span>{{ t('regions.mostActive') }}</span>
                  <strong>#{{ detail.market_position?.region_rank_by_activity || '-' }}</strong>
                  <small>{{ t('dashboard.transactions') }}</small>
                </article>
              </div>
            </section>

            <section class="panel">
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
                <Column field="median_price_per_m2" header="€/m²">
                  <template #body="{ data }">
                    {{ formatCurrency(data.median_price_per_m2) }}
                  </template>
                </Column>
              </DataTable>
            </section>
          </section>
        </TabPanel>
      </TabView>
    </template>
  </div>
</template>

<style scoped>
  .municipality-page,
  .hero-side,
  .hero-actions,
  .filter-grid,
  .content-grid,
  .tab-content,
  .benchmark-grid,
  .mix-list {
    display: grid;
    gap: 1rem;
  }
  .municipality-page {
    gap: 1.2rem;
  }
  .municipality-hero,
  .panel,
  .metric-card,
  .state-card {
    border: 1px solid var(--border);
    border-radius: 1.6rem;
    background: var(--surface-soft);
    box-shadow: var(--shadow-sm);
  }
  .municipality-hero {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.95fr);
    gap: 1.1rem;
    padding: 1.35rem;
    background: linear-gradient(135deg, var(--surface-strong), var(--surface-soft));
  }
  .municipality-hero h1,
  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
  }
  .municipality-hero h1 {
    font-size: clamp(2rem, 4vw, 3rem);
    line-height: 1.05;
  }
  .municipality-hero p,
  .metric-card p,
  .related-card small {
    color: var(--text-muted);
  }
  .eyebrow {
    display: inline-flex;
    margin-bottom: 0.55rem;
    color: var(--primary-strong);
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.17em;
    text-transform: uppercase;
  }
  .eyebrow.subtle {
    color: var(--text-soft);
  }
  .hero-actions {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 1.1rem;
  }
  .hero-link,
  .table-link {
    color: inherit;
    text-decoration: none;
  }
  .hero-side {
    align-content: start;
  }
  .metric-card,
  .panel {
    padding: 1rem;
  }
  .metric-card.accent {
    background: linear-gradient(
      135deg,
      var(--surface-dark),
      color-mix(in srgb, var(--surface-dark) 80%, var(--primary) 20%)
    );
    color: var(--shell-text);
  }
  .filter-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    align-items: end;
  }
  .field-inline {
    display: grid;
    gap: 0.35rem;
  }
  .field-inline span {
    font-size: 0.82rem;
    color: var(--text-muted);
    font-weight: 700;
  }
  .search-field {
    grid-column: span 1;
  }
  .content-grid {
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.95fr);
  }
  .panel-head {
    margin-bottom: 0.95rem;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .related-list {
    display: grid;
    gap: 0.8rem;
  }
  .related-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem;
    border-radius: 1.15rem;
    border: 1px solid var(--border);
    background: var(--surface-soft-muted);
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
    background: linear-gradient(90deg, var(--warning), var(--secondary));
  }
  .benchmark-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .benchmark-card {
    padding: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: 1.2rem;
    background: color-mix(in srgb, var(--surface-strong) 88%, var(--overlay-strong) 12%);
  }
  .benchmark-card span {
    display: block;
    color: var(--text-soft);
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 800;
  }
  .benchmark-card strong {
    display: block;
    margin-top: 0.3rem;
    font-size: 1.4rem;
  }
  .state-card {
    padding: 1.6rem;
  }
  @media (max-width: 980px) {
    .municipality-hero,
    .content-grid,
    .filter-grid,
    .hero-actions,
    .benchmark-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
