<script setup lang="ts">
  import { computed, onMounted, ref, watch } from 'vue'
  import { useDebounceFn } from '@vueuse/core'
  import { RouterLink, useRoute } from 'vue-router'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import InputText from 'primevue/inputtext'
  import Paginator from 'primevue/paginator'
  import Select from 'primevue/select'
  import Tab from 'primevue/tab'
  import TabList from 'primevue/tablist'
  import TabPanel from 'primevue/tabpanel'
  import TabPanels from 'primevue/tabpanels'
  import Tabs from 'primevue/tabs'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../components/EmptyState.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import MetricCard from '../components/MetricCard.vue'
  import MunicipalityCard from '../components/MunicipalityCard.vue'
  import FilterBar from '../components/FilterBar.vue'
  import FilterField from '../components/FilterField.vue'
  import PageHeader from '../components/PageHeader.vue'
  import SavedWorkspaceMenu from '../components/workbench/SavedWorkspaceMenu.vue'
  import MunicipalityCompareWorkspace from '../components/municipalities/MunicipalityCompareWorkspace.vue'
  import { buildCanonicalCompareSlots } from '../features/municipalities/compareState'
  import { useFilterOptions } from '../composables/useFilterOptions'
  import { useViewerQueryState } from '../composables/useViewerQueryState'
  import api from '../composables/useApi'
  import { useReferenceDataStore } from '../stores/referenceData'
  import { useWorkbenchStore } from '../stores/workbench'
  import type { ExplorerResponse, MunicipalityExplorerItem } from '../types/api'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber } from '../utils/format'

  type MunicipalitiesQueryState = {
    tab: string
    region: string
    property_type: string
    year: string
    search: string
    sort: string
    compare_a: string
    compare_b: string
    compare_c: string
    page: string
    page_size: string
  }

  interface MunicipalitiesPageEvent {
    page: number
    rows: number
  }

  const { t } = useI18n()
  const route = useRoute()
  const workbench = useWorkbenchStore()
  const referenceData = useReferenceDataStore()
  const viewerQuery = useViewerQueryState<MunicipalitiesQueryState>({
    tab: 'cards',
    region: '',
    property_type: '',
    year: '',
    search: '',
    sort: 'count',
    compare_a: '',
    compare_b: '',
    compare_c: '',
    page: '1',
    page_size: '24',
  })

  const initialized = ref(false)
  const bootstrapLoading = ref(true)
  const bootstrapError = ref('')
  const explorerLoading = ref(false)
  const explorerError = ref('')
  const compareLoading = ref(false)
  const compareError = ref('')
  const filtersRefreshing = computed(() => explorerLoading.value || compareLoading.value)
  const municipalities = ref<ExplorerResponse<MunicipalityExplorerItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 24,
    pages: 0,
    filters: {},
    sort: '',
    order: 'desc',
  })
  const compareRows = ref<MunicipalityExplorerItem[]>([])
  const explorerPageCache = new Map<string, ExplorerResponse<MunicipalityExplorerItem>>()
  const compareRowsCache = new Map<string, MunicipalityExplorerItem[]>()
  const MUNICIPALITIES_CACHE_LIMIT = 40
  let explorerRequestVersion = 0
  let compareRequestVersion = 0
  let lastCompareSignature = ''

  const activeTab = computed({
    get: () => viewerQuery.state.tab || 'cards',
    set: (tab: string) => viewerQuery.patchState({ tab: tab || 'cards' }),
  })

  const selectedRegionRef = computed(() => viewerQuery.state.region || '')
  const { propertyTypeOptions, regionOptions, yearOptions } = useFilterOptions({
    region: selectedRegionRef,
  })

  const sortOptions = computed(() => [
    { label: t('municipalities.sortTransactions'), value: 'count' },
    { label: t('dashboard.medianPrice'), value: 'median_price' },
    { label: t('municipalities.sortPrice'), value: 'median_price_per_m2' },
    { label: t('municipalities.sortName'), value: 'municipality' },
  ])

  const compareOptions = computed(() =>
    referenceData.municipalities
      .map((item) => item.municipality)
      .filter((value, index, array) => array.indexOf(value) === index)
      .sort((left, right) => left.localeCompare(right))
      .map((municipality) => ({ label: municipality, value: municipality })),
  )

  const explorerPage = computed(() =>
    Math.max(Number.parseInt(viewerQuery.state.page || '1', 10) || 1, 1),
  )
  const explorerPageSize = computed(() =>
    Math.max(Number.parseInt(viewerQuery.state.page_size || '24', 10) || 24, 1),
  )

  const topMarket = computed(() => municipalities.value.items?.[0] || null)
  const highestPrice = computed(
    () =>
      [...(municipalities.value.items || [])].sort(
        (a, b) => (b.median_price_per_m2 || 0) - (a.median_price_per_m2 || 0),
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

  function emptyMunicipalitiesPage(): ExplorerResponse<MunicipalityExplorerItem> {
    return {
      items: [],
      total: 0,
      page: explorerPage.value,
      page_size: explorerPageSize.value,
      pages: 0,
      filters: {},
      sort: viewerQuery.state.sort || 'count',
      order: viewerQuery.state.sort === 'municipality' ? 'asc' : 'desc',
    }
  }

  function rememberMunicipalitiesCache<T>(cache: Map<string, T>, cacheKey: string, payload: T) {
    cache.delete(cacheKey)
    cache.set(cacheKey, payload)

    while (cache.size > MUNICIPALITIES_CACHE_LIMIT) {
      const oldestKey = cache.keys().next().value
      if (!oldestKey) break
      cache.delete(oldestKey)
    }
  }

  function explorerCacheKey() {
    return JSON.stringify({
      region: viewerQuery.state.region || '',
      property_type: viewerQuery.state.property_type || '',
      year: viewerQuery.state.year || '',
      search: viewerQuery.state.search || '',
      sort: viewerQuery.state.sort || 'count',
      page: explorerPage.value,
      page_size: explorerPageSize.value,
    })
  }

  function compareCacheKey() {
    return JSON.stringify({
      compare_a: viewerQuery.state.compare_a || '',
      compare_b: viewerQuery.state.compare_b || '',
      compare_c: viewerQuery.state.compare_c || '',
      property_type: viewerQuery.state.property_type || '',
      year: viewerQuery.state.year || '',
    })
  }

  function filters() {
    return {
      region: viewerQuery.state.region || undefined,
      property_type: viewerQuery.state.property_type || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
      sort: viewerQuery.state.sort || 'count',
      page: viewerQuery.state.page || '1',
      page_size: viewerQuery.state.page_size || '24',
      compare_a: viewerQuery.state.compare_a || undefined,
      compare_b: viewerQuery.state.compare_b || undefined,
      compare_c: viewerQuery.state.compare_c || undefined,
    }
  }

  function explorerParams() {
    return {
      region: viewerQuery.state.region || undefined,
      property_type: viewerQuery.state.property_type || undefined,
      year: viewerQuery.state.year || undefined,
      search: viewerQuery.state.search || undefined,
      sort: viewerQuery.state.sort || 'count',
      order: viewerQuery.state.sort === 'municipality' ? 'asc' : 'desc',
      page: explorerPage.value,
      page_size: explorerPageSize.value,
    }
  }

  function compareTargets() {
    return [
      viewerQuery.state.compare_a,
      viewerQuery.state.compare_b,
      viewerQuery.state.compare_c,
    ].filter(Boolean)
  }

  async function addMunicipalityToWatchlist(item: MunicipalityExplorerItem) {
    await workbench.addWatchlistItem({
      entity_type: 'municipality',
      entity_key: item.slug,
      display_label: item.municipality,
      metadata: { link: `/obcine/${item.slug}`, region: item.region },
    })
  }

  function addMunicipalityToCompareTray(item: MunicipalityExplorerItem) {
    workbench.addCompareItem({
      id: `municipality:${item.slug}`,
      entity_type: 'municipality',
      label: item.municipality,
      slug: item.slug,
      region: item.region,
      metadata: { source: 'municipalities' },
    })
  }

  function normalizeQueryState() {
    const validMunicipalityNames = referenceData.municipalities.map((item) => item.municipality)
    const validMunicipalities = new Set(validMunicipalityNames)
    const canonicalCompareSlots = buildCanonicalCompareSlots(route.query, validMunicipalityNames)
    const nextCompareSlots = [
      canonicalCompareSlots.compareA || viewerQuery.state.compare_a,
      canonicalCompareSlots.compareB || viewerQuery.state.compare_b,
      canonicalCompareSlots.compareC || viewerQuery.state.compare_c,
    ].filter(
      (value, index, array) => array.indexOf(value) === index && validMunicipalities.has(value),
    )
    const patch: Partial<MunicipalitiesQueryState> = {}

    if (viewerQuery.state.region && !referenceData.regions.includes(viewerQuery.state.region)) {
      patch.region = ''
    }

    if (
      viewerQuery.state.property_type &&
      !referenceData.propertyTypes.includes(viewerQuery.state.property_type)
    ) {
      patch.property_type = ''
    }

    if (viewerQuery.state.year && !referenceData.years.includes(viewerQuery.state.year)) {
      patch.year = ''
    }

    if (!sortOptions.value.some((item) => item.value === viewerQuery.state.sort)) {
      patch.sort = 'count'
    }

    ;(['compare_a', 'compare_b', 'compare_c'] as const).forEach((key, index) => {
      patch[key] = nextCompareSlots[index] || ''
    })

    if (
      Object.entries(patch).some(
        ([key, value]) => viewerQuery.state[key as keyof MunicipalitiesQueryState] !== value,
      )
    ) {
      void viewerQuery.patchState(patch)
    }
  }

  async function loadMunicipalities() {
    const requestVersion = ++explorerRequestVersion
    const cacheKey = explorerCacheKey()
    const cached = explorerPageCache.get(cacheKey)

    if (cached) {
      explorerError.value = ''
      municipalities.value = cached
      explorerLoading.value = false
      return
    }

    explorerLoading.value = true
    explorerError.value = ''

    try {
      const { data } = await api.get('/api/stats/municipalities', {
        params: explorerParams(),
      })

      if (requestVersion !== explorerRequestVersion) return
      municipalities.value = data
      rememberMunicipalitiesCache(explorerPageCache, cacheKey, data)
    } catch (error) {
      if (requestVersion !== explorerRequestVersion) return
      municipalities.value = emptyMunicipalitiesPage()
      explorerError.value = getApiErrorMessage(error, t)
    } finally {
      if (requestVersion === explorerRequestVersion) {
        explorerLoading.value = false
      }
    }
  }

  async function loadCompareRows() {
    const requestVersion = ++compareRequestVersion
    compareError.value = ''
    const targets = compareTargets()
    const compareSignature = compareCacheKey()

    if (!targets.length) {
      lastCompareSignature = ''
      compareRows.value = []
      compareLoading.value = false
      return
    }

    const cached = compareRowsCache.get(compareSignature)
    if (cached) {
      lastCompareSignature = compareSignature
      compareRows.value = cached
      compareLoading.value = false
      return
    }

    compareLoading.value = true

    if (compareSignature !== lastCompareSignature) {
      compareRows.value = []
    }

    try {
      const rowResults = await Promise.allSettled(
        targets.map(async (municipality) => {
          const { data } = await api.get<ExplorerResponse<MunicipalityExplorerItem>>(
            '/api/stats/municipalities',
            {
              params: {
                property_type: viewerQuery.state.property_type || undefined,
                year: viewerQuery.state.year || undefined,
                municipality,
                page: 1,
                page_size: 1,
                sort: 'count',
                order: 'desc',
              },
            },
          )
          return data.items?.[0] ?? null
        }),
      )

      if (requestVersion !== compareRequestVersion) return
      lastCompareSignature = compareSignature

      const fulfilledRows = rowResults
        .filter(
          (result): result is PromiseFulfilledResult<MunicipalityExplorerItem | null> =>
            result.status === 'fulfilled',
        )
        .map((result) => result.value)
        .filter((row): row is MunicipalityExplorerItem => row !== null)

      compareRows.value = fulfilledRows
      rememberMunicipalitiesCache(compareRowsCache, compareSignature, fulfilledRows)

      const firstRejected = rowResults.find(
        (result): result is PromiseRejectedResult => result.status === 'rejected',
      )

      if (firstRejected) {
        compareError.value = getApiErrorMessage(firstRejected.reason, t)
      }
    } finally {
      if (requestVersion === compareRequestVersion) {
        compareLoading.value = false
      }
    }
  }

  function onPage(event: MunicipalitiesPageEvent) {
    void viewerQuery.patchState({
      page: String(event.page + 1),
      page_size: String(event.rows),
    })
  }

  const debouncedLoadExplorer = useDebounceFn(() => {
    void loadMunicipalities()
  }, 260)

  watch(
    () => [
      viewerQuery.state.region,
      viewerQuery.state.property_type,
      viewerQuery.state.year,
      viewerQuery.state.search,
      viewerQuery.state.sort,
    ],
    () => {
      if (!initialized.value) return
      if (viewerQuery.state.page !== '1') {
        void viewerQuery.patchState({ page: '1' })
        return
      }
      debouncedLoadExplorer()
    },
  )

  watch(
    () => [viewerQuery.state.page, viewerQuery.state.page_size],
    () => {
      if (!initialized.value) return
      void loadMunicipalities()
    },
  )

  watch(
    () => [
      viewerQuery.state.compare_a,
      viewerQuery.state.compare_b,
      viewerQuery.state.compare_c,
      viewerQuery.state.property_type,
      viewerQuery.state.year,
    ],
    () => {
      if (!initialized.value) return
      if (activeTab.value !== 'compare') return
      void loadCompareRows()
    },
  )

  watch(
    () => route.query.compare,
    () => {
      if (!referenceData.loaded) return
      normalizeQueryState()
    },
  )

  async function initializePage() {
    bootstrapLoading.value = true
    bootstrapError.value = ''

    try {
      await referenceData.ensureLoaded()
      normalizeQueryState()
      await Promise.all([
        loadMunicipalities(),
        ...(activeTab.value === 'compare' ? [loadCompareRows()] : []),
      ])
      initialized.value = true
    } catch (error) {
      bootstrapError.value = getApiErrorMessage(error, t)
    } finally {
      bootstrapLoading.value = false
    }
  }

  onMounted(() => {
    void initializePage()
  })

  watch(
    () => activeTab.value,
    (tab) => {
      if (!initialized.value) return
      if (tab === 'compare') {
        void loadCompareRows()
      }
    },
  )
</script>

<template>
  <div class="municipalities-page" :aria-busy="bootstrapLoading && !initialized">
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
      <FilterBar :columns="5">
        <FilterField :label="t('common.search')">
          <InputText
            v-model="viewerQuery.state.search"
            :placeholder="t('municipalities.searchPlaceholder')"
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
        <FilterField :label="t('municipalities.sortBy')">
          <Select
            v-model="viewerQuery.state.sort"
            :options="sortOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>
      </FilterBar>
      <div v-if="filtersRefreshing" class="filter-panel-status" role="status">
        <i class="pi pi-spin pi-spinner" aria-hidden="true"></i>
        {{ t('common.loading') }}
      </div>
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

    <Tabs v-else v-model:value="activeTab" class="municipalities-tabs">
      <TabList>
        <Tab value="cards">{{ t('municipalities.cardView') }}</Tab>
        <Tab value="table">{{ t('municipalities.tableView') }}</Tab>
        <Tab value="compare">{{ t('common.compare') }}</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="cards">
          <section class="tab-content" :aria-busy="explorerLoading">
            <div v-if="explorerError" class="state-card state-card-stack" role="alert">
              <EmptyState icon="pi pi-exclamation-triangle" :message="explorerError" />
              <div class="state-card-actions">
                <Button
                  size="small"
                  severity="secondary"
                  outlined
                  icon="pi pi-refresh"
                  :label="t('common.retry')"
                  @click="loadMunicipalities"
                />
              </div>
            </div>
            <p
              v-else-if="explorerLoading && municipalities.items.length"
              class="muted"
              role="status"
            >
              {{ t('common.loading') }}
            </p>

            <div v-else-if="municipalities.items?.length" class="card-grid">
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
              v-if="!explorerError && municipalities.total > 0"
              :rows="explorerPageSize"
              :first="(explorerPage - 1) * explorerPageSize"
              :total-records="municipalities.total"
              @page="onPage"
            />
          </section>
        </TabPanel>

        <TabPanel value="table">
          <section class="tab-content">
            <section class="panel" :aria-busy="explorerLoading">
              <div v-if="explorerError" class="state-card state-card-stack" role="alert">
                <EmptyState icon="pi pi-exclamation-triangle" :message="explorerError" />
                <div class="state-card-actions">
                  <Button
                    size="small"
                    severity="secondary"
                    outlined
                    icon="pi pi-refresh"
                    :label="t('common.retry')"
                    @click="loadMunicipalities"
                  />
                </div>
              </div>
              <p
                v-else-if="explorerLoading && municipalities.items.length"
                class="muted"
                role="status"
              >
                {{ t('common.loading') }}
              </p>
              <DataTable
                v-else-if="municipalities.items.length"
                :value="municipalities.items"
                lazy
                paginator
                :rows="explorerPageSize"
                :first="(explorerPage - 1) * explorerPageSize"
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
                        :aria-label="`${t('workbench.watch')} - ${data.municipality}`"
                        @click="addMunicipalityToWatchlist(data)"
                      />
                      <Button
                        size="small"
                        severity="secondary"
                        text
                        icon="pi pi-plus-circle"
                        :aria-label="`${t('workbench.compare')} - ${data.municipality}`"
                        @click="addMunicipalityToCompareTray(data)"
                      />
                    </div>
                  </template>
                </Column>
              </DataTable>
              <EmptyState v-else :message="t('municipalities.noResults')" />
            </section>
          </section>
        </TabPanel>

        <TabPanel value="compare">
          <section class="tab-content">
            <MunicipalityCompareWorkspace
              :options="compareOptions"
              :compare-a="viewerQuery.state.compare_a"
              :compare-b="viewerQuery.state.compare_b"
              :compare-c="viewerQuery.state.compare_c"
              :rows="compareRows"
              :loading="compareLoading"
              :error="compareError"
              @update:compare-a="viewerQuery.patchState({ compare_a: $event })"
              @update:compare-b="viewerQuery.patchState({ compare_b: $event })"
              @update:compare-c="viewerQuery.patchState({ compare_c: $event })"
              @retry="loadCompareRows"
            />
          </section>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
  .municipalities-page {
    display: grid;
    gap: clamp(1.25rem, 2vw, 1.75rem);
    animation: municipalities-in 420ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .hero-summary,
  .tab-content {
    display: grid;
    gap: 1rem;
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

  .municipalities-tabs {
    display: grid;
    gap: 1.15rem;
  }

  .municipalities-tabs :deep(.p-tablist) {
    padding: 0.34rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 70%, var(--primary) 30%);
    background: color-mix(in srgb, var(--surface-strong) 90%, var(--primary-overlay) 10%);
    box-shadow: 0 10px 20px color-mix(in srgb, var(--shadow-color) 8%, transparent);
  }

  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: 1rem;
  }

  .card-grid > * {
    min-width: 0;
  }

  .table-link {
    color: var(--link);
    font-weight: 700;
    text-decoration-color: color-mix(in srgb, var(--link) 55%, transparent);
    text-underline-offset: 0.16em;
    text-decoration-thickness: 0.09em;
  }

  .row-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .panel {
    border: 1px solid color-mix(in srgb, var(--border) 66%, var(--content-border-strong) 34%);
    border-radius: clamp(1rem, 1.6vw, 1.35rem);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--surface-panel-strong) 90%, transparent),
        transparent 38%
      ),
      var(--surface-panel);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 16px 34px color-mix(in srgb, rgb(2 6 23) 6%, transparent);
    padding: clamp(1rem, 1.8vw, 1.25rem);
    transition:
      border-color 170ms ease,
      box-shadow 170ms ease,
      transform 170ms ease;
  }

  .panel:hover {
    border-color: color-mix(in srgb, var(--border) 56%, var(--primary) 44%);
    box-shadow:
      inset 0 1px 0 var(--content-glow),
      0 24px 46px color-mix(in srgb, rgb(2 6 23) 10%, transparent);
    transform: translateY(-1px);
  }

  .filter-panel-status {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    margin-top: 0.85rem;
    padding: 0.4rem 0.7rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--surface-soft) 78%, var(--primary) 22%);
    color: var(--text);
    font-size: var(--text-xs);
    font-weight: 700;
  }

  @keyframes municipalities-in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @media (max-width: 1100px) {
    .hero-summary {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 720px) {
    .hero-summary,
    .card-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .municipalities-page {
      animation: none;
    }

    .panel {
      transition: none;
    }

    .panel:hover {
      transform: none;
    }
  }
</style>
