<script setup lang="ts">
  definePageMeta({ middleware: ['auth'] })

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()

  const error = ref('')

  async function loadMunicipality() {
    error.value = ''
    try {
      await stats.fetchMunicipalityDetail(String(route.params.slug))
    } catch (err: any) {
      stats.resetMunicipalityDetail()
      error.value = getApiErrorMessage(err, t)
    }
  }

  const { pending: loading } = useAsyncData(
    () => `municipality-${route.params.slug}`,
    loadMunicipality,
    { watch: [() => route.params.slug] },
  )

  const detail = computed(() => stats.municipalityDetail as any)

  const heroMetrics = computed(() => [
    {
      label: t('dashboard.transactions'),
      value: formatNumber(detail.value?.overview?.count),
      detail: t('municipality.coverageWindow', {
        from: detail.value?.overview?.earliest_year ?? '—',
        to: detail.value?.overview?.latest_year ?? '—',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(detail.value?.overview?.median_price),
      detail: `${formatNumber(detail.value?.overview?.avg_area, { maximumFractionDigits: 1 })} m²`,
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(detail.value?.overview?.median_price_per_m2),
      detail: detail.value?.region ?? '—',
    },
  ])

  const marketSignals = computed(() => [
    { label: t('map.region'), value: detail.value?.region ?? '—' },
    {
      label: t('municipality.regionStanding'),
      value:
        detail.value?.market_position?.region_rank_by_price_per_m2 != null
          ? `#${detail.value.market_position.region_rank_by_price_per_m2}`
          : '—',
    },
    {
      label: t('dashboard.propertyTypes'),
      value: detail.value?.property_type_mix?.[0]
        ? getPropertyTypeLabel(detail.value.property_type_mix[0].property_type, t)
        : '—',
    },
    {
      label: t('municipality.relatedMarkets'),
      value:
        detail.value?.related_municipalities?.length != null
          ? formatNumber(detail.value.related_municipalities.length)
          : '—',
    },
  ])

  const recentColumns = [
    { accessorKey: 'property_type', header: t('predict.propertyType') },
    { accessorKey: 'size_m2', header: t('predict.size') },
    { accessorKey: 'price_eur', header: t('dashboard.medianPrice') },
    { accessorKey: 'price_per_m2', header: '€/m²' },
    { accessorKey: 'year', header: t('map.yearFilter') },
    { accessorKey: 'actions', header: '', enableSorting: false },
  ]

  function shareStyle(share: number) {
    return { width: `${Math.max(10, Math.round((share ?? 0) * 100))}%` }
  }

  function openPrediction(transaction?: any) {
    router.push({
      path: '/napoved',
      query: {
        municipality: detail.value?.municipality ?? '',
        property_type: transaction?.property_type ?? 'stanovanje',
        size_m2: transaction?.size_m2 ?? detail.value?.overview?.avg_area ?? '',
        year_built: transaction?.year_built ?? '',
        price_eur: transaction?.price_eur ?? '',
      },
    })
  }

  function openMap() {
    router.push({
      path: '/zemljevid',
      query: {
        municipality: detail.value?.municipality ?? '',
        region: detail.value?.region ?? '',
      },
    })
  }
</script>

<template>
  <div class="municipality-page">
    <!-- Loading -->
    <div v-if="loading" class="state-card">
      <div class="grid gap-3">
        <USkeleton class="h-16 w-full" />
        <USkeleton class="h-8 w-2/3" />
        <USkeleton class="h-40 w-full" />
      </div>
    </div>

    <!-- Error -->
    <UAlert
      v-else-if="error"
      :description="error"
      color="error"
      variant="soft"
      icon="i-lucide-alert-circle"
    />

    <template v-else-if="detail">
      <!-- Hero -->
      <section class="municipality-hero">
        <div class="hero-main">
          <div>
            <span class="eyebrow">{{ t('municipality.pageEyebrow') }}</span>
            <h1>{{ detail.municipality }}</h1>
            <p class="muted">
              {{ t('municipality.heroBody', { region: detail.region ?? '—' }) }}
            </p>

            <div class="hero-actions">
              <UButton
                icon="i-lucide-bolt"
                :label="t('municipality.openPrediction')"
                @click="openPrediction()"
              />
              <UButton
                icon="i-lucide-map"
                variant="outline"
                color="neutral"
                :label="t('municipality.openMap')"
                @click="openMap"
              />
            </div>
          </div>

          <!-- Signal grid -->
          <div class="hero-storyline">
            <article v-for="item in marketSignals" :key="item.label" class="story-signal">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>
        </div>

        <div class="hero-side">
          <article v-for="card in heroMetrics" :key="card.label" class="metric-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <p class="muted">{{ card.detail }}</p>
          </article>
          <article class="metric-card accent">
            <span>{{ t('municipality.regionStanding') }}</span>
            <strong>#{{ detail.market_position?.region_rank_by_price_per_m2 ?? '—' }}</strong>
            <p>
              {{
                t('municipality.activityRankLabel', {
                  count: detail.market_position?.region_rank_by_activity ?? '—',
                })
              }}
            </p>
          </article>
        </div>
      </section>

      <!-- Year trend + property mix -->
      <section class="content-grid">
        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.priceTrend') }}</p>
              <h2>{{ t('municipality.yearTrend') }}</h2>
            </div>
          </div>

          <div v-if="detail.year_trend?.length" class="year-grid">
            <div v-for="item in detail.year_trend" :key="item.year" class="year-card">
              <strong>{{ item.year }}</strong>
              <span>{{ formatNumber(item.count) }} {{ t('dashboard.transactions') }}</span>
              <small>{{ formatCurrency(item.median_price) }}</small>
              <small>{{ formatCurrency(item.median_price_per_m2) }}/m²</small>
            </div>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('dashboard.propertyTypes') }}</p>
              <h2>{{ t('municipality.propertyMix') }}</h2>
            </div>
          </div>

          <div v-if="detail.property_type_mix?.length" class="mix-list">
            <div v-for="item in detail.property_type_mix" :key="item.property_type" class="mix-row">
              <div class="mix-copy">
                <strong>{{ getPropertyTypeLabel(item.property_type, t) }}</strong>
                <small>{{ formatPercent(item.share) }}</small>
              </div>
              <div class="mix-bar">
                <span :style="shareStyle(item.share)" />
              </div>
            </div>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>
      </section>

      <!-- Recent transactions + nearby benchmarks -->
      <section class="content-grid bottom-grid">
        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('municipality.recentTransactions') }}</p>
              <h2>{{ t('municipality.latestTransactions') }}</h2>
            </div>
          </div>

          <div v-if="detail.recent_transactions?.length" class="table-wrap">
            <UTable :columns="recentColumns" :data="detail.recent_transactions">
              <template #property_type-cell="{ row }">
                {{ getPropertyTypeLabel(row.original.property_type as string, t) ?? '—' }}
              </template>
              <template #size_m2-cell="{ row }">
                {{ formatNumber(row.original.size_m2 as number, { maximumFractionDigits: 1 }) }} m²
              </template>
              <template #price_eur-cell="{ row }">
                {{ formatCurrency(row.original.price_eur as number) }}
              </template>
              <template #price_per_m2-cell="{ row }">
                {{ formatCurrency(row.original.price_per_m2 as number) }}
              </template>
              <template #year-cell="{ row }">
                {{ row.original.year ?? '—' }}
              </template>
              <template #actions-cell="{ row }">
                <UButton
                  size="xs"
                  variant="soft"
                  :label="t('municipality.useForPrediction')"
                  @click="openPrediction(row.original)"
                />
              </template>
            </UTable>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('municipality.relatedMarkets') }}</p>
              <h2>{{ t('municipality.nearbyBenchmarks') }}</h2>
            </div>
          </div>

          <div v-if="detail.related_municipalities?.length" class="related-list">
            <NuxtLink
              v-for="item in detail.related_municipalities"
              :key="item.slug"
              :to="`/obcine/${item.slug}`"
              class="related-card"
            >
              <div>
                <strong>{{ item.municipality }}</strong>
                <small class="muted">{{ item.region ?? '—' }}</small>
              </div>
              <div class="related-metric">
                <strong>{{ formatCurrency(item.median_price_per_m2) }}</strong>
                <small class="muted"
                  >{{ formatNumber(item.count) }} {{ t('dashboard.transactions') }}</small
                >
              </div>
            </NuxtLink>
          </div>
          <p v-else class="muted">{{ t('common.noData') }}</p>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .municipality-page {
    display: grid;
    gap: 1.2rem;
  }

  .state-card {
    padding: 1.5rem;
    border-radius: 1.5rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .municipality-hero {
    position: relative;
    overflow: hidden;
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.95fr);
    gap: 1.1rem;
    padding: 1.35rem;
    border-radius: 1.6rem;
    border: 1px solid var(--border);
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 16%, transparent),
        transparent 32%
      ),
      radial-gradient(
        circle at right,
        color-mix(in srgb, var(--secondary) 12%, transparent),
        transparent 26%
      ),
      linear-gradient(135deg, var(--surface-panel-strong), var(--surface-soft));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .municipality-hero h1 {
    margin: 0.4rem 0 0.6rem;
    font-family: var(--font-display);
    font-size: clamp(1.8rem, 3vw, 2.7rem);
    line-height: 1.03;
  }

  .hero-main {
    display: grid;
    gap: 1rem;
    align-content: space-between;
  }

  .hero-actions {
    gap: 0.8rem;
    margin-top: 1rem;
  }

  .hero-storyline {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .story-signal {
    display: grid;
    gap: 0.25rem;
    padding: 0.9rem 0.95rem;
    border-radius: 1.2rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 20px rgb(15 23 42 / 6%);
  }

  .story-signal span {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .story-signal strong {
    font-size: 1rem;
    line-height: 1.15;
  }

  .hero-side {
    display: grid;
    gap: 0.8rem;
  }

  .metric-card {
    padding: 1rem;
    border-radius: 1.35rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      var(--shadow-sm);
  }

  .metric-card span {
    display: block;
    margin-bottom: 0.3rem;
    color: var(--text-soft);
    font-size: 0.82rem;
  }

  .metric-card strong {
    display: block;
    font-size: 1.3rem;
    line-height: 1.1;
  }

  .metric-card.accent {
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ui-bg-inverted) 88%, var(--ui-bg) 12%),
      color-mix(in srgb, var(--ui-bg-inverted) 80%, transparent)
    );
    color: var(--ui-text-inverted);
  }

  .metric-card.accent span,
  .metric-card.accent p {
    color: color-mix(in srgb, var(--ui-text-inverted) 72%, transparent);
  }

  .content-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.95fr);
    gap: 1rem;
  }

  .panel {
    padding: 1rem;
    border-radius: 1.5rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .panel-head {
    margin-bottom: 0.95rem;
  }

  .panel-head h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  .year-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.75rem;
  }

  .year-card {
    display: grid;
    gap: 0.2rem;
    padding: 0.9rem;
    border-radius: 1.15rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-muted) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease;
  }

  .year-card:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
  }

  .year-card strong {
    font-size: 1.1rem;
  }

  .year-card span,
  .year-card small {
    color: var(--text-muted);
    font-size: 0.82rem;
  }

  .mix-list {
    display: grid;
    gap: 0.8rem;
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

  .mix-copy small {
    color: var(--text-muted);
  }

  .mix-bar {
    height: 0.72rem;
    overflow: hidden;
    border-radius: 999px;
    background: color-mix(in srgb, var(--surface-muted) 90%, transparent);
  }

  .mix-bar span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(
      90deg,
      color-mix(in srgb, var(--warning) 88%, white 8%),
      color-mix(in srgb, var(--secondary) 22%, var(--warning) 78%)
    );
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
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-muted) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent)
    );
    text-decoration: none;
    color: inherit;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease;
  }

  .related-card:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 30px rgb(15 23 42 / 10%);
  }

  .related-card strong {
    display: block;
    font-size: 0.92rem;
  }

  .related-card small {
    display: block;
    font-size: 0.8rem;
  }

  .related-metric {
    text-align: right;
  }

  @media (max-width: 980px) {
    .municipality-hero,
    .content-grid {
      grid-template-columns: 1fr;
    }

    .hero-storyline {
      grid-template-columns: 1fr;
    }
  }
</style>
