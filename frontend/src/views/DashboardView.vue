<script setup lang="ts">
  import { computed, onMounted, reactive, ref, watch } from 'vue'
  import { RouterLink, type RouteLocationRaw } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import FilterBar from '../components/FilterBar.vue'
  import FilterField from '../components/FilterField.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SectionPanel from '../components/SectionPanel.vue'
  import PropertyTypePieChart from '../components/charts/PropertyTypePieChart.vue'
  import TrendLineChart from '../components/charts/TrendLineChart.vue'
  import DashboardActionGrid from '../features/dashboard/DashboardActionGrid.vue'
  import DashboardWorkspaceHub from '../features/dashboard/DashboardWorkspaceHub.vue'
  import { useFilterOptions } from '../composables/useFilterOptions'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import {
    buildWorkspaceRoute,
    describeRoute,
    toLocationQuery,
    workspacePageTitleKeys,
  } from '../constants/workbench'
  import { useReferenceDataStore } from '../stores/referenceData'
  import { useStatsStore } from '../stores/stats'
  import { useWorkbenchStore } from '../stores/workbench'
  import type {
    MunicipalityExplorerItem,
    PropertyTypeMix,
    RegionExplorerItem,
    SavedWorkspace,
    TransactionRecord,
    WatchlistFeedItem,
  } from '../types/api'
  import { getApiErrorMessage } from '../utils/apiError'
  import { useFormat } from '../composables/useFormat'
  import { formatCurrency, formatNumber } from '../utils/format'

  const { t } = useI18n()
  const { formatType } = useFormat()
  const stats = useStatsStore()
  const workbench = useWorkbenchStore()
  const referenceData = useReferenceDataStore()
  const viewerQuery = useViewerQueryState({
    property_type: '',
    region: '',
    municipality: '',
    year: '',
  })
  const { propertyTypeOptions, regionOptions, municipalityOptions, yearOptions } = useFilterOptions(
    {
      region: computed(() => viewerQuery.state.region),
      labels: {
        allPropertyTypes: 'dashboard.filterAllTypes',
      },
    },
  )

  const dashboardReady = ref(false)
  const workspacesLoading = ref(true)
  const workspacesError = ref('')
  const watchlistLoading = ref(true)
  const watchlistError = ref('')
  const sectionLoading = reactive({
    marketHome: false,
    trend: false,
    transactions: false,
    regions: false,
    municipalities: false,
  })
  const sectionErrors = reactive({
    marketHome: '',
    trend: '',
    transactions: '',
    regions: '',
    municipalities: '',
  })
  let dashboardRequestToken = 0

  interface DashboardMarketHome {
    headline: {
      total_records?: number | null
      earliest_year?: number | string | null
      latest_year?: number | string | null
      median_price?: number | null
      avg_price_per_m2?: number | null
    }
    market_coverage?: {
      present?: number | null
      official_total?: number | null
    }
    property_type_mix?: PropertyTypeMix[]
    year_coverage?: Array<Record<string, unknown>>
  }

  interface DashboardQuickLink {
    id: string
    label: string
    description: string
    to: RouteLocationRaw
    icon: string
    tone?: 'primary' | 'secondary' | 'success'
  }

  interface DashboardWorkspaceLink {
    id: number
    name: string
    subtitle: string
    to: RouteLocationRaw
  }

  interface DashboardFeedLink {
    id: string
    label: string
    summary: string
    trend?: string
    to?: RouteLocationRaw | null
  }

  interface DashboardWorkflowLink {
    id: string
    label: string
    subtitle: string
    to: RouteLocationRaw
  }

  const marketHome = computed<DashboardMarketHome>(
    () =>
      (stats.marketHome as DashboardMarketHome | null) || {
        headline: {},
        market_coverage: {},
        property_type_mix: [],
        year_coverage: [],
      },
  )

  const propertyMix = computed<PropertyTypeMix[]>(() => marketHome.value.property_type_mix || [])
  const latestSales = computed<TransactionRecord[]>(() => stats.transactionsExplorer?.items || [])
  const topRegions = computed<RegionExplorerItem[]>(
    () => stats.regionsExplorer?.items?.slice(0, 5) || [],
  )
  const municipalitySpotlight = computed<MunicipalityExplorerItem | null>(
    () => stats.municipalitiesExplorer?.items?.[0] || null,
  )
  const trendData = computed(() => stats.trend || [])
  const pinnedWorkspaces = computed(() => workbench.pinnedWorkspaces.slice(0, 4))
  const watchlistFeed = computed(() => workbench.watchlistFeed.slice(0, 4))
  const recentWorkflows = computed(() => workbench.recentRoutes.slice(0, 4))
  const dashboardQuickLinks = computed<DashboardQuickLink[]>(() => [
    {
      id: 'market',
      label: t('nav.market'),
      description: t('market.consumerBody'),
      to: { path: '/trg', query: routeQuery({ tab: 'overview' }) },
      icon: 'pi pi-chart-bar',
      tone: 'primary',
    },
    {
      id: 'map',
      label: t('nav.map'),
      description: t('map.explorerBody'),
      to: { path: '/zemljevid', query: routeQuery({ view: 'transactions' }) },
      icon: 'pi pi-compass',
      tone: 'secondary',
    },
    {
      id: 'municipalities',
      label: t('nav.municipalities'),
      description: t('municipalities.consumerBody'),
      to: { path: '/obcine', query: routeQuery({ tab: 'cards' }) },
      icon: 'pi pi-building',
      tone: 'success',
    },
  ])
  const pinnedWorkspaceLinks = computed<DashboardWorkspaceLink[]>(() =>
    pinnedWorkspaces.value.map((item) => ({
      id: item.id,
      name: item.name,
      subtitle: workspacePageLabel(item.page),
      to: workspaceLink(item),
    })),
  )
  const watchlistFeedLinks = computed<DashboardFeedLink[]>(() =>
    watchlistFeed.value.map((item) => ({
      id: item.id,
      label: item.display_label,
      summary: watchlistFeedSummary(item),
      trend: watchlistFeedTrend(item) || undefined,
      to: item.link ? { path: item.link } : null,
    })),
  )
  const recentWorkflowLinks = computed<DashboardWorkflowLink[]>(() =>
    recentWorkflows.value.map((item) => ({
      id: `${item.path}-${item.label}`,
      label: item.label,
      subtitle: recentWorkflowLabel(item),
      to: { path: item.path, query: toLocationQuery(item.query as Record<string, unknown>) },
    })),
  )
  const activeFilterCountValue = computed(() => viewerQuery.activeFilterCount.value)
  const activeFilterTagSeverity = computed(() =>
    activeFilterCountValue.value > 0 ? 'contrast' : 'secondary',
  )
  const activeFilterTagLabel = computed(() =>
    activeFilterCountValue.value > 0
      ? t('dashboard.activeFilterCount', { count: activeFilterCountValue.value })
      : t('dashboard.noActiveFilters'),
  )
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

  function recentWorkflowLabel(item: { path: string; query?: Record<string, unknown> | null }) {
    return describeRoute(item.path, (item.query as Record<string, unknown>) || {})
  }

  function watchlistFeedSummary(item: WatchlistFeedItem) {
    if (item.headline_label && item.headline_value != null) {
      return `${item.headline_label}: ${formatCurrency(item.headline_value)}`
    }
    if (item.headline_label) return item.headline_label
    return t('common.noData')
  }

  function watchlistFeedTrend(item: WatchlistFeedItem) {
    if (item.trend_value == null) return ''
    const value = `${formatNumber(item.trend_value, { maximumFractionDigits: 1 })}%`
    return item.trend_label ? `${item.trend_label}: ${value}` : value
  }

  function normalizeViewerSelection() {
    if (!referenceData.loaded) return

    const currentRegion = viewerQuery.state.region
    const currentMunicipality = viewerQuery.state.municipality
    const municipalityRecord = currentMunicipality
      ? referenceData.municipalities.find((item) => item.municipality === currentMunicipality)
      : null
    const next: Record<string, string> = {}

    if (currentRegion && !referenceData.regions.includes(currentRegion)) {
      next.region = ''
      next.municipality = ''
    }

    if (currentMunicipality && !municipalityRecord) {
      next.municipality = ''
    }

    if (municipalityRecord?.region && municipalityRecord.region !== currentRegion) {
      next.region = municipalityRecord.region
    }

    if (Object.keys(next).length > 0) {
      viewerQuery.patchState(next)
    }
  }

  async function loadWorkspaces() {
    workspacesLoading.value = true
    workspacesError.value = ''
    try {
      await workbench.fetchWorkspaces()
    } catch (error) {
      workspacesError.value = getApiErrorMessage(error, t)
    } finally {
      workspacesLoading.value = false
    }
  }

  async function loadWatchlistFeed() {
    watchlistLoading.value = true
    watchlistError.value = ''
    try {
      await workbench.fetchWatchlistFeed()
    } catch (error) {
      watchlistError.value = getApiErrorMessage(error, t)
    } finally {
      watchlistLoading.value = false
    }
  }

  async function loadSection(
    key: keyof typeof sectionLoading,
    request: (params: Record<string, string | undefined>) => Promise<unknown>,
    params: Record<string, string | undefined>,
    token: number,
  ) {
    if (token !== dashboardRequestToken) return
    sectionLoading[key] = true
    sectionErrors[key] = ''

    try {
      await request(params)
    } catch (error) {
      if (token === dashboardRequestToken) {
        sectionErrors[key] = getApiErrorMessage(error, t)
      }
    } finally {
      if (token === dashboardRequestToken) {
        sectionLoading[key] = false
      }
    }
  }

  async function loadDashboard() {
    const token = ++dashboardRequestToken
    const params = viewerParams()

    await Promise.allSettled([
      loadSection('marketHome', stats.fetchMarketHome, params, token),
      loadSection(
        'trend',
        (requestParams) =>
          stats.fetchTrend({
            property_type: requestParams.property_type,
            region: requestParams.region,
            municipality: requestParams.municipality,
          }),
        params,
        token,
      ),
      loadSection(
        'transactions',
        (requestParams) =>
          stats.fetchTransactionsExplorer({
            ...requestParams,
            page: 1,
            page_size: 6,
            sort: 'recent',
            order: 'desc',
          }),
        params,
        token,
      ),
      loadSection(
        'regions',
        (requestParams) =>
          stats.fetchRegionsExplorer({
            ...requestParams,
            page: 1,
            page_size: 8,
            sort: 'count',
            order: 'desc',
          }),
        params,
        token,
      ),
      loadSection(
        'municipalities',
        (requestParams) =>
          stats.fetchMunicipalitiesExplorer({
            ...requestParams,
            page: 1,
            page_size: 8,
            sort: 'count',
            order: 'desc',
          }),
        params,
        token,
      ),
    ])
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
    void loadWatchlistFeed()
  }

  watch(
    () => [referenceData.loaded, viewerQuery.state.region, viewerQuery.state.municipality],
    () => {
      normalizeViewerSelection()
    },
    { immediate: true },
  )

  watch(
    () => [
      viewerQuery.state.property_type,
      viewerQuery.state.region,
      viewerQuery.state.municipality,
      viewerQuery.state.year,
    ],
    () => {
      if (!dashboardReady.value) return
      void loadDashboard()
    },
  )

  onMounted(async () => {
    await referenceData.ensureLoaded().catch(() => undefined)
    normalizeViewerSelection()
    void loadWorkspaces()
    void loadWatchlistFeed()
    await loadDashboard()
    dashboardReady.value = true
  })
</script>

<template>
  <div class="dashboard-page">
    <section class="hero-shell dashboard-hero">
      <div class="dashboard-hero-copy">
        <PageHeader
          :eyebrow="t('dashboard.consumerKicker')"
          :title="t('dashboard.consumerTitle')"
          :description="t('dashboard.consumerBody')"
        >
          <template #actions>
            <div class="hero-actions">
              <SavedWorkspaceMenu
                page="dashboard"
                :state="{
                  page: 'dashboard',
                  filters: viewerParams(),
                }"
              />
              <Button
                :as="RouterLink"
                :to="{ path: '/trg', query: routeQuery({ tab: 'overview' }) }"
                class="hero-link"
                severity="secondary"
                outlined
                icon="pi pi-chart-bar"
                :label="t('nav.market')"
              />
              <Button
                :as="RouterLink"
                :to="{ path: '/napoved', query: routeQuery() }"
                class="hero-link hero-link--primary"
                icon="pi pi-bolt"
                :label="t('dashboard.quickPrediction')"
              />
            </div>
          </template>
        </PageHeader>

        <div class="hero-status">
          <Tag :severity="activeFilterTagSeverity" :value="activeFilterTagLabel" />
          <span>{{ t('dashboard.marketLens') }}</span>
        </div>
      </div>

      <div class="hero-summary">
        <MetricCard
          v-for="(card, index) in summaryCards"
          :key="card.label"
          :class="{ 'summary-card--feature': index === 0 }"
          :label="card.label"
          :value="card.value"
          :meta="card.meta"
          :tone="card.tone || 'default'"
        />
      </div>
    </section>

    <SectionPanel
      :eyebrow="t('dashboard.activeFilters')"
      :title="t('dashboard.marketLens')"
      compact
    >
      <template #actions>
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
      </template>

      <FilterBar :columns="4">
        <FilterField :label="t('dashboard.filterByType')">
          <Select
            v-model="viewerQuery.state.property_type"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>

        <FilterField :label="t('municipalities.filterByRegion')">
          <Select
            v-model="viewerQuery.state.region"
            :options="regionOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>

        <FilterField :label="t('dashboard.municipality')">
          <Select
            v-model="viewerQuery.state.municipality"
            :options="municipalityOptions"
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
      </FilterBar>
    </SectionPanel>

    <SectionPanel :eyebrow="t('common.explore')" :title="t('dashboard.quickActionsTitle')" compact>
      <DashboardActionGrid :items="dashboardQuickLinks" />
    </SectionPanel>

    <div class="dashboard-grid dashboard-grid--primary">
      <SectionPanel
        class="dashboard-chart-panel"
        :eyebrow="t('dashboard.priceTrend')"
        :title="t('market.trendTitle')"
      >
        <template #actions>
          <Button
            :as="RouterLink"
            :to="{ path: '/trg', query: routeQuery({ tab: 'overview' }) }"
            class="hero-link"
            severity="secondary"
            outlined
            size="small"
            :label="t('market.viewAll')"
            icon="pi pi-arrow-right"
            icon-pos="right"
          />
        </template>

        <LoadingSpinner
          v-if="sectionLoading.trend && !trendData.length"
          :label="t('common.loading')"
        />
        <div
          v-else-if="sectionErrors.trend && !trendData.length"
          class="state-card state-card-stack"
          role="alert"
        >
          <EmptyState icon="pi pi-exclamation-triangle" :message="sectionErrors.trend" />
          <div class="state-card-actions">
            <Button
              icon="pi pi-refresh"
              severity="secondary"
              outlined
              :label="t('common.retry')"
              @click="loadDashboard"
            />
          </div>
        </div>
        <TrendLineChart v-else-if="trendData.length" :data="trendData" compact />
        <EmptyState v-else :message="t('common.noData')" />
      </SectionPanel>

      <SectionPanel
        class="dashboard-spotlight-panel municipality-spotlight"
        :eyebrow="t('dashboard.municipalitySpotlight')"
        :title="municipalitySpotlight?.municipality || t('common.noData')"
      >
        <template #actions>
          <Tag severity="contrast" :value="t('dashboard.marketTableTitle')" />
        </template>

        <LoadingSpinner
          v-if="sectionLoading.municipalities && !municipalitySpotlight"
          :label="t('common.loading')"
        />
        <div
          v-else-if="sectionErrors.municipalities && !municipalitySpotlight"
          class="state-card state-card-stack"
          role="alert"
        >
          <EmptyState icon="pi pi-exclamation-triangle" :message="sectionErrors.municipalities" />
          <div class="state-card-actions">
            <Button
              icon="pi pi-refresh"
              severity="secondary"
              outlined
              :label="t('common.retry')"
              @click="loadDashboard"
            />
          </div>
        </div>
        <template v-else-if="municipalitySpotlight">
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
            <Button
              :as="RouterLink"
              :to="`/obcine/${municipalitySpotlight.slug}`"
              class="hero-link"
              severity="contrast"
              outlined
              icon="pi pi-building"
              :label="t('municipalities.viewDetail')"
            />
            <Button
              :as="RouterLink"
              :to="{
                path: '/trg',
                query: routeQuery({
                  tab: 'transactions',
                  municipality: municipalitySpotlight.municipality,
                }),
              }"
              class="hero-link"
              severity="secondary"
              outlined
              icon="pi pi-table"
              :label="t('market.tabTransactions')"
            />
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
      </SectionPanel>
    </div>

    <div class="dashboard-grid dashboard-grid--secondary">
      <SectionPanel
        class="dashboard-chart-panel"
        :eyebrow="t('dashboard.propertyMix')"
        :title="t('dashboard.propertyMixTitle')"
      >
        <template #actions>
          <Button
            :as="RouterLink"
            :to="{ path: '/trg', query: routeQuery({ tab: 'distribution' }) }"
            class="hero-link"
            severity="secondary"
            outlined
            size="small"
            :label="t('market.viewAll')"
            icon="pi pi-arrow-right"
            icon-pos="right"
          />
        </template>
        <PropertyTypePieChart v-if="propertyMix.length" :items="propertyMix" />
        <EmptyState v-else :message="t('common.noData')" />
      </SectionPanel>

      <SectionPanel
        class="dashboard-table-panel"
        :eyebrow="t('dashboard.regionSnapshot')"
        :title="t('dashboard.regionTableTitle')"
      >
        <template #actions>
          <Button
            :as="RouterLink"
            :to="{ path: '/regije', query: routeQuery({ tab: 'table' }) }"
            class="hero-link"
            severity="secondary"
            outlined
            size="small"
            :label="t('market.viewAll')"
            icon="pi pi-arrow-right"
            icon-pos="right"
          />
        </template>

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
      </SectionPanel>
    </div>

    <SectionPanel
      class="dashboard-workspace-panel"
      :eyebrow="t('workbench.pinnedWorkspaces')"
      :title="t('workbench.resumeWork')"
    >
      <DashboardWorkspaceHub
        :pinned-workspaces="pinnedWorkspaceLinks"
        :watchlist-feed="watchlistFeedLinks"
        :recent-workflows="recentWorkflowLinks"
        :workspaces-loading="workspacesLoading"
        :workspaces-error="workspacesError"
        :watchlist-loading="watchlistLoading"
        :watchlist-error="watchlistError"
        @retry-workspaces="loadWorkspaces"
        @retry-watchlist="loadWatchlistFeed"
      />
    </SectionPanel>

    <SectionPanel :eyebrow="t('dashboard.recentSales')" :title="t('dashboard.latestTransactions')">
      <template #actions>
        <Button
          :as="RouterLink"
          :to="{ path: '/trg', query: routeQuery({ tab: 'transactions' }) }"
          class="hero-link"
          severity="secondary"
          outlined
          size="small"
          :label="t('market.viewAll')"
          icon="pi pi-arrow-right"
          icon-pos="right"
        />
      </template>

      <LoadingSpinner
        v-if="sectionLoading.transactions && !latestSales.length"
        :label="t('common.loading')"
      />
      <div
        v-else-if="sectionErrors.transactions && !latestSales.length"
        class="state-card state-card-stack"
        role="alert"
      >
        <EmptyState icon="pi pi-exclamation-triangle" :message="sectionErrors.transactions" />
        <div class="state-card-actions">
          <Button
            icon="pi pi-refresh"
            severity="secondary"
            outlined
            :label="t('common.retry')"
            @click="loadDashboard"
          />
        </div>
      </div>
      <DataTable
        v-else-if="latestSales.length"
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
          <template #body="{ data }">{{ formatType(data.property_type) }}</template>
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
      <EmptyState v-else :message="t('common.noData')" />
    </SectionPanel>
  </div>
</template>

<style scoped>
  .dashboard-page {
    display: grid;
    gap: var(--space-section);
  }

  .dashboard-hero {
    position: relative;
    display: grid;
    grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
    gap: 1.2rem;
    overflow: hidden;
    padding: clamp(1.1rem, 2vw, 1.55rem);
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--primary) 40%);
    border-radius: calc(var(--radius-md) + 0.4rem);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 18%, transparent),
        transparent 34%
      ),
      radial-gradient(
        circle at bottom left,
        color-mix(in srgb, var(--primary) 10%, transparent),
        transparent 30%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-hero) 90%, var(--primary) 10%),
        var(--surface-panel)
      );
    box-shadow: var(--shadow-sm);
  }

  .dashboard-hero::before,
  .dashboard-hero::after {
    content: '';
    position: absolute;
    inset: auto;
    pointer-events: none;
    border-radius: 999px;
    filter: blur(0.2px);
  }

  .dashboard-hero::before {
    top: -2rem;
    right: 2rem;
    width: 10rem;
    height: 10rem;
    background: color-mix(in srgb, var(--primary) 15%, transparent);
    opacity: 0.9;
  }

  .dashboard-hero::after {
    bottom: -3.5rem;
    left: 35%;
    width: 12rem;
    height: 12rem;
    background: color-mix(in srgb, var(--primary) 8%, transparent);
    opacity: 0.65;
  }

  .dashboard-hero-copy,
  .hero-summary {
    position: relative;
    z-index: 1;
  }

  .dashboard-hero-copy {
    display: grid;
    gap: 1rem;
    align-content: start;
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    width: 100%;
  }

  .hero-actions > * {
    flex: 1 1 11.5rem;
  }

  .hero-status {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.7rem;
    padding: 0.85rem 0.95rem;
    border: 1px solid color-mix(in srgb, var(--border) 62%, var(--primary) 38%);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--surface-card) 90%, var(--primary) 10%);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .hero-status span {
    color: var(--text-muted);
    font-size: 0.86rem;
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  .hero-summary,
  .dashboard-grid,
  .workspace-hub,
  .spotlight-metrics {
    display: grid;
    gap: 0.9rem;
  }

  .hero-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-self: stretch;
  }

  .dashboard-grid {
    align-items: stretch;
  }

  .dashboard-grid--primary {
    grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.82fr);
  }

  .dashboard-grid--secondary {
    grid-template-columns: 1fr;
  }

  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }

  .state-card-actions {
    display: flex;
    justify-content: flex-start;
  }

  .filter-summary {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .municipality-spotlight {
    background: color-mix(in srgb, var(--surface-hero) 88%, var(--primary) 12%);
  }

  .dashboard-spotlight-panel {
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 10%, transparent),
        transparent 38%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-hero) 94%, var(--primary) 6%),
        var(--surface-panel)
      );
  }

  .dashboard-chart-panel {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-panel) 96%, var(--primary) 4%),
        var(--surface-panel)
      ),
      var(--surface-panel);
  }

  .dashboard-table-panel {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-panel) 92%, var(--secondary) 8%),
        var(--surface-panel)
      ),
      var(--surface-panel);
  }

  .dashboard-workspace-panel {
    background: transparent;
    box-shadow: none;
    padding: 0.2rem 0 0;
    border: 0;
  }

  .spotlight-copy {
    margin: 0;
    color: var(--text-muted);
  }

  .spotlight-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .spotlight-metrics div {
    border: 1px solid color-mix(in srgb, var(--border) 68%, var(--primary) 32%);
    border-radius: var(--radius-sm);
    padding: 0.9rem 1rem;
    background: var(--surface-subtle);
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

  .region-ranking {
    display: grid;
    gap: 0.7rem;
  }

  .region-rank-row,
  .hero-link,
  .table-link {
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
    border-radius: var(--radius-sm);
    background: var(--surface-subtle);
    transition:
      transform 0.16s ease,
      border-color 0.16s ease,
      box-shadow 0.16s ease;
  }

  .region-rank-row:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: var(--radius-xs);
    background: color-mix(in srgb, var(--primary) 12%, transparent);
    color: var(--primary);
    font-weight: 800;
  }

  .table-link {
    font-weight: 700;
  }

  .summary-card--feature {
    grid-column: span 2;
    min-height: 8.4rem;
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-panel) 84%, var(--primary) 16%),
        var(--surface-panel)
      ),
      var(--surface-panel);
  }

  .summary-card--feature :deep(.metric-card-value) {
    font-size: clamp(1.45rem, 2.3vw, 2.1rem);
  }

  .summary-card--feature :deep(.metric-card-meta) {
    max-width: 28ch;
  }

  .hero-link--primary {
    box-shadow: 0 18px 30px color-mix(in srgb, var(--primary) 20%, transparent);
  }

  @media (max-width: 1200px) {
    .dashboard-hero,
    .dashboard-grid--primary,
    .dashboard-grid--secondary {
      grid-template-columns: 1fr;
    }

    .summary-card--feature {
      grid-column: auto;
    }
  }

  @media (max-width: 980px) {
    .hero-summary {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .hero-actions {
      flex-direction: column;
    }
  }

  @media (max-width: 720px) {
    .hero-summary,
    .spotlight-metrics {
      grid-template-columns: 1fr;
    }

    .hero-status {
      width: 100%;
    }

    .dashboard-hero :deep(.page-header-actions) {
      width: 100%;
      display: block;
    }

    .dashboard-hero :deep(.page-header-actions > *) {
      width: 100%;
    }

    .dashboard-hero :deep(.page-header-actions .p-button) {
      width: 100%;
    }
  }
</style>
