<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { RouterLink } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import InputText from 'primevue/inputtext'
  import Paginator from 'primevue/paginator'
  import Select from 'primevue/select'
  import TabPanel from 'primevue/tabpanel'
  import TabView from 'primevue/tabview'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import MunicipalityCard from '../components/MunicipalityCard.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import api from '../composables/useApi'
  import { useWorkbenchStore } from '../stores/workbench'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const workbench = useWorkbenchStore()
  const viewerQuery = useViewerQueryState({
    tab: 'cards',
    region: '',
    property_type: '',
    year: '',
    search: '',
    sort: 'count',
    compare_a: '',
    compare_b: '',
    compare_c: '',
  })

  const loading = ref(true)
  const pageError = ref('')
  const allMunicipalities = ref<Array<{ municipality: string; region?: string }>>([])
  const propertyTypes = ref<string[]>([])
  const yearOptionsSource = ref<string[]>([])
  const municipalities = ref<any>({ items: [], total: 0, page: 1, page_size: 24 })
  const compareRows = ref<any[]>([])

  const tabIndexMap: Record<string, number> = { cards: 0, table: 1, compare: 2 }
  const tabNames = ['cards', 'table', 'compare']
  const activeTab = computed({
    get: () => tabIndexMap[viewerQuery.state.tab] ?? 0,
    set: (index: number) => viewerQuery.patchState({ tab: tabNames[index] || 'cards' }),
  })

  const regionOptions = computed(() => {
    const regions = [...new Set(allMunicipalities.value.map((item) => item.region).filter(Boolean))]
    return [{ label: t('municipalities.allRegions'), value: '' }].concat(
      regions.sort().map((region) => ({ label: region as string, value: region as string })),
    )
  })

  const propertyTypeOptions = computed(() => [
    { label: t('market.allPropertyTypes'), value: '' },
    ...propertyTypes.value.map((value) => ({ label: getPropertyTypeLabel(value, t), value })),
  ])

  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: '' },
    ...yearOptionsSource.value.map((year) => ({ label: year, value: year })),
  ])

  const sortOptions = computed(() => [
    { label: t('municipalities.sortTransactions'), value: 'count' },
    { label: t('municipalities.sortPrice'), value: 'median_price_per_m2' },
    { label: t('municipalities.sortName'), value: 'municipality' },
  ])

  const compareOptions = computed(() =>
    allMunicipalities.value
      .filter((item) => !viewerQuery.state.region || item.region === viewerQuery.state.region)
      .map((item) => ({ label: item.municipality, value: item.municipality })),
  )

  const topMarket = computed(() => municipalities.value.items?.[0] || null)
  const highestPrice = computed(
    () =>
      [...(municipalities.value.items || [])].sort(
        (a: any, b: any) => (b.median_price_per_m2 || 0) - (a.median_price_per_m2 || 0),
      )[0] || null,
  )

  const summaryCards = computed(() => [
    {
      label: t('dashboard.marketMunicipalitiesLabel'),
      value: formatNumber(municipalities.value.total),
      meta: t('municipalities.pageDescription'),
    },
    {
      label: t('regions.mostActive'),
      value: topMarket.value?.municipality || '-',
      meta: topMarket.value
        ? `${formatNumber(topMarket.value.count)} ${t('dashboard.transactions')}`
        : '-',
      tone: 'warning',
    },
    {
      label: t('regions.highestPriced'),
      value: highestPrice.value?.municipality || '-',
      meta: highestPrice.value
        ? `${formatCurrency(highestPrice.value.median_price_per_m2)}/m²`
        : '-',
      tone: 'success',
    },
  ])

  function filters() {
    return {
      region: viewerQuery.state.region || undefined,
      property_type: viewerQuery.state.property_type || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
      sort: viewerQuery.state.sort || 'count',
      order: viewerQuery.state.sort === 'municipality' ? 'asc' : 'desc',
    }
  }

  async function addMunicipalityToWatchlist(item: any) {
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: item.slug,
      display_label: item.municipality,
      metadata: { link: `/obcine/${item.slug}`, region: item.region },
    })
  }

  function addMunicipalityToCompareTray(item: any) {
    workbench.addCompareItem({
      id: `municipality:${item.slug}`,
      entity_type: 'municipality',
      label: item.municipality,
      slug: item.slug,
      region: item.region,
      metadata: { source: 'municipalities' },
    })
  }

  async function loadReferences() {
    const [municipalityRes, marketRes, trendRes] = await Promise.all([
      api.get('/api/regions/municipalities'),
      api.get('/api/stats/market-home'),
      api.get('/api/stats/trend'),
    ])
    allMunicipalities.value = municipalityRes.data || []
    propertyTypes.value = (marketRes.data.property_type_mix || []).map(
      (item: any) => item.property_type,
    )
    yearOptionsSource.value = (trendRes.data || []).map((item: any) => String(item.year))
  }

  async function loadMunicipalities() {
    const { data } = await api.get('/api/stats/municipalities', {
      params: {
        ...filters(),
        page: municipalities.value.page,
        page_size: municipalities.value.page_size,
      },
    })
    municipalities.value = data
  }

  async function loadCompareRows() {
    const targets = [
      viewerQuery.state.compare_a,
      viewerQuery.state.compare_b,
      viewerQuery.state.compare_c,
    ].filter(Boolean)
    if (!targets.length) {
      compareRows.value = []
      return
    }
    const rows = await Promise.all(
      targets.map(async (municipality) => {
        const { data } = await api.get('/api/stats/municipalities', {
          params: {
            region: viewerQuery.state.region || undefined,
            property_type: viewerQuery.state.property_type || undefined,
            year: viewerQuery.state.year || undefined,
            municipality,
            page: 1,
            page_size: 1,
            sort: 'count',
            order: 'desc',
          },
        })
        return data.items?.[0] || null
      }),
    )
    compareRows.value = rows.filter(Boolean)
  }

  async function loadView() {
    loading.value = true
    pageError.value = ''
    try {
      await Promise.all([loadMunicipalities(), loadCompareRows()])
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
    } finally {
      loading.value = false
    }
  }

  function onPage(event: any) {
    municipalities.value.page = event.page + 1
    municipalities.value.page_size = event.rows
    void loadMunicipalities()
  }

  watch(
    () => [
      viewerQuery.state.region,
      viewerQuery.state.property_type,
      viewerQuery.state.year,
      viewerQuery.state.search,
      viewerQuery.state.sort,
      viewerQuery.state.compare_a,
      viewerQuery.state.compare_b,
      viewerQuery.state.compare_c,
    ],
    () => {
      municipalities.value.page = 1
      void loadView()
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
    await loadView()
  })
</script>

<template>
  <div class="municipalities-page">
    <section class="hero-shell">
      <PageHeader
        :eyebrow="t('municipalities.consumerKicker')"
        :title="t('municipalities.consumerTitle')"
        :description="t('municipalities.consumerBody')"
      >
        <template #actions>
          <SavedWorkspaceMenu
            page="municipalities"
            :state="{
              page: 'municipalities',
              filters: filters(),
              tab: viewerQuery.state.tab,
              sort: viewerQuery.state.sort,
            }"
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
          <span>{{ t('common.search') }}</span>
          <InputText
            v-model="viewerQuery.state.search"
            :placeholder="t('municipalities.searchPlaceholder')"
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
        <label class="field-inline">
          <span>{{ t('municipalities.sortBy') }}</span>
          <Select
            v-model="viewerQuery.state.sort"
            :options="sortOptions"
            option-label="label"
            option-value="value"
          />
        </label>
      </div>
    </section>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />
    <p v-else-if="pageError" class="state-card error-text">{{ pageError }}</p>

    <TabView v-else v-model:active-index="activeTab">
      <TabPanel value="0" :header="t('municipalities.cardView')">
        <section class="tab-content">
          <div v-if="municipalities.items?.length" class="card-grid">
            <MunicipalityCard
              v-for="item in municipalities.items"
              :key="item.slug"
              :municipality="item.municipality"
              :slug="item.slug"
              :region="item.region"
              :count="item.count"
              :median-price-per-m2="item.median_price_per_m2"
            />
          </div>
          <EmptyState v-else :message="t('municipalities.noResults')" />
          <Paginator
            :rows="municipalities.page_size"
            :first="(municipalities.page - 1) * municipalities.page_size"
            :total-records="municipalities.total"
            @page="onPage"
          />
        </section>
      </TabPanel>

      <TabPanel value="1" :header="t('municipalities.tableView')">
        <section class="tab-content">
          <section class="panel">
            <DataTable
              :value="municipalities.items"
              lazy
              paginator
              :rows="municipalities.page_size"
              :first="(municipalities.page - 1) * municipalities.page_size"
              :total-records="municipalities.total"
              size="small"
              striped-rows
              responsive-layout="scroll"
              table-style="min-width: 100%"
              @page="onPage"
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
                      @click="addMunicipalityToWatchlist(data)"
                    />
                    <Button
                      size="small"
                      severity="secondary"
                      text
                      icon="pi pi-plus-circle"
                      @click="addMunicipalityToCompareTray(data)"
                    />
                  </div>
                </template>
              </Column>
            </DataTable>
          </section>
        </section>
      </TabPanel>

      <TabPanel value="2" :header="t('common.compare')">
        <section class="tab-content">
          <section class="panel">
            <div class="compare-grid">
              <label class="field-inline">
                <span>{{ t('municipalities.compareFirst') }}</span>
                <Select
                  v-model="viewerQuery.state.compare_a"
                  :options="compareOptions"
                  option-label="label"
                  option-value="value"
                  show-clear
                />
              </label>
              <label class="field-inline">
                <span>{{ t('municipalities.compareSecond') }}</span>
                <Select
                  v-model="viewerQuery.state.compare_b"
                  :options="compareOptions"
                  option-label="label"
                  option-value="value"
                  show-clear
                />
              </label>
              <label class="field-inline">
                <span>{{ t('municipalities.compareThird') }}</span>
                <Select
                  v-model="viewerQuery.state.compare_c"
                  :options="compareOptions"
                  option-label="label"
                  option-value="value"
                  show-clear
                />
              </label>
            </div>
          </section>

          <div v-if="compareRows.length" class="compare-cards">
            <article v-for="item in compareRows" :key="item.slug" class="compare-card">
              <div class="compare-head">
                <div>
                  <strong>{{ item.municipality }}</strong>
                  <p class="muted">{{ item.region || '-' }}</p>
                </div>
                <RouterLink :to="`/obcine/${item.slug}`" class="table-link">
                  {{ t('municipalities.viewDetail') }}
                </RouterLink>
              </div>
              <dl class="compare-metrics">
                <div>
                  <dt>{{ t('dashboard.transactions') }}</dt>
                  <dd>{{ formatNumber(item.count) }}</dd>
                </div>
                <div>
                  <dt>{{ t('dashboard.medianPrice') }}</dt>
                  <dd>{{ formatCurrency(item.median_price) }}</dd>
                </div>
                <div>
                  <dt>{{ t('dashboard.pricePerM2') }}</dt>
                  <dd>{{ formatCurrency(item.median_price_per_m2) }}</dd>
                </div>
              </dl>
            </article>
          </div>
          <EmptyState v-else :message="t('municipalities.comparePrompt')" />
        </section>
      </TabPanel>
    </TabView>
  </div>
</template>

<style scoped>
  .municipalities-page,
  .hero-summary,
  .filter-grid,
  .tab-content,
  .compare-grid,
  .compare-cards,
  .compare-metrics {
    display: grid;
    gap: 1rem;
  }
  .municipalities-page {
    gap: 1.2rem;
  }
  .hero-shell,
  .panel,
  .state-card,
  .compare-card {
    border: 1px solid var(--border);
    border-radius: 1.6rem;
  }
  .hero-shell,
  .panel,
  .compare-card {
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
    grid-template-columns: repeat(5, minmax(0, 1fr));
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
  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 0.85rem;
  }
  .compare-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .compare-cards {
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  }
  .compare-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.85rem;
  }
  .compare-metrics {
    display: grid;
    gap: 0.8rem;
    margin: 0;
  }
  .compare-metrics div {
    display: grid;
    gap: 0.2rem;
  }
  .compare-metrics dt {
    font-size: 0.76rem;
    color: var(--text-soft);
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .compare-metrics dd {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
  }
  .table-link {
    color: inherit;
    text-decoration: none;
    font-weight: 700;
  }
  .row-actions {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
  }
  .state-card {
    padding: 1.1rem 1.2rem;
  }
  @media (max-width: 1100px) {
    .filter-grid,
    .compare-grid {
      grid-template-columns: 1fr;
    }
  }
  @media (max-width: 720px) {
    .hero-summary {
      grid-template-columns: 1fr;
    }
  }
</style>
