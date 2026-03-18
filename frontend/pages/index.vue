<script setup lang="ts">
  definePageMeta({ middleware: ['auth'] })

  const { t } = useI18n()
  const stats = useStatsStore()
  const api = useApi()

  const pageError = ref('')
  const selectedPropertyType = ref('')
  const dashboardSearch = ref('')
  const segmentLoading = ref(false)
  const segmentHome = ref<Record<string, any> | null>(null)
  const availablePropertyTypes = ref<string[]>([])

  function fmt(value: any, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value: any) {
    return formatCurrency(value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  }

  function fmtPercent(value: any) {
    return formatPercent(value)
  }

  function propertyTypeLabel(value: unknown) {
    return getPropertyTypeLabel(typeof value === 'string' ? value : '', t)
  }

  async function loadDashboard() {
    pageError.value = ''
    try {
      const marketHomeData = await stats.fetchMarketHome()
      availablePropertyTypes.value = (marketHomeData?.property_type_mix || []).map(
        (item: any) => item.property_type,
      )
    } catch (err: any) {
      pageError.value = getApiErrorMessage(err, t)
    }
  }

  const { pending: loading } = useAsyncData('dashboard', loadDashboard)

  watch(selectedPropertyType, async (nextType) => {
    if (!nextType) {
      segmentHome.value = null
      return
    }
    segmentLoading.value = true
    try {
      const { data } = await api.get('/api/stats/market-home', {
        params: { property_type: nextType },
      })
      segmentHome.value = data as any
    } catch {
      segmentHome.value = null
    } finally {
      segmentLoading.value = false
    }
  })

  const marketHome = computed(
    () =>
      (stats.marketHome as any) || {
        headline: {},
        largest_markets: [],
        price_leaders: [],
        region_snapshot: [],
        latest_sales: [],
        property_type_mix: [],
      },
  )

  const spotlight = computed(() => marketHome.value.largest_markets?.[0] || null)

  const spotlightStats = computed(() => {
    if (!spotlight.value) return []
    return [
      { label: t('map.region'), value: spotlight.value.region || '—' },
      { label: t('dashboard.transactions'), value: fmt(spotlight.value.count) },
      { label: t('dashboard.pricePerM2'), value: fmtCurrency(spotlight.value.median_price_per_m2) },
    ]
  })

  const summaryCards = computed(() => [
    {
      label: t('dashboard.totalRecords'),
      value: fmt(marketHome.value.headline?.total_records),
      meta: t('dashboard.marketCoverageYears', {
        from: marketHome.value.headline?.earliest_year || '—',
        to: marketHome.value.headline?.latest_year || '—',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: fmtCurrency(marketHome.value.headline?.median_price),
      meta: t('dashboard.latestYearLabel', {
        year: marketHome.value.headline?.latest_year || '—',
      }),
    },
    {
      label: t('dashboard.pricePerM2'),
      value: fmtCurrency(marketHome.value.headline?.avg_price_per_m2),
      meta: spotlight.value?.municipality || t('common.noData'),
    },
    {
      label: t('dashboard.marketCoverageLabel'),
      value: `${fmt(marketHome.value.market_coverage?.present)} / ${fmt(marketHome.value.market_coverage?.official_total)}`,
      meta: t('dashboard.marketMunicipalities', {
        count: fmt(marketHome.value.market_coverage?.present),
      }),
    },
  ])

  const propertyTypeOptions = computed(() => [
    { label: t('dashboard.filterAllTypes'), value: '' },
    ...availablePropertyTypes.value.map((v) => ({
      label: propertyTypeLabel(v),
      value: v,
    })),
  ])

  const segmentShare = computed(() => {
    const total = marketHome.value.headline?.total_records || 0
    const segmentTotal = segmentHome.value?.headline?.total_records || 0
    if (!total || !segmentTotal) return null
    return segmentTotal / total
  })

  const segmentCards = computed(() => {
    if (!segmentHome.value) return []
    return [
      {
        label: t('dashboard.totalRecords'),
        value: fmt(segmentHome.value.headline?.total_records),
        meta: t('dashboard.segmentSpotlight'),
      },
      {
        label: t('dashboard.segmentShare'),
        value: segmentShare.value != null ? fmtPercent(segmentShare.value) : '—',
        meta: propertyTypeLabel(selectedPropertyType.value),
      },
      {
        label: t('dashboard.medianPrice'),
        value: fmtCurrency(segmentHome.value.headline?.median_price),
        meta: t('dashboard.marketTableTitle'),
      },
      {
        label: t('dashboard.pricePerM2'),
        value: fmtCurrency(segmentHome.value.headline?.avg_price_per_m2),
        meta: t('dashboard.regionSnapshot'),
      },
    ]
  })

  function mixColor(share: number): 'success' | 'warning' | 'neutral' {
    if (share >= 0.35) return 'success'
    if (share >= 0.15) return 'warning'
    return 'neutral'
  }

  function matchesSearch(...values: unknown[]) {
    const query = dashboardSearch.value.trim().toLowerCase()
    if (!query) return true
    return values.some((v) =>
      String(v || '')
        .toLowerCase()
        .includes(query),
    )
  }

  const largestMarketsRows = computed(() =>
    (marketHome.value.largest_markets || []).filter((item: any) =>
      matchesSearch(item.municipality, item.region),
    ),
  )

  const regionSnapshotRows = computed(() =>
    (marketHome.value.region_snapshot || []).filter((item: any) => matchesSearch(item.region)),
  )

  const latestSalesRows = computed(() =>
    (marketHome.value.latest_sales || []).filter((item: any) =>
      matchesSearch(item.municipality, propertyTypeLabel(item.property_type), item.year),
    ),
  )

  const largestMarketsColumns = computed(() => [
    { accessorKey: 'municipality', header: t('dashboard.municipality') },
    { accessorKey: 'count', header: t('dashboard.transactions') },
    { accessorKey: 'median_price', header: t('dashboard.medianPrice') },
    { accessorKey: 'median_price_per_m2', header: '€/m²' },
  ])

  const regionSnapshotColumns = computed(() => [
    { accessorKey: 'region', header: t('map.region') },
    { accessorKey: 'count', header: t('dashboard.transactions') },
    { accessorKey: 'median_price_per_m2', header: t('dashboard.pricePerM2') },
  ])

  const latestSalesColumns = computed(() => [
    { accessorKey: 'municipality', header: t('dashboard.municipality') },
    { accessorKey: 'property_type', header: t('predict.propertyType') },
    { accessorKey: 'size_m2', header: t('predict.size') },
    { accessorKey: 'price_eur', header: t('dashboard.medianPrice') },
    { accessorKey: 'price_per_m2', header: '€/m²' },
    { accessorKey: 'year', header: t('map.year') },
  ])
</script>

<template>
  <div class="dashboard-page">
    <!-- Hero shell -->
    <section class="hero-shell">
      <div class="hero-main">
        <div class="hero-copy">
          <p class="eyebrow">{{ t('dashboard.consumerKicker') }}</p>
          <h1>{{ t('dashboard.consumerTitle') }}</h1>
          <p class="muted">{{ t('dashboard.consumerBody') }}</p>
          <div class="hero-actions">
            <NuxtLink to="/napoved" class="hero-link">
              <UButton
                icon="i-lucide-bolt"
                :label="t('dashboard.quickPrediction')"
                color="primary"
                size="lg"
              />
            </NuxtLink>
            <NuxtLink to="/zemljevid" class="hero-link">
              <UButton
                icon="i-lucide-map"
                :label="t('dashboard.quickMap')"
                color="neutral"
                variant="outline"
                size="lg"
              />
            </NuxtLink>
            <NuxtLink v-if="spotlight?.slug" :to="`/obcine/${spotlight.slug}`" class="hero-link">
              <UButton
                icon="i-lucide-building-2"
                :label="t('dashboard.municipalitySpotlight')"
                color="neutral"
                variant="ghost"
                size="lg"
              />
            </NuxtLink>
          </div>
        </div>

        <div v-if="spotlight" class="hero-story-card">
          <div class="hero-story-head">
            <div>
              <p class="eyebrow">{{ t('dashboard.municipalitySpotlight') }}</p>
              <h2>{{ spotlight.municipality }}</h2>
              <p class="muted">
                {{
                  t('dashboard.latestYearLabel', { year: marketHome.headline?.latest_year || '—' })
                }}
              </p>
            </div>
            <UBadge :label="spotlight.region || '—'" color="success" variant="soft" />
          </div>

          <div class="hero-story-grid">
            <article v-for="item in spotlightStats" :key="item.label" class="hero-story-stat">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>
        </div>
      </div>

      <div class="hero-summary">
        <KpiCard
          v-for="card in summaryCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
          :meta="card.meta"
        />
      </div>
    </section>

    <!-- Filter shell -->
    <section class="filter-shell">
      <div>
        <p class="eyebrow">{{ t('dashboard.filterByType') }}</p>
        <h2>
          {{
            selectedPropertyType
              ? propertyTypeLabel(selectedPropertyType)
              : t('dashboard.filterAllTypes')
          }}
        </h2>
        <p class="muted">{{ t('dashboard.filterCompareHint') }}</p>
      </div>

      <div class="filter-actions">
        <UInput
          v-model="dashboardSearch"
          :placeholder="t('common.search')"
          icon="i-lucide-search"
        />
        <div class="type-chips">
          <UButton
            v-for="option in propertyTypeOptions"
            :key="option.value"
            size="sm"
            :variant="selectedPropertyType === option.value ? 'solid' : 'outline'"
            :color="selectedPropertyType === option.value ? 'primary' : 'neutral'"
            @click="selectedPropertyType = option.value"
          >
            {{ option.label }}
          </UButton>
        </div>
      </div>
    </section>

    <!-- Loading / error -->
    <div v-if="loading" class="panel state-card">
      <div class="kpi-grid">
        <USkeleton v-for="n in 4" :key="n" class="h-20 w-full rounded-xl" />
      </div>
    </div>
    <UAlert
      v-else-if="pageError"
      :description="pageError"
      color="error"
      variant="soft"
      icon="i-lucide-alert-circle"
    />

    <template v-else>
      <!-- Segment spotlight -->
      <section v-if="selectedPropertyType" class="panel segment-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{{ t('dashboard.segmentSpotlight') }}</p>
            <h2>
              {{
                t('dashboard.segmentSpotlightTitle', {
                  type: propertyTypeLabel(selectedPropertyType),
                })
              }}
            </h2>
            <p class="muted">{{ t('dashboard.segmentTopMarketsTitle') }}</p>
          </div>
        </div>

        <div v-if="segmentLoading" class="kpi-grid">
          <USkeleton v-for="n in 4" :key="n" class="h-20 w-full rounded-xl" />
        </div>

        <template v-else-if="segmentHome">
          <div class="segment-kpi-grid">
            <KpiCard
              v-for="card in segmentCards"
              :key="card.label"
              :label="card.label"
              :value="card.value"
              :meta="card.meta"
            />
          </div>

          <div v-if="segmentHome.largest_markets?.length" class="leader-list">
            <NuxtLink
              v-for="item in segmentHome.largest_markets.slice(0, 4)"
              :key="`${selectedPropertyType}-${item.slug}`"
              :to="`/obcine/${item.slug}`"
              class="leader-row"
            >
              <div>
                <strong>{{ item.municipality }}</strong>
                <p class="muted">{{ item.region || '—' }}</p>
              </div>
              <UBadge
                :label="`${fmt(item.count)} ${t('dashboard.transactions')}`"
                color="success"
                variant="soft"
              />
            </NuxtLink>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </template>
      </section>

      <!-- Largest markets + Region snapshot -->
      <div class="grid-two">
        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">{{ t('dashboard.largestMarkets') }}</p>
              <h2>{{ t('dashboard.marketTableTitle') }}</h2>
            </div>
          </div>
          <div class="table-wrap">
            <UTable :columns="largestMarketsColumns" :data="largestMarketsRows.slice(0, 10)">
              <template #municipality-cell="{ row }">
                <NuxtLink :to="`/obcine/${row.original.slug}`" class="table-link">
                  {{ row.original.municipality }}
                </NuxtLink>
              </template>
              <template #count-cell="{ row }">
                {{ fmt(row.original.count) }}
              </template>
              <template #median_price-cell="{ row }">
                {{ fmtCurrency(row.original.median_price) }}
              </template>
              <template #median_price_per_m2-cell="{ row }">
                {{ fmtCurrency(row.original.median_price_per_m2) }}
              </template>
            </UTable>
            <p
              v-if="!largestMarketsRows.length"
              class="muted"
              style="text-align: center; padding: 2rem"
            >
              {{ t('common.noData') }}
            </p>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">{{ t('dashboard.regionSnapshot') }}</p>
              <h2>{{ t('dashboard.regionTableTitle') }}</h2>
            </div>
          </div>
          <div class="table-wrap">
            <UTable :columns="regionSnapshotColumns" :data="regionSnapshotRows.slice(0, 10)">
              <template #count-cell="{ row }">
                {{ fmt(row.original.count) }}
              </template>
              <template #median_price_per_m2-cell="{ row }">
                {{ fmtCurrency(row.original.median_price_per_m2) }}
              </template>
            </UTable>
            <p
              v-if="!regionSnapshotRows.length"
              class="muted"
              style="text-align: center; padding: 2rem"
            >
              {{ t('common.noData') }}
            </p>
          </div>
        </article>
      </div>

      <!-- Property type mix + Price leaders -->
      <div class="grid-two">
        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">{{ t('dashboard.propertyMix') }}</p>
              <h2>{{ t('dashboard.propertyMixTitle') }}</h2>
            </div>
          </div>
          <div v-if="marketHome.property_type_mix.length" class="mix-list">
            <div
              v-for="item in marketHome.property_type_mix.slice(0, 6)"
              :key="item.property_type"
              class="mix-row"
            >
              <div>
                <strong>{{ propertyTypeLabel(item.property_type) }}</strong>
                <p class="muted">{{ fmt(item.count) }} {{ t('dashboard.transactions') }}</p>
              </div>
              <UBadge
                :label="fmtPercent(item.share)"
                :color="mixColor(item.share)"
                variant="soft"
              />
            </div>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">{{ t('dashboard.priceLeaders') }}</p>
              <h2>{{ t('dashboard.priceLeadersTitle') }}</h2>
            </div>
          </div>
          <div v-if="marketHome.price_leaders.length" class="leader-list">
            <NuxtLink
              v-for="item in marketHome.price_leaders.slice(0, 6)"
              :key="item.slug"
              :to="`/obcine/${item.slug}`"
              class="leader-row"
            >
              <div>
                <strong>{{ item.municipality }}</strong>
                <p class="muted">{{ item.region || '—' }}</p>
              </div>
              <UBadge
                :label="`${fmtCurrency(item.median_price_per_m2)}/m²`"
                color="success"
                variant="soft"
              />
            </NuxtLink>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>
      </div>

      <!-- Latest transactions -->
      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{{ t('dashboard.recentSales') }}</p>
            <h2>{{ t('dashboard.latestTransactions') }}</h2>
          </div>
        </div>
        <div class="table-wrap">
          <UTable :columns="latestSalesColumns" :data="latestSalesRows.slice(0, 12)">
            <template #municipality-cell="{ row }">
              <NuxtLink :to="`/obcine/${row.original.slug}`" class="table-link">
                {{ row.original.municipality }}
              </NuxtLink>
            </template>
            <template #property_type-cell="{ row }">
              {{ propertyTypeLabel(row.original.property_type) }}
            </template>
            <template #size_m2-cell="{ row }"> {{ fmt(row.original.size_m2, 1) }} m² </template>
            <template #price_eur-cell="{ row }">
              {{ fmtCurrency(row.original.price_eur) }}
            </template>
            <template #price_per_m2-cell="{ row }">
              {{ fmtCurrency(row.original.price_per_m2) }}
            </template>
            <template #year-cell="{ row }">
              {{ row.original.year || '—' }}
            </template>
          </UTable>
          <p v-if="!latestSalesRows.length" class="muted" style="text-align: center; padding: 2rem">
            {{ t('common.noData') }}
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .dashboard-page {
    display: grid;
    gap: 1.15rem;
  }

  /* Hero */
  .hero-shell {
    position: relative;
    overflow: hidden;
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
    gap: 1rem;
    padding: 1.3rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 16%, transparent),
        transparent 34%
      ),
      radial-gradient(
        circle at bottom right,
        color-mix(in srgb, var(--secondary) 14%, transparent),
        transparent 28%
      ),
      linear-gradient(135deg, var(--surface-strong), var(--surface-soft));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .hero-shell::after {
    content: '';
    position: absolute;
    inset: auto -8% -28% auto;
    width: 15rem;
    height: 15rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--primary) 10%, transparent);
    filter: blur(18px);
    pointer-events: none;
  }

  .hero-main {
    display: grid;
    gap: 1rem;
    min-width: 0;
  }

  .hero-copy h1 {
    margin: 0.4rem 0 0.5rem;
    font-family: var(--font-display);
    font-size: clamp(2rem, 4vw, 3rem);
    line-height: 1.05;
    max-width: 11ch;
    letter-spacing: -0.04em;
  }

  .hero-copy p {
    max-width: 56ch;
    line-height: 1.7;
    margin: 0;
  }

  .hero-actions {
    margin-top: 1rem;
  }

  .hero-summary {
    display: grid;
    gap: 0.75rem;
    align-content: start;
  }

  .hero-story-card {
    display: grid;
    gap: 0.9rem;
    padding: 1rem 1.05rem;
    border-radius: 1.4rem;
    border: 1px solid color-mix(in srgb, var(--primary) 16%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 90%, transparent),
      color-mix(in srgb, var(--primary) 10%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 30px rgb(15 23 42 / 8%);
  }

  .hero-story-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.8rem;
  }

  .hero-story-head h2 {
    margin: 0.2rem 0 0;
    font-family: var(--font-display);
    font-size: clamp(1.4rem, 2vw, 1.9rem);
    line-height: 1.02;
  }

  .hero-story-head p {
    margin: 0.25rem 0 0;
  }

  .hero-story-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .hero-story-stat {
    display: grid;
    gap: 0.22rem;
    padding: 0.85rem 0.9rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--surface-muted) 82%, transparent)
    );
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 12%);
  }

  .hero-story-stat span {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .hero-story-stat strong {
    font-size: 1rem;
  }

  /* Filter shell */
  .filter-shell {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: end;
    gap: 1rem;
    padding: 1.3rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-strong) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .filter-shell h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.25rem, 1rem + 1.4vw, 1.8rem);
    letter-spacing: -0.04em;
  }

  .filter-actions {
    display: grid;
    gap: 0.85rem;
  }

  .type-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  /* Panels */
  .panel {
    padding: 1.3rem;
  }

  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.85rem;
  }

  .panel-head h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.1rem, 0.9rem + 0.8vw, 1.5rem);
    letter-spacing: -0.03em;
  }

  .segment-panel {
    display: grid;
    gap: 1rem;
  }

  .segment-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1rem;
  }

  /* Lists */
  .leader-list {
    display: grid;
    gap: 0.7rem;
  }
  .mix-list {
    display: grid;
    gap: 0.7rem;
  }

  .leader-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.95rem 1rem;
    border-radius: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 90%, transparent),
      color-mix(in srgb, var(--surface-muted) 85%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 5%);
    color: inherit;
    text-decoration: none;
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease;
  }

  .leader-row:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 28%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 9%, var(--surface-soft)),
      color-mix(in srgb, var(--secondary) 8%, var(--surface-muted))
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 20px 36px rgb(15 23 42 / 10%);
  }

  .leader-row p {
    margin: 0.2rem 0 0;
  }

  .mix-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.95rem 1rem;
    border-radius: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 90%, transparent),
      color-mix(in srgb, var(--surface-muted) 85%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 5%);
  }

  .mix-row p {
    margin: 0.2rem 0 0;
  }

  @media (max-width: 900px) {
    .hero-shell,
    .filter-shell {
      grid-template-columns: 1fr;
    }
    .hero-story-grid,
    .segment-kpi-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 600px) {
    .hero-story-grid,
    .segment-kpi-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
