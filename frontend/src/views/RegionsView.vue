<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
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
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import FilterBar from '../components/FilterBar.vue'
  import FilterField from '../components/FilterField.vue'
  import MetricCard from '../components/MetricCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import RegionBarChart from '../components/charts/RegionBarChart.vue'
  import RegionInsightPanel from '../features/regions/RegionInsightPanel.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { toLocationQuery } from '../constants/workbench'
  import { useFilterOptions } from '../composables/useFilterOptions'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import api from '../composables/useApi'
  import { useReferenceDataStore } from '../stores/referenceData'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'
  import type { MunicipalityExplorerItem, RegionExplorerItem } from '../types/api'

  type PageEvent = {
    page: number
    rows: number
  }

  interface ExplorerPage<T> {
    items: T[]
    total: number
    page: number
    page_size: number
  }

  const ALLOWED_METRICS = ['median_price_per_m2', 'median_price', 'count'] as const
  type ChartMetric = (typeof ALLOWED_METRICS)[number]

  const { t } = useI18n()
  const workbench = useWorkbenchStore()
  const referenceData = useReferenceDataStore()
  const viewerQuery = useViewerQueryState({
    tab: 'overview',
    property_type: '',
    region: '',
    year: '',
    search: '',
    sort: 'median_price_per_m2',
  })

  const initialized = ref(false)
  const bootstrapLoading = ref(true)
  const bootstrapError = ref('')
  const regionsLoading = ref(false)
  const regionsError = ref('')
  const drilldownLoading = ref(false)
  const drilldownError = ref('')
  const regions = ref<ExplorerPage<RegionExplorerItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 12,
  })
  const drilldown = ref<ExplorerPage<MunicipalityExplorerItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 12,
  })
  let regionsRequestVersion = 0
  let drilldownRequestVersion = 0

  const activeTab = computed({
    get: () =>
      ['overview', 'table', 'drilldown'].includes(viewerQuery.state.tab)
        ? viewerQuery.state.tab
        : 'overview',
    set: (tab: string) => viewerQuery.patchState({ tab: tab || 'overview' }),
  })

  const selectedRegionRef = computed(() => viewerQuery.state.region || '')
  const { propertyTypeOptions, regionOptions, yearOptions } = useFilterOptions({
    region: selectedRegionRef,
  })

  const chartMetric = computed<ChartMetric>({
    get: () =>
      ALLOWED_METRICS.includes(viewerQuery.state.sort as ChartMetric)
        ? (viewerQuery.state.sort as ChartMetric)
        : 'median_price_per_m2',
    set: (value) => {
      void viewerQuery.patchState({ sort: value })
    },
  })

  const chartMetricOptions = computed(() => [
    { label: t('regions.medianPricePerM2'), value: 'median_price_per_m2' },
    { label: t('regions.medianPrice'), value: 'median_price' },
    { label: t('regions.transactionCount'), value: 'count' },
  ])

  const highestPriced = computed(() => {
    const items = regions.value.items || []
    return (
      [...items].sort(
        (left, right) => (right.median_price_per_m2 || 0) - (left.median_price_per_m2 || 0),
      )[0] || null
    )
  })

  const mostActive = computed(() => {
    const items = regions.value.items || []
    return [...items].sort((left, right) => (right.count || 0) - (left.count || 0))[0] || null
  })

  const selectedRegionStats = computed(() => {
    if (viewerQuery.state.region) {
      return (
        (regions.value.items || []).find((item) => item.region === viewerQuery.state.region) || null
      )
    }
    return mostActive.value || highestPriced.value || null
  })

  const summaryCards = computed(() => [
    {
      label: t('regions.totalRegions'),
      value: formatNumber(regions.value.total || regions.value.items?.length || 0),
      meta: t('regions.pageDescription'),
    },
    {
      label: t('regions.highestPriced'),
      value: highestPriced.value?.region || '-',
      meta: highestPriced.value
        ? `${formatCurrency(highestPriced.value.median_price_per_m2)}/m²`
        : '-',
      tone: 'success',
    },
    {
      label: t('regions.mostActive'),
      value: mostActive.value?.region || '-',
      meta: mostActive.value
        ? `${formatNumber(mostActive.value.count)} ${t('dashboard.transactions')}`
        : '-',
      tone: 'warning',
    },
  ])

  function emptyRegionsPage(
    page = regions.value.page,
    pageSize = regions.value.page_size,
  ): ExplorerPage<RegionExplorerItem> {
    return {
      items: [],
      total: 0,
      page,
      page_size: pageSize,
    }
  }

  function emptyDrilldownPage(
    page = drilldown.value.page,
    pageSize = drilldown.value.page_size,
  ): ExplorerPage<MunicipalityExplorerItem> {
    return {
      items: [],
      total: 0,
      page,
      page_size: pageSize,
    }
  }

  function filters() {
    return {
      property_type: viewerQuery.state.property_type || undefined,
      region: viewerQuery.state.region || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
    }
  }

  function municipalityRouteQuery() {
    return toLocationQuery({
      tab: 'table',
      region: viewerQuery.state.region || undefined,
      property_type: viewerQuery.state.property_type || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
    })
  }

  async function addRegionToWatchlist(region: string) {
    await workbench.addWatchlistItem({
      entity_type: 'region',
      entity_key: region,
      display_label: region,
      metadata: {
        link: `/regije?tab=drilldown&region=${encodeURIComponent(region)}`,
      },
    })
  }

  function addRegionToCompare(region: string) {
    workbench.addCompareItem({
      id: `region:${region}`,
      entity_type: 'region',
      label: region,
      metadata: { source: 'regions' },
    })
  }

  function normalizeQueryState() {
    const patch: Record<string, string> = {}

    if (
      viewerQuery.state.property_type &&
      !referenceData.propertyTypes.includes(viewerQuery.state.property_type)
    ) {
      patch.property_type = ''
    }

    if (viewerQuery.state.region && !referenceData.regions.includes(viewerQuery.state.region)) {
      patch.region = ''
    }

    if (viewerQuery.state.year && !referenceData.years.includes(viewerQuery.state.year)) {
      patch.year = ''
    }

    if (!ALLOWED_METRICS.includes(viewerQuery.state.sort as ChartMetric)) {
      patch.sort = 'median_price_per_m2'
    }

    if (Object.keys(patch).length) {
      void viewerQuery.patchState(patch)
    }
  }

  async function loadRegions() {
    const requestVersion = ++regionsRequestVersion
    regionsLoading.value = true
    regionsError.value = ''

    try {
      const { data } = await api.get('/api/stats/regions-explorer', {
        params: {
          ...filters(),
          page: regions.value.page,
          page_size: regions.value.page_size,
          sort: chartMetric.value,
          order: 'desc',
        },
      })

      if (requestVersion !== regionsRequestVersion) return
      regions.value = data
    } catch (error) {
      if (requestVersion !== regionsRequestVersion) return
      regions.value = emptyRegionsPage()
      regionsError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === regionsRequestVersion) {
        regionsLoading.value = false
      }
    }
  }

  async function loadDrilldown() {
    const requestVersion = ++drilldownRequestVersion
    drilldownLoading.value = true
    drilldownError.value = ''

    if (!viewerQuery.state.region) {
      drilldown.value = { items: [], total: 0, page: 1, page_size: drilldown.value.page_size }
      drilldownLoading.value = false
      return
    }

    try {
      const { data } = await api.get('/api/stats/municipalities', {
        params: {
          property_type: viewerQuery.state.property_type || undefined,
          region: viewerQuery.state.region,
          year: viewerQuery.state.year || undefined,
          search: viewerQuery.state.search || undefined,
          page: drilldown.value.page,
          page_size: drilldown.value.page_size,
          sort: 'count',
          order: 'desc',
        },
      })

      if (requestVersion !== drilldownRequestVersion) return
      drilldown.value = data
    } catch (error) {
      if (requestVersion !== drilldownRequestVersion) return
      drilldown.value = emptyDrilldownPage()
      drilldownError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === drilldownRequestVersion) {
        drilldownLoading.value = false
      }
    }
  }

  function onRegionsPage(event: PageEvent) {
    regions.value.page = event.page + 1
    regions.value.page_size = event.rows
    void loadRegions()
  }

  function onDrillPage(event: PageEvent) {
    drilldown.value.page = event.page + 1
    drilldown.value.page_size = event.rows
    void loadDrilldown()
  }

  async function initializePage() {
    bootstrapLoading.value = true
    bootstrapError.value = ''

    try {
      await referenceData.ensureLoaded()
      normalizeQueryState()
      await Promise.all([loadRegions(), loadDrilldown()])
      initialized.value = true
    } catch (error) {
      bootstrapError.value = getApiErrorMessage(error, t)
    } finally {
      bootstrapLoading.value = false
    }
  }

  watch(
    () => [
      viewerQuery.state.property_type,
      viewerQuery.state.region,
      viewerQuery.state.year,
      viewerQuery.state.search,
      viewerQuery.state.sort,
    ],
    () => {
      if (!initialized.value) return
      regions.value.page = 1
      drilldown.value.page = 1
      void loadRegions()
      void loadDrilldown()
    },
  )

  onMounted(() => {
    void initializePage()
  })
</script>

<template>
  <div class="regions-page">
    <section class="hero-shell">
      <div class="hero-copy">
        <PageHeader
          :eyebrow="t('regions.consumerKicker')"
          :title="t('regions.consumerTitle')"
          :description="t('regions.consumerBody')"
        >
          <template #actions>
            <SavedWorkspaceMenu
              page="regions"
              :state="{
                page: 'regions',
                filters: filters(),
                tab: viewerQuery.state.tab,
                sort: viewerQuery.state.sort,
              }"
            />
            <Button
              v-if="viewerQuery.state.region"
              severity="secondary"
              text
              icon="pi pi-bookmark"
              :label="t('workbench.watch')"
              @click="addRegionToWatchlist(viewerQuery.state.region)"
            />
          </template>
        </PageHeader>
        <p class="hero-note">
          {{
            viewerQuery.state.region
              ? `${t('regions.drillDown', { region: viewerQuery.state.region })} ${t('regions.consumerBody')}`
              : t('regions.pageDescription')
          }}
        </p>
      </div>

      <RegionInsightPanel
        :eyebrow="t('common.overview')"
        :title="selectedRegionStats?.region || t('regions.pageTitle')"
        :description="
          selectedRegionStats ? t('regions.pageDescription') : t('regions.selectRegionPrompt')
        "
        :tag-label="
          viewerQuery.state.region ? t('regions.viewMunicipalities') : t('regions.mostActive')
        "
        :stats="
          selectedRegionStats
            ? [
                {
                  label: t('dashboard.transactions'),
                  value: formatNumber(selectedRegionStats.count),
                },
                {
                  label: t('dashboard.marketMunicipalitiesLabel'),
                  value: formatNumber(selectedRegionStats.municipality_count || 0),
                },
                {
                  label: t('dashboard.pricePerM2'),
                  value: `${formatCurrency(selectedRegionStats.median_price_per_m2)}/m²`,
                },
              ]
            : []
        "
        :empty-message="t('common.noData')"
        :busy="regionsLoading"
      >
        <template #actions>
          <Button
            severity="secondary"
            outlined
            icon="pi pi-table"
            :label="t('regions.viewMunicipalities')"
            @click="
              viewerQuery.patchState({
                tab: 'drilldown',
                region: selectedRegionStats?.region || '',
              })
            "
          />
          <Button
            v-if="selectedRegionStats?.region"
            severity="secondary"
            text
            icon="pi pi-plus-circle"
            :label="t('workbench.compare')"
            @click="addRegionToCompare(selectedRegionStats.region)"
          />
        </template>
      </RegionInsightPanel>

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
      <FilterBar :columns="4">
        <FilterField :label="t('market.selectPropertyType')">
          <Select
            v-model="viewerQuery.state.property_type"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>
        <FilterField :label="t('map.region')">
          <Select
            v-model="viewerQuery.state.region"
            :options="regionOptions"
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
    </section>

    <LoadingSpinner v-if="bootstrapLoading && !initialized" :label="t('common.loading')" />
    <div
      v-else-if="bootstrapError && !initialized"
      class="state-card state-card-stack"
      role="alert"
    >
      <EmptyState icon="pi pi-exclamation-triangle" :message="bootstrapError" />
      <div class="state-card-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="initializePage"
        />
      </div>
    </div>

    <Tabs v-else v-model:value="activeTab" class="region-tabs">
      <TabList>
        <Tab value="overview">{{ t('common.overview') }}</Tab>
        <Tab value="table">{{ t('municipalities.tableView') }}</Tab>
        <Tab value="drilldown">{{ t('regions.viewMunicipalities') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="overview">
          <section class="tab-content">
            <section class="regions-overview-grid">
              <section class="panel chart-panel" :aria-busy="regionsLoading">
                <div class="panel-head">
                  <div>
                    <p class="eyebrow subtle">{{ t('regions.consumerKicker') }}</p>
                    <h2>
                      {{
                        t('regions.chartTitle', {
                          metric: t(
                            `regions.${chartMetric === 'count' ? 'transactionCount' : chartMetric === 'median_price' ? 'medianPrice' : 'medianPricePerM2'}`,
                          ),
                        })
                      }}
                    </h2>
                  </div>
                  <Select
                    v-model="chartMetric"
                    :options="chartMetricOptions"
                    option-label="label"
                    option-value="value"
                  />
                </div>

                <p class="panel-copy">
                  {{ t('regions.pageDescription') }}
                </p>

                <div v-if="regionsError" class="state-card state-card-stack" role="alert">
                  <EmptyState icon="pi pi-exclamation-triangle" :message="regionsError" />
                  <div class="state-card-actions">
                    <Button
                      size="small"
                      severity="secondary"
                      outlined
                      icon="pi pi-refresh"
                      :label="t('common.retry')"
                      @click="loadRegions"
                    />
                  </div>
                </div>
                <p v-else-if="regionsLoading && regions.items.length" class="muted" role="status">
                  {{ t('common.loading') }}
                </p>

                <RegionBarChart
                  v-else-if="regions.items?.length"
                  :regions="regions.items"
                  :metric="chartMetric"
                />
                <EmptyState v-else :message="t('common.noData')" />
              </section>

              <RegionInsightPanel
                class="region-spotlight"
                :eyebrow="
                  viewerQuery.state.region
                    ? t('regions.drillDown', { region: viewerQuery.state.region })
                    : t('regions.pageTitle')
                "
                :title="selectedRegionStats?.region || t('regions.pageTitle')"
                :description="
                  selectedRegionStats
                    ? t('regions.pageDescription')
                    : t('regions.selectRegionPrompt')
                "
                :tag-label="
                  viewerQuery.state.region
                    ? t('regions.viewMunicipalities')
                    : t('regions.mostActive')
                "
                :stats="
                  selectedRegionStats
                    ? [
                        {
                          label: t('dashboard.transactions'),
                          value: formatNumber(selectedRegionStats.count),
                        },
                        {
                          label: t('dashboard.marketMunicipalitiesLabel'),
                          value: formatNumber(selectedRegionStats.municipality_count || 0),
                        },
                        {
                          label: t('dashboard.pricePerM2'),
                          value: `${formatCurrency(selectedRegionStats.median_price_per_m2)}/m²`,
                        },
                      ]
                    : []
                "
                :empty-message="t('common.noData')"
                :busy="regionsLoading"
              >
                <template #actions>
                  <Button
                    severity="secondary"
                    outlined
                    icon="pi pi-table"
                    :label="t('regions.viewMunicipalities')"
                    @click="
                      viewerQuery.patchState({
                        tab: 'drilldown',
                        region: selectedRegionStats?.region || '',
                      })
                    "
                  />
                  <Button
                    v-if="selectedRegionStats?.region"
                    severity="secondary"
                    text
                    icon="pi pi-bookmark"
                    :label="t('workbench.watch')"
                    @click="addRegionToWatchlist(selectedRegionStats.region)"
                  />
                  <Button
                    v-if="selectedRegionStats?.region"
                    severity="secondary"
                    text
                    icon="pi pi-plus-circle"
                    :label="t('workbench.compare')"
                    @click="addRegionToCompare(selectedRegionStats.region)"
                  />
                </template>
              </RegionInsightPanel>
            </section>
          </section>
        </TabPanel>

        <TabPanel value="table">
          <section class="tab-content">
            <section class="panel table-panel" :aria-busy="regionsLoading">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">{{ t('municipalities.tableView') }}</p>
                  <h2>{{ t('regions.pageTitle') }}</h2>
                </div>
                <Tag
                  severity="secondary"
                  :value="formatNumber(regions.total || regions.items.length)"
                />
              </div>

              <p class="panel-copy">
                {{ t('regions.pageDescription') }}
              </p>

              <div v-if="regionsError" class="state-card state-card-stack" role="alert">
                <EmptyState icon="pi pi-exclamation-triangle" :message="regionsError" />
                <div class="state-card-actions">
                  <Button
                    size="small"
                    severity="secondary"
                    outlined
                    icon="pi pi-refresh"
                    :label="t('common.retry')"
                    @click="loadRegions"
                  />
                </div>
              </div>
              <p v-else-if="regionsLoading && regions.items.length" class="muted" role="status">
                {{ t('common.loading') }}
              </p>
              <DataTable
                v-else-if="regions.items.length"
                :value="regions.items"
                lazy
                paginator
                :rows="regions.page_size"
                :first="(regions.page - 1) * regions.page_size"
                :total-records="regions.total"
                size="small"
                striped-rows
                responsive-layout="scroll"
                table-style="min-width: 100%"
                @page="onRegionsPage"
              >
                <Column field="region" :header="t('map.region')">
                  <template #body="{ data }">
                    <button
                      type="button"
                      class="link-button"
                      @click="viewerQuery.patchState({ tab: 'drilldown', region: data.region })"
                    >
                      {{ data.region }}
                    </button>
                  </template>
                </Column>
                <Column
                  field="municipality_count"
                  :header="t('dashboard.marketMunicipalitiesLabel')"
                >
                  <template #body="{ data }">{{ formatNumber(data.municipality_count) }}</template>
                </Column>
                <Column field="count" :header="t('dashboard.transactions')">
                  <template #body="{ data }">{{ formatNumber(data.count) }}</template>
                </Column>
                <Column field="median_price" :header="t('dashboard.medianPrice')">
                  <template #body="{ data }">{{ formatCurrency(data.median_price) }}</template>
                </Column>
                <Column field="median_price_per_m2" :header="t('dashboard.pricePerM2')">
                  <template #body="{ data }">
                    {{ formatCurrency(data.median_price_per_m2) }}/m²
                  </template>
                </Column>
                <Column :header="t('common.actions')">
                  <template #body="{ data }">
                    <div class="row-actions">
                      <Button
                        size="small"
                        severity="secondary"
                        text
                        icon="pi pi-bookmark"
                        :aria-label="`${t('workbench.watch')} - ${data.region}`"
                        @click="addRegionToWatchlist(data.region)"
                      />
                      <Button
                        size="small"
                        severity="secondary"
                        text
                        icon="pi pi-plus-circle"
                        :aria-label="`${t('workbench.compare')} - ${data.region}`"
                        @click="addRegionToCompare(data.region)"
                      />
                    </div>
                  </template>
                </Column>
              </DataTable>
              <EmptyState v-else :message="t('common.noData')" />
            </section>
          </section>
        </TabPanel>

        <TabPanel value="drilldown">
          <section class="tab-content">
            <section class="panel drilldown-panel" :aria-busy="drilldownLoading">
              <div class="panel-head">
                <div>
                  <p class="eyebrow subtle">
                    {{
                      t('regions.drillDown', {
                        region: viewerQuery.state.region || t('municipalities.allRegions'),
                      })
                    }}
                  </p>
                  <h2>{{ viewerQuery.state.region || t('regions.pageTitle') }}</h2>
                </div>
                <Button
                  v-if="viewerQuery.state.region"
                  :as="RouterLink"
                  :to="{ path: '/obcine', query: municipalityRouteQuery() }"
                  class="hero-link"
                  severity="contrast"
                  outlined
                  :label="t('regions.viewMunicipalities')"
                />
              </div>

              <p class="panel-copy">
                {{
                  viewerQuery.state.region
                    ? t('regions.pageDescription')
                    : t('regions.selectRegionPrompt')
                }}
              </p>

              <div v-if="drilldownError" class="state-card state-card-stack" role="alert">
                <EmptyState icon="pi pi-exclamation-triangle" :message="drilldownError" />
                <div class="state-card-actions">
                  <Button
                    size="small"
                    severity="secondary"
                    outlined
                    icon="pi pi-refresh"
                    :label="t('common.retry')"
                    @click="loadDrilldown"
                  />
                </div>
              </div>
              <p v-else-if="drilldownLoading && drilldown.items.length" class="muted" role="status">
                {{ t('common.loading') }}
              </p>

              <DataTable
                v-else-if="drilldown.items?.length"
                :value="drilldown.items"
                lazy
                paginator
                :rows="drilldown.page_size"
                :first="(drilldown.page - 1) * drilldown.page_size"
                :total-records="drilldown.total"
                size="small"
                striped-rows
                responsive-layout="scroll"
                table-style="min-width: 100%"
                @page="onDrillPage"
              >
                <Column field="municipality" :header="t('dashboard.municipality')">
                  <template #body="{ data }">
                    <RouterLink :to="`/obcine/${data.slug}`" class="table-link">
                      {{ data.municipality }}
                    </RouterLink>
                  </template>
                </Column>
                <Column field="count" :header="t('dashboard.transactions')">
                  <template #body="{ data }">{{ formatNumber(data.count) }}</template>
                </Column>
                <Column field="median_price" :header="t('dashboard.medianPrice')">
                  <template #body="{ data }">{{ formatCurrency(data.median_price) }}</template>
                </Column>
                <Column field="median_price_per_m2" :header="t('dashboard.pricePerM2')">
                  <template #body="{ data }">
                    {{ formatCurrency(data.median_price_per_m2) }}/m²
                  </template>
                </Column>
              </DataTable>
              <EmptyState
                v-else
                :message="
                  viewerQuery.state.region ? t('common.noData') : t('regions.selectRegionPrompt')
                "
              />
            </section>
          </section>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
  .regions-page,
  .hero-shell,
  .hero-copy,
  .hero-summary,
  .tab-content,
  .regions-overview-grid,
  .spotlight-metrics {
    display: grid;
    gap: var(--space-grid);
  }

  .regions-page {
    gap: var(--space-section);
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

  .hero-shell {
    grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
    align-items: start;
    padding: clamp(1rem, 2vw, 1.35rem);
    border: 1px solid color-mix(in srgb, var(--border) 64%, var(--primary) 36%);
    border-radius: calc(var(--radius-md) + 0.2rem);
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--primary) 12%, transparent),
        transparent 28%
      ),
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 68%, transparent),
        var(--surface-soft)
      ),
      var(--surface-soft);
    box-shadow: var(--shadow-sm);
  }

  .hero-copy {
    align-content: start;
    padding: 0.2rem 0.35rem 0.2rem 0;
  }

  .hero-note,
  .panel-copy,
  .hero-focus-copy {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.55;
  }

  .hero-summary {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    grid-column: 1 / -1;
  }

  .hero-link,
  .table-link {
    color: inherit;
    text-decoration: none;
  }

  .hero-focus,
  .panel,
  .chart-panel,
  .table-panel,
  .drilldown-panel {
    align-content: start;
  }

  .hero-focus {
    display: grid;
    gap: 0.9rem;
    padding: var(--space-panel);
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-card) 90%, var(--primary) 10%),
        var(--surface-panel)
      ),
      var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  .regions-overview-grid {
    grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.9fr);
  }

  .focus-stats,
  .spotlight-metrics {
    gap: 0.75rem;
  }

  .focus-stat,
  .spotlight-stat {
    display: grid;
    gap: 0.2rem;
    min-width: 0;
    padding: 0.95rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    border-radius: var(--radius-sm);
    background: var(--surface-soft-muted);
  }

  .focus-stat span,
  .spotlight-stat span {
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .focus-stat strong,
  .spotlight-stat strong {
    font-size: 1.1rem;
  }

  .hero-focus-actions,
  .spotlight-actions,
  .row-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .hero-focus-actions {
    margin-top: 0.15rem;
  }

  .spotlight-actions {
    margin-top: 1rem;
  }

  .link-button {
    padding: 0;
    border: 0;
    background: none;
    color: var(--primary);
    font: inherit;
    font-weight: 700;
    cursor: pointer;
  }

  .panel {
    padding: var(--space-panel);
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 90%, transparent),
        transparent 44%
      ),
      var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.9rem;
    flex-wrap: wrap;
  }

  .panel-head h2 {
    margin: 0;
    text-wrap: balance;
  }

  .panel-head.compact {
    align-items: center;
  }

  .region-tabs {
    display: grid;
    gap: var(--space-grid);
  }

  .region-tabs :deep(.p-tablist) {
    gap: 0.35rem;
    padding: 0.35rem;
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--surface-soft) 82%, var(--primary) 18%);
    box-shadow: var(--shadow-sm);
  }

  .region-tabs :deep(.p-tab) {
    flex: 1 1 0;
    justify-content: center;
    min-height: 2.85rem;
    border-radius: calc(var(--radius-sm) + 0.1rem);
    font-weight: 700;
  }

  .region-tabs :deep(.p-tab[aria-selected='true']) {
    background: var(--surface-panel);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  .panel-copy {
    max-width: 68ch;
  }

  .table-panel :deep(.p-datatable),
  .drilldown-panel :deep(.p-datatable) {
    margin-top: 0.35rem;
  }

  @media (max-width: 960px) {
    .hero-shell,
    .regions-overview-grid,
    .hero-summary {
      grid-template-columns: 1fr;
    }

    .hero-shell {
      padding: 1rem;
    }

    .panel-head,
    .panel-head.compact {
      align-items: stretch;
    }

    .region-tabs :deep(.p-tablist) {
      overflow-x: auto;
      overscroll-behavior-x: contain;
    }

    .region-tabs :deep(.p-tab) {
      flex: 0 0 auto;
      white-space: nowrap;
    }

    .spotlight-actions,
    .hero-focus-actions,
    .row-actions {
      flex-direction: column;
      align-items: stretch;
    }

    .spotlight-actions :deep(.p-button),
    .hero-focus-actions :deep(.p-button),
    .row-actions :deep(.p-button) {
      width: 100%;
    }
  }
</style>
