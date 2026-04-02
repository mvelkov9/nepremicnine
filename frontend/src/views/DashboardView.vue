<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import PropertyTypePieChart from '../components/charts/PropertyTypePieChart.vue'
  import TrendLineChart from '../components/charts/TrendLineChart.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import {
    buildWorkspaceRoute,
    toLocationQuery,
    workspacePageTitleKeys,
  } from '../constants/workbench'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import api from '../composables/useApi'
  import { useAuthStore } from '../stores/auth'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import type { SavedWorkspace } from '../types/api'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const auth = useAuthStore()
  const stats = useStatsStore()
  const workbench = useWorkbenchStore()
  const viewerQuery = useViewerQueryState({
    property_type: '',
    region: '',
    municipality: '',
    year: '',
  })

  const loading = ref(true)
  const pageError = ref('')
  const allMunicipalities = ref<Array<{ municipality: string; region?: string }>>([])

  const marketHome = computed<any>(
    () =>
      stats.marketHome || {
        headline: {},
        market_coverage: {},
        largest_markets: [],
        price_leaders: [],
        region_snapshot: [],
        latest_sales: [],
        property_type_mix: [],
        year_coverage: [],
      },
  )

  const propertyTypeOptions = computed(() => [
    { label: t('dashboard.filterAllTypes'), value: '' },
    ...(marketHome.value.property_type_mix || []).map((item: any) => ({
      label: getPropertyTypeLabel(item.property_type, t),
      value: item.property_type,
    })),
  ])

  const regionOptions = computed(() => {
    const regions = [...new Set(allMunicipalities.value.map((item) => item.region).filter(Boolean))]
    return [
      { label: t('municipalities.allRegions'), value: '' },
      ...regions.sort().map((region) => ({ label: region as string, value: region as string })),
    ]
  })

  const municipalityOptions = computed(() => {
    const items = viewerQuery.state.region
      ? allMunicipalities.value.filter((item) => item.region === viewerQuery.state.region)
      : allMunicipalities.value
    return [
      { label: t('map.allMunicipalities'), value: '' },
      ...items.map((item) => ({ label: item.municipality, value: item.municipality })),
    ]
  })

  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: '' },
    ...((marketHome.value.year_coverage || []) as any[]).map((item) => ({
      label: String(item.year),
      value: String(item.year),
    })),
  ])

  const summaryCards = computed(() => [
    {
      label: t('dashboard.totalRecords'),
      value: formatNumber(marketHome.value.headline?.total_records),
      meta: t('dashboard.marketCoverageYears', {
        from: marketHome.value.headline?.earliest_year || '-',
        to: marketHome.value.headline?.latest_year || '-',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(marketHome.value.headline?.median_price),
      meta: t('dashboard.latestYearLabel', {
        year: marketHome.value.headline?.latest_year || '-',
      }),
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(marketHome.value.headline?.avg_price_per_m2),
      meta:
        viewerQuery.activeFilterCount.value > 0
          ? t('dashboard.filteredSummary')
          : t('dashboard.filterAllTypes'),
      tone: 'success',
    },
    {
      label: t('dashboard.marketCoverageLabel'),
      value: `${formatNumber(marketHome.value.market_coverage?.present)} / ${formatNumber(marketHome.value.market_coverage?.official_total)}`,
      meta: t('dashboard.marketMunicipalities', {
        count: formatNumber(marketHome.value.market_coverage?.present),
      }),
      tone: 'warning',
    },
  ])

  const latestSales = computed(() => stats.transactionsExplorer?.items || [])
  const topRegions = computed(() => stats.regionsExplorer?.items?.slice(0, 5) || [])
  const municipalitySpotlight = computed(() => stats.municipalitiesExplorer?.items?.[0] || null)
  const trendData = computed(() => stats.trend || [])
  const propertyMix = computed(() => marketHome.value.property_type_mix || [])
  const pinnedWorkspaces = computed(() => workbench.pinnedWorkspaces.slice(0, 4))
  const watchlistFeed = computed(() => workbench.watchlistFeed.slice(0, 4))
  const recentWorkflows = computed(() => workbench.recentRoutes.slice(0, 4))
  const activeFilterCountValue = computed(() => viewerQuery.activeFilterCount.value)
  const activeFilterTagSeverity = computed(() =>
    activeFilterCountValue.value > 0 ? 'contrast' : 'secondary',
  )
  const activeFilterTagLabel = computed(() =>
    activeFilterCountValue.value > 0
      ? t('dashboard.activeFilterCount', { count: activeFilterCountValue.value })
      : t('dashboard.noActiveFilters'),
  )

  function viewerParams() {
    return {
      property_type: viewerQuery.state.property_type || undefined,
      region: viewerQuery.state.region || undefined,
      municipality: viewerQuery.state.municipality || undefined,
      year: viewerQuery.state.year || undefined,
    }
  }

  function routeQuery(extra: Record<string, string> = {}) {
    return toLocationQuery({ ...viewerParams(), ...extra })
  }

  function workspaceLink(item: SavedWorkspace) {
    return buildWorkspaceRoute(item.page, {
      ...(item.filters || {}),
      ...(item.tab ? { tab: item.tab } : {}),
      ...(item.sort ? { sort: item.sort } : {}),
    })
  }

  function workspacePageLabel(page: string) {
    return t(workspacePageTitleKeys[page] || 'app.title')
  }

  async function loadReferenceData() {
    try {
      const { data } = await api.get('/api/regions/municipalities')
      allMunicipalities.value = data || []
    } catch {
      allMunicipalities.value = []
    }
  }

  async function loadDashboard() {
    loading.value = true
    pageError.value = ''

    try {
      const params = viewerParams()
      await Promise.all([
        stats.fetchMarketHome(params),
        stats.fetchTrend({
          property_type: params.property_type,
          region: params.region,
          municipality: params.municipality,
        }),
        stats.fetchTransactionsExplorer({
          ...params,
          page: 1,
          page_size: 6,
          sort: 'recent',
          order: 'desc',
        }),
        stats.fetchRegionsExplorer({
          ...params,
          page: 1,
          page_size: 8,
          sort: 'count',
          order: 'desc',
        }),
        stats.fetchMunicipalitiesExplorer({
          ...params,
          page: 1,
          page_size: 8,
          sort: 'count',
          order: 'desc',
        }),
      ])
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
    } finally {
      loading.value = false
    }
  }

  function clearFilters() {
    viewerQuery.resetState()
  }

  async function watchMunicipalitySpotlight() {
    if (!municipalitySpotlight.value) return
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: municipalitySpotlight.value.slug,
      display_label: municipalitySpotlight.value.municipality,
      metadata: {
        link: `/obcine/${municipalitySpotlight.value.slug}`,
        region: municipalitySpotlight.value.region,
      },
    })
    await workbench.fetchWatchlistFeed()
  }

  watch(
    () => viewerQuery.state.region,
    (region) => {
      if (!region) return
      const valid = allMunicipalities.value.some(
        (item) => item.region === region && item.municipality === viewerQuery.state.municipality,
      )
      if (!valid) viewerQuery.patchState({ municipality: '' })
    },
  )

  watch(
    () => [
      viewerQuery.state.property_type,
      viewerQuery.state.region,
      viewerQuery.state.municipality,
      viewerQuery.state.year,
    ],
    () => {
      void loadDashboard()
    },
  )

  onMounted(async () => {
    await Promise.all([
      loadReferenceData(),
      workbench.fetchWorkspaces(),
      workbench.fetchWatchlistFeed(),
    ])
    await loadDashboard()
  })
</script>

<template>
  <div class="dashboard-page">
    <section class="hero-shell dashboard-hero">
      <PageHeader
        :eyebrow="t('dashboard.consumerKicker')"
        :title="t('dashboard.consumerTitle')"
        :description="t('dashboard.consumerBody')"
      >
        <template #actions>
          <SavedWorkspaceMenu
            page="dashboard"
            :state="{
              page: 'dashboard',
              filters: viewerParams(),
            }"
          />
          <RouterLink
            :to="{ path: '/trg', query: routeQuery({ tab: 'overview' }) }"
            class="hero-link"
          >
            <Button severity="secondary" outlined icon="pi pi-chart-bar" :label="t('nav.market')" />
          </RouterLink>
          <RouterLink
            :to="{ path: '/zemljevid', query: routeQuery({ view: 'transactions' }) }"
            class="hero-link"
          >
            <Button
              severity="secondary"
              outlined
              icon="pi pi-map"
              :label="t('dashboard.quickMap')"
            />
          </RouterLink>
          <RouterLink :to="{ path: '/napoved', query: routeQuery() }" class="hero-link">
            <Button icon="pi pi-bolt" :label="t('dashboard.quickPrediction')" />
          </RouterLink>
          <RouterLink v-if="auth.isAdmin" to="/admin" class="hero-link">
            <Button severity="contrast" outlined icon="pi pi-cog" :label="t('nav.admin')" />
          </RouterLink>
        </template>
      </PageHeader>

      <div class="hero-summary">
        <MetricCard
          v-for="card in summaryCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
          :meta="card.meta"
          :tone="card.tone || 'default'"
        />
      </div>
    </section>

    <section class="panel filter-panel">
      <div class="panel-head compact">
        <div>
          <p class="eyebrow subtle">{{ t('dashboard.activeFilters') }}</p>
          <h2>{{ t('dashboard.marketLens') }}</h2>
        </div>
        <div class="filter-summary">
          <Tag :severity="activeFilterTagSeverity" :value="activeFilterTagLabel" />
          <Button
            severity="secondary"
            outlined
            icon="pi pi-filter-slash"
            :label="t('map.clearFilter')"
            @click="clearFilters"
          />
        </div>
      </div>

      <div class="filter-grid">
        <label class="field-inline">
          <span>{{ t('dashboard.filterByType') }}</span>
          <Select
            v-model="viewerQuery.state.property_type"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </label>

        <label class="field-inline">
          <span>{{ t('municipalities.filterByRegion') }}</span>
          <Select
            v-model="viewerQuery.state.region"
            :options="regionOptions"
            option-label="label"
            option-value="value"
          />
        </label>

        <label class="field-inline">
          <span>{{ t('dashboard.municipality') }}</span>
          <Select
            v-model="viewerQuery.state.municipality"
            :options="municipalityOptions"
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
      </div>
    </section>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />
    <p v-else-if="pageError" class="state-card error-text">{{ pageError }}</p>

    <template v-else>
      <div class="dashboard-grid">
        <section class="panel trend-panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.priceTrend') }}</p>
              <h2>{{ t('market.trendTitle') }}</h2>
            </div>
            <RouterLink
              :to="{ path: '/trg', query: routeQuery({ tab: 'overview' }) }"
              class="hero-link"
            >
              <Button
                severity="secondary"
                outlined
                size="small"
                :label="t('market.viewAll')"
                icon="pi pi-arrow-right"
                icon-pos="right"
              />
            </RouterLink>
          </div>
          <TrendLineChart v-if="trendData.length" :data="trendData" compact />
          <EmptyState v-else :message="t('common.noData')" />
        </section>

        <section class="panel mix-panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.propertyMix') }}</p>
              <h2>{{ t('dashboard.propertyMixTitle') }}</h2>
            </div>
            <RouterLink
              :to="{ path: '/trg', query: routeQuery({ tab: 'distribution' }) }"
              class="hero-link"
            >
              <Button
                severity="secondary"
                outlined
                size="small"
                :label="t('market.viewAll')"
                icon="pi pi-arrow-right"
                icon-pos="right"
              />
            </RouterLink>
          </div>
          <PropertyTypePieChart v-if="propertyMix.length" :items="propertyMix" />
          <EmptyState v-else :message="t('common.noData')" />
        </section>

        <aside class="panel municipality-spotlight">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.municipalitySpotlight') }}</p>
              <h2>{{ municipalitySpotlight?.municipality || t('common.noData') }}</h2>
            </div>
            <Tag severity="contrast" :value="t('dashboard.marketTableTitle')" />
          </div>

          <template v-if="municipalitySpotlight">
            <p class="spotlight-copy">{{ municipalitySpotlight.region || '-' }}</p>
            <div class="spotlight-metrics">
              <div>
                <span>{{ t('dashboard.transactions') }}</span>
                <strong>{{ formatNumber(municipalitySpotlight.count) }}</strong>
              </div>
              <div>
                <span>{{ t('dashboard.pricePerM2') }}</span>
                <strong>{{ formatCurrency(municipalitySpotlight.median_price_per_m2) }}</strong>
              </div>
            </div>
            <div class="spotlight-actions">
              <RouterLink :to="`/obcine/${municipalitySpotlight.slug}`" class="hero-link">
                <Button
                  severity="contrast"
                  outlined
                  icon="pi pi-building"
                  :label="t('municipalities.viewDetail')"
                />
              </RouterLink>
              <RouterLink
                :to="{
                  path: '/trg',
                  query: routeQuery({
                    tab: 'transactions',
                    municipality: municipalitySpotlight.municipality,
                  }),
                }"
                class="hero-link"
              >
                <Button
                  severity="secondary"
                  outlined
                  icon="pi pi-table"
                  :label="t('market.tabTransactions')"
                />
              </RouterLink>
              <Button
                severity="secondary"
                text
                icon="pi pi-bookmark"
                :label="t('workbench.watch')"
                @click="watchMunicipalitySpotlight"
              />
            </div>
          </template>
          <EmptyState v-else :message="t('common.noData')" />
        </aside>
      </div>

      <div class="dashboard-grid bottom-grid">
        <section class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.regionSnapshot') }}</p>
              <h2>{{ t('dashboard.regionTableTitle') }}</h2>
            </div>
            <RouterLink
              :to="{ path: '/regije', query: routeQuery({ tab: 'table' }) }"
              class="hero-link"
            >
              <Button
                severity="secondary"
                outlined
                size="small"
                :label="t('market.viewAll')"
                icon="pi pi-arrow-right"
                icon-pos="right"
              />
            </RouterLink>
          </div>

          <div v-if="topRegions.length" class="region-ranking">
            <RouterLink
              v-for="(region, index) in topRegions"
              :key="region.region"
              :to="{
                path: '/regije',
                query: routeQuery({ tab: 'drilldown', region: region.region }),
              }"
              class="region-rank-row"
            >
              <span class="rank-badge">#{{ index + 1 }}</span>
              <div>
                <strong>{{ region.region }}</strong>
                <p class="muted">
                  {{ formatNumber(region.count) }} {{ t('dashboard.transactions') }}
                </p>
              </div>
              <Tag severity="success" :value="`${formatCurrency(region.median_price_per_m2)}/m²`" />
            </RouterLink>
          </div>
          <EmptyState v-else :message="t('common.noData')" />
        </section>

        <section class="panel quick-panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.workflowTitle') }}</p>
              <h2>{{ t('dashboard.quickActionsTitle') }}</h2>
            </div>
          </div>

          <div class="quick-actions">
            <RouterLink
              :to="{ path: '/trg', query: routeQuery({ tab: 'transactions' }) }"
              class="quick-link"
            >
              <strong>{{ t('market.tabTransactions') }}</strong>
              <small>{{ t('dashboard.quickTransactionsBody') }}</small>
            </RouterLink>
            <RouterLink
              :to="{ path: '/regije', query: routeQuery({ tab: 'table' }) }"
              class="quick-link"
            >
              <strong>{{ t('nav.regions') }}</strong>
              <small>{{ t('dashboard.quickRegionsBody') }}</small>
            </RouterLink>
            <RouterLink
              :to="{ path: '/obcine', query: routeQuery({ tab: 'table' }) }"
              class="quick-link"
            >
              <strong>{{ t('nav.municipalities') }}</strong>
              <small>{{ t('dashboard.quickMunicipalitiesBody') }}</small>
            </RouterLink>
            <RouterLink :to="{ path: '/analiza', query: routeQuery() }" class="quick-link">
              <strong>{{ t('nav.analysis') }}</strong>
              <small>{{ t('dashboard.quickAnalysisBody') }}</small>
            </RouterLink>
          </div>
        </section>
      </div>

      <div class="dashboard-grid bottom-grid">
        <section class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('workbench.pinnedWorkspaces') }}</p>
              <h2>{{ t('workbench.resumeWork') }}</h2>
            </div>
          </div>

          <div v-if="pinnedWorkspaces.length" class="quick-actions">
            <RouterLink
              v-for="item in pinnedWorkspaces"
              :key="item.id"
              :to="workspaceLink(item)"
              class="quick-link"
            >
              <strong>{{ item.name }}</strong>
              <small>{{ workspacePageLabel(item.page) }}</small>
            </RouterLink>
          </div>
          <EmptyState v-else :message="t('workbench.noPinnedWorkspaces')" />
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('workbench.watchlistFeed') }}</p>
              <h2>{{ t('workbench.marketSignals') }}</h2>
            </div>
          </div>

          <div v-if="watchlistFeed.length" class="quick-actions">
            <RouterLink
              v-for="item in watchlistFeed"
              :key="item.id"
              :to="item.link || '/obcine'"
              class="quick-link"
            >
              <strong>{{ item.display_label }}</strong>
              <small>
                {{ item.headline_label }}: {{ formatCurrency(item.headline_value) }}
                <template v-if="item.trend_value != null"> · {{ item.trend_value }}%</template>
              </small>
            </RouterLink>
          </div>
          <EmptyState v-else :message="t('workbench.noWatchlistFeed')" />
        </section>
      </div>

      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow subtle">{{ t('workbench.recentWorkflows') }}</p>
            <h2>{{ t('workbench.recentWorkflowsTitle') }}</h2>
          </div>
        </div>

        <div v-if="recentWorkflows.length" class="quick-actions">
          <RouterLink
            v-for="item in recentWorkflows"
            :key="`${item.path}-${item.label}`"
            :to="{ path: item.path, query: toLocationQuery(item.query as Record<string, unknown>) }"
            class="quick-link"
          >
            <strong>{{ item.label }}</strong>
            <small>{{ item.path }}</small>
          </RouterLink>
        </div>
        <EmptyState v-else :message="t('workbench.noRecentWorkflows')" />
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow subtle">{{ t('dashboard.recentSales') }}</p>
            <h2>{{ t('dashboard.latestTransactions') }}</h2>
          </div>
          <RouterLink
            :to="{ path: '/trg', query: routeQuery({ tab: 'transactions' }) }"
            class="hero-link"
          >
            <Button
              severity="secondary"
              outlined
              size="small"
              :label="t('market.viewAll')"
              icon="pi pi-arrow-right"
              icon-pos="right"
            />
          </RouterLink>
        </div>

        <DataTable
          :value="latestSales"
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
          <Column field="property_type" :header="t('predict.propertyType')">
            <template #body="{ data }">{{ getPropertyTypeLabel(data.property_type, t) }}</template>
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
        </DataTable>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .dashboard-page {
    display: grid;
    gap: 1.2rem;
  }

  .dashboard-hero,
  .panel,
  .state-card {
    border: 1px solid var(--border);
    border-radius: 1.6rem;
  }

  .dashboard-hero,
  .panel {
    background:
      linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft)), var(--surface-soft);
    box-shadow: var(--shadow-sm);
    padding: 1.25rem;
  }

  .hero-summary,
  .filter-grid,
  .dashboard-grid,
  .quick-actions,
  .spotlight-metrics {
    display: grid;
    gap: 0.9rem;
  }

  .hero-summary {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .filter-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .dashboard-grid {
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) minmax(300px, 0.78fr);
    align-items: stretch;
  }

  .bottom-grid {
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  }

  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.85rem;
  }

  .panel-head.compact {
    align-items: center;
  }

  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.12rem, 1.8vw, 1.48rem);
    line-height: 1.08;
  }

  .eyebrow.subtle {
    color: var(--text-soft);
  }

  .field-inline {
    display: grid;
    gap: 0.35rem;
  }

  .field-inline span {
    color: var(--text-muted);
    font-size: 0.82rem;
    font-weight: 700;
  }

  .filter-summary {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .municipality-spotlight {
    display: grid;
    gap: 0.9rem;
    align-content: start;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 84%, transparent),
        var(--surface-soft)
      ),
      var(--surface-soft);
  }

  .spotlight-copy {
    margin: 0;
    color: var(--text-muted);
  }

  .spotlight-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .spotlight-metrics div,
  .quick-link {
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: 1.15rem;
    padding: 0.9rem 1rem;
    background: color-mix(in srgb, var(--surface-strong) 88%, var(--overlay-strong) 12%);
  }

  .spotlight-metrics span {
    display: block;
    color: var(--text-soft);
    font-size: 0.72rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 800;
  }

  .spotlight-metrics strong {
    display: block;
    margin-top: 0.3rem;
    font-size: 1.15rem;
  }

  .spotlight-actions {
    display: grid;
    gap: 0.65rem;
  }

  .region-ranking,
  .quick-actions {
    display: grid;
    gap: 0.7rem;
  }

  .region-rank-row,
  .hero-link,
  .table-link,
  .quick-link {
    text-decoration: none;
    color: inherit;
  }

  .region-rank-row {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 0.75rem;
    padding: 0.8rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: 1.15rem;
    background: color-mix(in srgb, var(--surface-strong) 88%, var(--overlay-strong) 12%);
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .region-rank-row:hover,
  .quick-link:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    box-shadow: 0 16px 28px color-mix(in srgb, var(--shadow-color) 12%, transparent);
  }

  .rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--primary) 12%, transparent);
    color: var(--primary);
    font-weight: 800;
  }

  .quick-link {
    display: grid;
    gap: 0.25rem;
  }

  .quick-link strong {
    font-size: 0.96rem;
  }

  .quick-link small {
    color: var(--text-muted);
    line-height: 1.5;
  }

  .table-link {
    font-weight: 700;
  }

  .state-card {
    padding: 1.1rem 1.2rem;
  }

  @media (max-width: 1200px) {
    .dashboard-grid,
    .bottom-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 980px) {
    .hero-summary,
    .filter-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .hero-summary,
    .filter-grid,
    .spotlight-metrics {
      grid-template-columns: 1fr;
    }

    .dashboard-hero :deep(.page-header-actions) {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr;
    }

    .dashboard-hero :deep(.page-header-actions .p-button) {
      width: 100%;
    }
  }
</style>
