<script setup>
  import { computed, ref, watch } from 'vue'
  import { RouterLink, useRoute, useRouter } from 'vue-router'
  import { useI18n } from 'vue-i18n'
  import AppIcon from '../components/AppIcon.vue'
  import LoadingSpinner from '../components/LoadingSpinner.vue'
  import { useStatsStore } from '../stores/stats'
  import { getApiErrorMessage } from '../utils/apiError'
  import { formatCurrency, formatNumber, formatPercent } from '../utils/format'
  import { getPropertyTypeLabel } from '../utils/propertyType'

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()

  const loading = ref(false)
  const error = ref('')

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtPercent(value) {
    return formatPercent(value)
  }

  function formatType(value) {
    return getPropertyTypeLabel(value, t)
  }

  async function loadMunicipality() {
    loading.value = true
    error.value = ''

    try {
      await stats.fetchMunicipalityDetail(route.params.slug)
    } catch (err) {
      stats.resetMunicipalityDetail()
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  watch(
    () => route.params.slug,
    () => {
      loadMunicipality()
    },
    { immediate: true },
  )

  const detail = computed(() => stats.municipalityDetail)

  const heroMetrics = computed(() => [
    {
      label: t('dashboard.transactions'),
      value: fmt(detail.value?.overview?.count),
      detail: t('municipality.coverageWindow', {
        from: detail.value?.overview?.earliest_year || '—',
        to: detail.value?.overview?.latest_year || '—',
      }),
    },
    {
      label: t('dashboard.medianPrice'),
      value: formatCurrency(detail.value?.overview?.median_price),
      detail: `${fmt(detail.value?.overview?.avg_area, 1)} m²`,
    },
    {
      label: t('dashboard.pricePerM2'),
      value: formatCurrency(detail.value?.overview?.median_price_per_m2),
      detail: detail.value?.region || '—',
    },
  ])

  const dominantPropertyType = computed(() => detail.value?.property_type_mix?.[0] || null)

  const marketSignals = computed(() => [
    {
      label: t('map.region'),
      value: detail.value?.region || '—',
    },
    {
      label: t('municipality.regionStanding'),
      value:
        detail.value?.market_position?.region_rank_by_price_per_m2 != null
          ? `#${detail.value.market_position.region_rank_by_price_per_m2}`
          : '—',
    },
    {
      label: t('dashboard.propertyTypes'),
      value: dominantPropertyType.value
        ? formatType(dominantPropertyType.value.property_type)
        : '—',
    },
    {
      label: t('municipality.relatedMarkets'),
      value:
        detail.value?.related_municipalities?.length != null
          ? fmt(detail.value.related_municipalities.length)
          : '—',
    },
  ])

  function shareStyle(share) {
    return { width: `${Math.max(10, Math.round((share || 0) * 100))}%` }
  }

  function openPrediction(transaction = null) {
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
      },
    })
  }
</script>

<template>
  <div class="municipality-page">
    <div v-if="loading" class="state-card">
      <LoadingSpinner :label="t('common.loading')" />
    </div>

    <p v-else-if="error" class="state-card error-text">{{ error }}</p>

    <template v-else-if="detail">
      <section class="municipality-hero">
        <div class="hero-main">
          <div>
            <span class="eyebrow">{{ t('municipality.pageEyebrow') }}</span>
            <h1>{{ detail.municipality }}</h1>
            <p>
              {{ t('municipality.heroBody', { region: detail.region || '—' }) }}
            </p>

            <div class="hero-actions">
              <button class="hero-btn primary" @click="openPrediction()">
                <AppIcon name="prediction" :size="16" />
                <span>{{ t('municipality.openPrediction') }}</span>
              </button>
              <button class="hero-btn" @click="openMap">
                <AppIcon name="map" :size="16" />
                <span>{{ t('municipality.openMap') }}</span>
              </button>
            </div>
          </div>

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
            <p>{{ card.detail }}</p>
          </article>

          <article class="metric-card accent">
            <span>{{ t('municipality.regionStanding') }}</span>
            <strong> #{{ detail.market_position?.region_rank_by_price_per_m2 || '—' }} </strong>
            <p>
              {{
                t('municipality.activityRankLabel', {
                  count: detail.market_position?.region_rank_by_activity || '—',
                })
              }}
            </p>
          </article>
        </div>
      </section>

      <section class="content-grid">
        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow subtle">{{ t('dashboard.priceTrend') }}</span>
              <h2>{{ t('municipality.yearTrend') }}</h2>
            </div>
          </div>

          <div v-if="detail.year_trend?.length" class="year-grid">
            <div v-for="item in detail.year_trend" :key="item.year" class="year-card">
              <strong>{{ item.year }}</strong>
              <span>{{ fmt(item.count) }} {{ t('dashboard.transactions') }}</span>
              <small>{{ formatCurrency(item.median_price) }}</small>
              <small>{{ formatCurrency(item.median_price_per_m2) }}/m²</small>
            </div>
          </div>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
        </article>

        <article class="panel">
          <div class="panel-head">
            <div>
              <span class="eyebrow subtle">{{ t('dashboard.propertyTypes') }}</span>
              <h2>{{ t('municipality.propertyMix') }}</h2>
            </div>
          </div>

          <div v-if="detail.property_type_mix?.length" class="mix-list">
            <div v-for="item in detail.property_type_mix" :key="item.property_type" class="mix-row">
              <div class="mix-copy">
                <strong>{{ formatType(item.property_type) }}</strong>
                <small>{{ fmtPercent(item.share) }}</small>
              </div>
              <div class="mix-bar">
                <span :style="shareStyle(item.share)"></span>
              </div>
            </div>
          </div>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
        </article>
      </section>

      <section class="content-grid bottom-grid">
        <article class="panel panel-wide">
          <div class="panel-head">
            <div>
              <span class="eyebrow subtle">{{ t('municipality.recentTransactions') }}</span>
              <h2>{{ t('municipality.latestTransactions') }}</h2>
            </div>
          </div>

          <div v-if="detail.recent_transactions?.length" class="table-shell">
            <table>
              <thead>
                <tr>
                  <th>{{ t('predict.propertyType') }}</th>
                  <th>{{ t('predict.size') }}</th>
                  <th>{{ t('dashboard.medianPrice') }}</th>
                  <th>€/m²</th>
                  <th>{{ t('map.yearFilter') }}</th>
                  <th>{{ t('common.actions') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in detail.recent_transactions"
                  :key="`${item.property_type}-${item.price_eur}-${item.year}`"
                >
                  <td>{{ formatType(item.property_type) || '—' }}</td>
                  <td>{{ fmt(item.size_m2, 1) }} m²</td>
                  <td>{{ formatCurrency(item.price_eur) }}</td>
                  <td>{{ formatCurrency(item.price_per_m2) }}</td>
                  <td>{{ item.year || '—' }}</td>
                  <td>
                    <button class="table-btn" @click="openPrediction(item)">
                      {{ t('municipality.useForPrediction') }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
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
                <small>{{ item.region || '—' }}</small>
              </div>
              <div class="related-metric">
                <strong>{{ formatCurrency(item.median_price_per_m2) }}</strong>
                <small>{{ fmt(item.count) }} {{ t('dashboard.transactions') }}</small>
              </div>
            </RouterLink>
          </div>
          <p v-else class="empty-text">{{ t('common.noData') }}</p>
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

  .municipality-hero,
  .panel,
  .metric-card,
  .state-card {
    border-radius: 1.6rem;
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
    background:
      linear-gradient(135deg, var(--surface-panel-strong), var(--surface-soft)),
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 16%, transparent),
        transparent 32%
      ),
      radial-gradient(
        circle at right,
        color-mix(in srgb, var(--secondary) 12%, transparent),
        transparent 26%
      );
  }

  .municipality-hero h1,
  .panel h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  .municipality-hero h1 {
    font-size: clamp(1.8rem, 3vw, 2.7rem);
    line-height: 1.03;
  }

  .municipality-hero p,
  .metric-card p,
  .year-card span,
  .year-card small,
  .mix-copy small,
  .related-card small,
  .empty-text {
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

  .hero-main {
    display: grid;
    gap: 1rem;
    align-content: space-between;
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
    margin-top: 1.2rem;
  }

  .hero-btn,
  .table-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.8rem 1rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface-panel);
    color: var(--text);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      box-shadow 160ms ease,
      border-color 160ms ease,
      background 160ms ease;
  }

  .hero-btn:hover,
  .table-btn:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 30px rgb(15 23 42 / 10%);
  }

  .hero-btn.primary,
  .table-btn {
    border-color: color-mix(in srgb, var(--primary) 28%, transparent);
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--primary) 86%, white 6%),
      color-mix(in srgb, var(--secondary) 18%, var(--primary) 82%)
    );
    color: var(--ui-text-inverted);
  }

  .hero-side,
  .mix-list,
  .related-list {
    display: grid;
    gap: 0.8rem;
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

  .metric-card,
  .panel {
    padding: 1rem;
  }

  .metric-card span {
    display: block;
    margin-bottom: 0.35rem;
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

  .bottom-grid .panel-wide {
    min-width: 0;
  }

  .panel-wide {
    grid-column: span 1;
  }

  .panel-head {
    margin-bottom: 0.95rem;
  }

  .year-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.75rem;
  }

  .year-card,
  .related-card {
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
    text-decoration: none;
    color: inherit;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease,
      background 160ms ease;
  }

  .year-card:hover,
  .related-card:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 9%, var(--surface-soft-muted)),
      color-mix(in srgb, var(--secondary) 7%, var(--surface-soft))
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 30px rgb(15 23 42 / 10%);
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
    background: color-mix(in srgb, var(--ui-bg-muted) 90%, transparent);
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

  .table-shell {
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    padding: 0.8rem 0.45rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }

  th {
    color: var(--text-soft);
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .related-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .related-metric {
    text-align: right;
  }

  .state-card {
    padding: 1.6rem;
  }

  .error-text {
    color: var(--danger);
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

  @media (max-width: 720px) {
    .municipality-hero,
    .panel,
    .metric-card {
      padding: 1rem;
    }
  }
</style>
