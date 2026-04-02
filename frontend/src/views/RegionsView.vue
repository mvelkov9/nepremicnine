<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
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
  import PageHeader from '../components/PageHeader.vue'
  import RegionBarChart from '../components/charts/RegionBarChart.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { toLocationQuery } from '../constants/workbench'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import api from '../composables/useApi'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const workbench = useWorkbenchStore()
  const viewerQuery = useViewerQueryState({
    tab: 'overview',
    property_type: '',
    region: '',
    year: '',
    search: '',
  })

  const loading = ref(true)
  const pageError = ref('')
  const chartMetric = ref<'median_price_per_m2' | 'median_price' | 'count'>('median_price_per_m2')
  const regions = ref<any>({ items: [], total: 0, page: 1, page_size: 12 })
  const drilldown = ref<any>({ items: [], total: 0, page: 1, page_size: 12 })
  const allPropertyTypes = ref<string[]>([])
  const yearOptionsSource = ref<string[]>([])

  const tabIndexMap: Record<string, number> = { overview: 0, table: 1, drilldown: 2 }
  const tabNames = ['overview', 'table', 'drilldown']
  const activeTab = computed({
    get: () => tabIndexMap[viewerQuery.state.tab] ?? 0,
    set: (index: number) => viewerQuery.patchState({ tab: tabNames[index] || 'overview' }),
  })

  const propertyTypeOptions = computed(() => [
    { label: t('market.allPropertyTypes'), value: '' },
    ...allPropertyTypes.value.map((value) => ({ label: getPropertyTypeLabel(value, t), value })),
  ])

  const regionOptions = computed(() => [
    { label: t('municipalities.allRegions'), value: '' },
    ...(regions.value.items || []).map((item: any) => ({ label: item.region, value: item.region })),
  ])

  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: '' },
    ...yearOptionsSource.value.map((year) => ({ label: year, value: year })),
  ])

  const highestPriced = computed(
    () =>
      [...(regions.value.items || [])].sort(
        (a: any, b: any) => (b.median_price_per_m2 || 0) - (a.median_price_per_m2 || 0),
      )[0] || null,
  )
  const mostActive = computed(
    () =>
      [...(regions.value.items || [])].sort(
        (a: any, b: any) => (b.count || 0) - (a.count || 0),
      )[0] || null,
  )

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

  async function loadReferences() {
    const [marketRes, trendRes] = await Promise.all([
      api.get('/api/stats/market-home'),
      api.get('/api/stats/trend'),
    ])
    allPropertyTypes.value = (marketRes.data.property_type_mix || []).map(
      (item: any) => item.property_type,
    )
    yearOptionsSource.value = (trendRes.data || []).map((item: any) => String(item.year))
  }

  async function loadDrilldown() {
    if (!viewerQuery.state.region) {
      drilldown.value = { items: [], total: 0, page: 1, page_size: 12 }
      return
    }
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
    drilldown.value = data
  }

  async function loadRegions() {
    loading.value = true
    pageError.value = ''
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
      regions.value = data
      await loadDrilldown()
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
    } finally {
      loading.value = false
    }
  }

  function onRegionsPage(event: any) {
    regions.value.page = event.page + 1
    regions.value.page_size = event.rows
    void loadRegions()
  }

  function onDrillPage(event: any) {
    drilldown.value.page = event.page + 1
    drilldown.value.page_size = event.rows
    void loadDrilldown()
  }

  watch(
    () => [
      viewerQuery.state.property_type,
      viewerQuery.state.region,
      viewerQuery.state.year,
      viewerQuery.state.search,
      chartMetric.value,
    ],
    () => {
      regions.value.page = 1
      drilldown.value.page = 1
      void loadRegions()
    },
  )

  onMounted(async () => {
    try {
      await loadReferences()
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
      loading.value = false
      return
    }
    await loadRegions()
  })
</script>

<template>
  <div class="regions-page">
    <section class="hero-shell">
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
              sort: chartMetric,
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
          <span>{{ t('map.region') }}</span>
          <Select
            v-model="viewerQuery.state.region"
            :options="regionOptions"
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
        <label class="field-inline">
          <span>{{ t('common.search') }}</span>
          <InputText v-model="viewerQuery.state.search" :placeholder="t('common.search')" />
        </label>
      </div>
    </section>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />
    <p v-else-if="pageError" class="state-card error-text">{{ pageError }}</p>

    <TabView v-else v-model:active-index="activeTab">
      <TabPanel value="0" :header="t('common.overview')">
        <section class="tab-content">
          <section class="panel">
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
                :options="[
                  { label: t('regions.medianPricePerM2'), value: 'median_price_per_m2' },
                  { label: t('regions.medianPrice'), value: 'median_price' },
                  { label: t('regions.transactionCount'), value: 'count' },
                ]"
                option-label="label"
                option-value="value"
              />
            </div>
            <RegionBarChart
              v-if="regions.items?.length"
              :regions="regions.items"
              :metric="chartMetric"
            />
            <EmptyState v-else :message="t('common.noData')" />
          </section>
        </section>
      </TabPanel>

      <TabPanel value="1" :header="t('municipalities.tableView')">
        <section class="tab-content">
          <section class="panel">
            <DataTable
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
                    class="link-button"
                    @click="viewerQuery.patchState({ tab: 'drilldown', region: data.region })"
                  >
                    {{ data.region }}
                  </button>
                </template>
              </Column>
              <Column field="municipality_count" :header="t('dashboard.marketMunicipalitiesLabel')">
                <template #body="{ data }">{{ formatNumber(data.municipality_count) }}</template>
              </Column>
              <Column field="count" :header="t('dashboard.transactions')">
                <template #body="{ data }">{{ formatNumber(data.count) }}</template>
              </Column>
              <Column field="median_price" :header="t('dashboard.medianPrice')">
                <template #body="{ data }">{{ formatCurrency(data.median_price) }}</template>
              </Column>
              <Column field="median_price_per_m2" header="€/m²">
                <template #body="{ data }">{{ formatCurrency(data.median_price_per_m2) }}</template>
              </Column>
              <Column :header="t('common.actions')">
                <template #body="{ data }">
                  <div class="row-actions">
                    <Button
                      size="small"
                      severity="secondary"
                      text
                      icon="pi pi-bookmark"
                      @click="addRegionToWatchlist(data.region)"
                    />
                    <Button
                      size="small"
                      severity="secondary"
                      text
                      icon="pi pi-plus-circle"
                      @click="addRegionToCompare(data.region)"
                    />
                  </div>
                </template>
              </Column>
            </DataTable>
          </section>
        </section>
      </TabPanel>

      <TabPanel value="2" :header="t('regions.viewMunicipalities')">
        <section class="tab-content">
          <section class="panel">
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
              <RouterLink
                v-if="viewerQuery.state.region"
                :to="{ path: '/obcine', query: municipalityRouteQuery() }"
                class="hero-link"
              >
                <Tag severity="contrast" :value="t('regions.viewMunicipalities')" />
              </RouterLink>
            </div>
            <DataTable
              v-if="drilldown.items?.length"
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
              <Column field="median_price_per_m2" header="€/m²">
                <template #body="{ data }">{{ formatCurrency(data.median_price_per_m2) }}</template>
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
    </TabView>
  </div>
</template>

<style scoped>
  .regions-page,
  .hero-summary,
  .filter-grid,
  .tab-content {
    display: grid;
    gap: 1rem;
  }
  .regions-page {
    gap: 1.2rem;
  }
  .hero-shell,
  .panel,
  .state-card {
    border: 1px solid var(--border);
    border-radius: 1.6rem;
  }
  .hero-shell,
  .panel {
    background:
      linear-gradient(180deg, var(--surface-soft-subtle), var(--surface-soft)), var(--surface-soft);
    box-shadow: var(--shadow-sm);
    padding: 1.25rem;
  }
  .hero-shell {
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--primary-overlay) 76%, transparent),
        var(--surface-soft)
      ),
      var(--surface-soft);
  }
  .hero-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin-top: 1rem;
  }
  .filter-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
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
  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.85rem;
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
  .hero-link,
  .table-link {
    color: inherit;
    text-decoration: none;
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
  .row-actions {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
  }
  .state-card {
    padding: 1.1rem 1.2rem;
  }
  @media (max-width: 960px) {
    .filter-grid {
      grid-template-columns: 1fr;
    }
    .hero-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
