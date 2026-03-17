<script setup>
  import { computed, ref } from 'vue'
  import { refDebounced, useAsyncState, watchDebounced } from '@vueuse/core'
  import { useI18n } from 'vue-i18n'
  import api from '~/legacy/composables/useApi'
  import { useAuthStore } from '~/legacy/stores/auth'
  import { useStatsStore } from '~/legacy/stores/stats'
  import { getApiErrorMessage } from '~/legacy/utils/apiError'
  import { formatCurrency, formatNumber, formatPercent } from '~/legacy/utils/format'
  import { getPropertyTypeLabel } from '~/legacy/utils/propertyType'

  definePageMeta({ middleware: ['auth'] })

  const EMPTY_MARKET_HOME = {
    headline: {},
    largest_markets: [],
    price_leaders: [],
    region_snapshot: [],
    latest_sales: [],
    property_type_mix: [],
    market_coverage: {},
  }

  const { t } = useI18n()
  const auth = useAuthStore()
  const stats = useStatsStore()

  const selectedPropertyType = ref('')
  const dashboardSearch = ref('')
  const debouncedSearch = refDebounced(dashboardSearch, 180)
  const segmentHome = ref(null)
  const segmentLoading = ref(false)
  const segmentError = ref('')

  useSeoMeta({
    title: () => `${t('dashboard.title')} | ${t('app.title')}`,
    description: () => t('layout.page.dashboard'),
  })

  function fmt(value, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value, decimals = 0) {
    return formatCurrency(value, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  function fmtPercent(value) {
    return formatPercent(value)
  }

  function propertyTypeLabel(value) {
    return getPropertyTypeLabel(value, t)
  }

  function matchesSearch(...values) {
    const query = debouncedSearch.value.trim().toLowerCase()
    if (!query) return true

    return values.some((value) =>
      String(value || '')
        .toLowerCase()
        .includes(query),
    )
  }

  function mixTone(share) {
    if (share >= 0.35) return 'success'
    if (share >= 0.15) return 'warning'
    return 'neutral'
  }

  const {
    state: marketHomeState,
    isLoading: dashboardLoading,
    error: dashboardFailure,
    execute: refreshDashboard,
  } = useAsyncState(() => stats.fetchMarketHome(), EMPTY_MARKET_HOME, {
    immediate: false,
    resetOnExecute: false,
  })

  await refreshDashboard()

  watchDebounced(
    selectedPropertyType,
    async (nextType) => {
      if (!nextType) {
        segmentHome.value = null
        segmentError.value = ''
        return
      }

      segmentLoading.value = true
      segmentError.value = ''

      try {
        const { data } = await api.get('/api/stats/market-home', {
          params: { property_type: nextType },
        })
        segmentHome.value = data
      } catch (error) {
        segmentHome.value = null
        segmentError.value = getApiErrorMessage(error, t)
      } finally {
        segmentLoading.value = false
      }
    },
    { debounce: 220, maxWait: 900 },
  )

  const pageError = computed(() =>
    dashboardFailure.value ? getApiErrorMessage(dashboardFailure.value, t) : '',
  )

  const marketHome = computed(() => marketHomeState.value || EMPTY_MARKET_HOME)
  const spotlight = computed(() => marketHome.value.largest_markets?.[0] || null)

  const summaryCards = computed(() => [
    {
      label: t('dashboard.totalRecords'),
      value: fmt(marketHome.value.headline?.total_records),
      meta: t('dashboard.marketCoverageYears', {
        from: marketHome.value.headline?.earliest_year || '—',
        to: marketHome.value.headline?.latest_year || '—',
      }),
      tone: 'primary',
    },
    {
      label: t('dashboard.medianPrice'),
      value: fmtCurrency(marketHome.value.headline?.median_price),
      meta: t('dashboard.latestYearLabel', {
        year: marketHome.value.headline?.latest_year || '—',
      }),
      tone: 'success',
    },
    {
      label: t('dashboard.pricePerM2'),
      value: fmtCurrency(marketHome.value.headline?.avg_price_per_m2),
      meta: spotlight.value?.municipality || t('common.noData'),
      tone: 'warning',
    },
    {
      label: t('dashboard.marketCoverageLabel'),
      value: `${fmt(marketHome.value.market_coverage?.present)} / ${fmt(marketHome.value.market_coverage?.official_total)}`,
      meta: t('dashboard.marketMunicipalities', {
        count: fmt(marketHome.value.market_coverage?.present),
      }),
      tone: 'neutral',
    },
  ])

  const spotlightStats = computed(() => {
    if (!spotlight.value) return []

    return [
      {
        label: t('map.region'),
        value: spotlight.value.region || '—',
      },
      {
        label: t('dashboard.transactions'),
        value: fmt(spotlight.value.count),
      },
      {
        label: t('dashboard.pricePerM2'),
        value: fmtCurrency(spotlight.value.median_price_per_m2),
      },
    ]
  })

  const propertyTypeButtons = computed(() => [
    { label: t('dashboard.filterAllTypes'), value: '' },
    ...(marketHome.value.property_type_mix || []).map((item) => ({
      label: propertyTypeLabel(item.property_type),
      value: item.property_type,
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

  const largestMarketsRows = computed(() =>
    (marketHome.value.largest_markets || []).filter((item) =>
      matchesSearch(item.municipality, item.region),
    ),
  )

  const regionSnapshotRows = computed(() =>
    (marketHome.value.region_snapshot || []).filter((item) => matchesSearch(item.region)),
  )

  const latestSalesRows = computed(() =>
    (marketHome.value.latest_sales || []).filter((item) =>
      matchesSearch(item.municipality, propertyTypeLabel(item.property_type), item.year),
    ),
  )

  const topPropertyMix = computed(() => (marketHome.value.property_type_mix || []).slice(0, 6))
  const priceLeaders = computed(() => (marketHome.value.price_leaders || []).slice(0, 6))
  const segmentLeaders = computed(() => (segmentHome.value?.largest_markets || []).slice(0, 4))
</script>

<template>
  <div class="page-frame py-6 lg:py-8">
    <div class="grid gap-6">
      <section
        class="relative overflow-hidden rounded-[2rem] border border-[var(--ui-border)] bg-[var(--surface-panel-strong)] p-6 shadow-[var(--shadow-lg)] lg:p-8"
      >
        <div
          class="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[radial-gradient(circle_at_top_left,color-mix(in_srgb,var(--ui-primary)_20%,transparent)_0%,transparent_65%),radial-gradient(circle_at_top_right,color-mix(in_srgb,var(--ui-secondary)_12%,transparent)_0%,transparent_58%)]"
        ></div>

        <div class="relative grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
          <div class="grid gap-6">
            <div class="flex flex-wrap items-center gap-3">
              <UBadge
                color="primary"
                variant="soft"
                :label="t('dashboard.consumerKicker')"
                class="rounded-full"
              />
              <span class="text-sm text-[var(--ui-text-muted)]">
                {{ t('dashboard.marketCommandTitle') }}
              </span>
            </div>

            <div class="grid gap-4">
              <div class="space-y-3">
                <h2
                  class="max-w-4xl text-3xl font-semibold tracking-tight text-[var(--ui-text)] lg:text-5xl"
                >
                  {{ t('dashboard.consumerTitle') }}
                </h2>
                <p class="max-w-3xl text-base leading-7 text-[var(--ui-text-toned)] lg:text-lg">
                  {{ t('dashboard.consumerBody') }}
                </p>
              </div>

              <div class="flex flex-wrap gap-3">
                <UButton to="/napoved" size="xl">
                  {{ t('dashboard.quickPrediction') }}
                </UButton>
                <UButton to="/zemljevid" color="neutral" variant="soft" size="xl">
                  {{ t('dashboard.quickMap') }}
                </UButton>
                <UButton
                  v-if="spotlight?.slug"
                  :to="`/obcine/${spotlight.slug}`"
                  color="neutral"
                  variant="outline"
                  size="xl"
                >
                  {{ t('dashboard.municipalitySpotlight') }}
                </UButton>
                <UButton v-if="auth.isAdmin" to="/admin" color="neutral" variant="ghost" size="xl">
                  {{ t('layout.openAdminWorkbench') }}
                </UButton>
              </div>
            </div>

            <UCard
              v-if="spotlight"
              variant="subtle"
              class="rounded-[1.6rem] border border-[var(--ui-border)] bg-[var(--surface-brand-soft)]"
            >
              <template #header>
                <div class="flex flex-wrap items-start justify-between gap-4">
                  <div class="space-y-2">
                    <p class="eyebrow">{{ t('dashboard.municipalitySpotlight') }}</p>
                    <div>
                      <h3 class="text-2xl font-semibold tracking-tight text-[var(--ui-text)]">
                        {{ spotlight.municipality }}
                      </h3>
                      <p class="text-sm text-[var(--ui-text-muted)]">
                        {{
                          t('dashboard.latestYearLabel', {
                            year: marketHome.headline?.latest_year || '—',
                          })
                        }}
                      </p>
                    </div>
                  </div>

                  <UBadge
                    color="success"
                    variant="soft"
                    :label="spotlight.region || '—'"
                    class="rounded-full"
                  />
                </div>
              </template>

              <div class="grid gap-3 sm:grid-cols-3">
                <div
                  v-for="item in spotlightStats"
                  :key="item.label"
                  class="rounded-2xl border border-white/30 bg-white/50 p-4 dark:bg-white/5"
                >
                  <p
                    class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                  >
                    {{ item.label }}
                  </p>
                  <p class="mt-2 text-xl font-semibold text-[var(--ui-text)]">
                    {{ item.value }}
                  </p>
                </div>
              </div>
            </UCard>
          </div>

          <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-2">
            <UCard
              v-for="card in summaryCards"
              :key="card.label"
              variant="subtle"
              class="rounded-[1.6rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
            >
              <div class="space-y-4">
                <UBadge
                  :color="card.tone"
                  variant="soft"
                  :label="card.label"
                  class="rounded-full"
                />
                <div class="space-y-1">
                  <p class="text-3xl font-semibold tracking-tight text-[var(--ui-text)]">
                    {{ card.value }}
                  </p>
                  <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                    {{ card.meta }}
                  </p>
                </div>
              </div>
            </UCard>
          </div>
        </div>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <UCard
          variant="subtle"
          class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
        >
          <template #header>
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div class="space-y-2">
                <p class="eyebrow">{{ t('dashboard.dataLens') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ t('dashboard.marketTableTitle') }}
                </h3>
                <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{ t('dashboard.filterCompareHint') }}
                </p>
              </div>

              <div class="w-full max-w-md">
                <UInput
                  v-model="dashboardSearch"
                  icon="i-lucide-search"
                  size="xl"
                  :placeholder="t('common.search')"
                />
              </div>
            </div>
          </template>

          <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <button
              v-for="option in propertyTypeButtons"
              :key="option.value || 'all'"
              type="button"
              class="rounded-2xl border px-4 py-3 text-left transition duration-200"
              :class="
                selectedPropertyType === option.value
                  ? 'border-[var(--ui-primary)] bg-[color-mix(in_srgb,var(--ui-primary)_12%,var(--surface-strong))] shadow-[var(--shadow-control)]'
                  : 'border-[var(--ui-border)] bg-[var(--surface-strong)] hover:border-[color-mix(in_srgb,var(--ui-primary)_28%,var(--ui-border))] hover:bg-[var(--surface-soft)]'
              "
              @click="selectedPropertyType = option.value"
            >
              <p class="text-sm font-semibold text-[var(--ui-text)]">{{ option.label }}</p>
              <p class="mt-1 text-xs leading-5 text-[var(--ui-text-muted)]">
                {{ option.value ? t('dashboard.segmentSpotlight') : t('dashboard.filterAllHint') }}
              </p>
            </button>
          </div>
        </UCard>

        <UCard
          variant="subtle"
          class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
        >
          <template #header>
            <div class="space-y-2">
              <p class="eyebrow">{{ t('dashboard.workflowTitle') }}</p>
              <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                {{ auth.isAdmin ? t('dashboard.workflowAdmin') : t('dashboard.workflowViewer') }}
              </h3>
              <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                {{
                  auth.isAdmin
                    ? t('dashboard.workflowAdminDetail')
                    : t('dashboard.workflowViewerDetail')
                }}
              </p>
            </div>
          </template>

          <div class="grid gap-3">
            <div
              class="rounded-2xl border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
            >
              <p
                class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
              >
                {{ t('dashboard.propertyMix') }}
              </p>
              <div class="mt-3 flex flex-wrap gap-2">
                <UBadge
                  v-for="item in topPropertyMix"
                  :key="item.property_type"
                  :color="mixTone(item.share)"
                  variant="soft"
                  :label="`${propertyTypeLabel(item.property_type)} · ${fmtPercent(item.share)}`"
                  class="rounded-full"
                />
              </div>
            </div>

            <div
              class="rounded-2xl border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
            >
              <div class="flex items-center justify-between gap-3">
                <div>
                  <p
                    class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                  >
                    {{ t('dashboard.priceLeaders') }}
                  </p>
                  <p class="mt-2 text-sm text-[var(--ui-text-muted)]">
                    {{ t('dashboard.priceLeadersTitle') }}
                  </p>
                </div>
                <UBadge
                  color="success"
                  variant="soft"
                  :label="`${priceLeaders.length}`"
                  class="rounded-full"
                />
              </div>
            </div>
          </div>
        </UCard>
      </section>

      <div v-if="dashboardLoading" class="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
        <USkeleton v-for="index in 4" :key="index" class="h-40 rounded-[1.75rem]" />
      </div>

      <UCard
        v-else-if="pageError"
        variant="subtle"
        class="rounded-[1.75rem] border border-[color-mix(in_srgb,var(--ui-error)_36%,var(--ui-border))] bg-[var(--surface-panel)]"
      >
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="space-y-2">
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-circle-alert" class="text-lg text-[var(--ui-error)]" />
              <p class="text-lg font-semibold text-[var(--ui-text)]">{{ t('common.error') }}</p>
            </div>
            <p class="text-sm leading-6 text-[var(--ui-text-muted)]">{{ pageError }}</p>
          </div>

          <UButton color="neutral" variant="soft" @click="refreshDashboard">
            {{ t('common.retry') }}
          </UButton>
        </div>
      </UCard>

      <template v-else>
        <UCard
          v-if="selectedPropertyType"
          variant="subtle"
          class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
        >
          <template #header>
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div class="space-y-2">
                <p class="eyebrow">{{ t('dashboard.segmentSpotlight') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{
                    t('dashboard.segmentSpotlightTitle', {
                      type: propertyTypeLabel(selectedPropertyType),
                    })
                  }}
                </h3>
                <p class="text-sm leading-6 text-[var(--ui-text-muted)]">
                  {{ t('dashboard.segmentTopMarketsTitle') }}
                </p>
              </div>

              <UBadge
                color="primary"
                variant="soft"
                :label="propertyTypeLabel(selectedPropertyType)"
                class="rounded-full"
              />
            </div>
          </template>

          <div v-if="segmentLoading" class="grid gap-4 lg:grid-cols-4">
            <USkeleton v-for="index in 4" :key="`segment-${index}`" class="h-32 rounded-[1.5rem]" />
          </div>

          <div
            v-else-if="segmentError"
            class="rounded-2xl border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
          >
            <p class="text-sm text-[var(--ui-error)]">{{ segmentError }}</p>
          </div>

          <div v-else-if="segmentHome" class="grid gap-4">
            <div class="grid gap-4 lg:grid-cols-4">
              <div
                v-for="card in segmentCards"
                :key="card.label"
                class="rounded-[1.4rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
              >
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ card.label }}
                </p>
                <p class="mt-3 text-2xl font-semibold text-[var(--ui-text)]">{{ card.value }}</p>
                <p class="mt-2 text-sm text-[var(--ui-text-muted)]">{{ card.meta }}</p>
              </div>
            </div>

            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <NuxtLink
                v-for="item in segmentLeaders"
                :key="`${selectedPropertyType}-${item.slug}`"
                :to="`/obcine/${item.slug}`"
                class="rounded-[1.4rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4 transition duration-200 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--ui-primary)_24%,var(--ui-border))]"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="font-semibold text-[var(--ui-text)]">{{ item.municipality }}</p>
                    <p class="mt-1 text-sm text-[var(--ui-text-muted)]">{{ item.region || '—' }}</p>
                  </div>
                  <UBadge
                    color="success"
                    variant="soft"
                    :label="fmt(item.count)"
                    class="rounded-full"
                  />
                </div>
              </NuxtLink>
            </div>
          </div>
        </UCard>

        <section class="grid gap-4 xl:grid-cols-[1.1fr_0.9fr_0.9fr]">
          <UCard
            variant="subtle"
            class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
          >
            <template #header>
              <div class="space-y-2">
                <p class="eyebrow">{{ t('dashboard.largestMarkets') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ t('dashboard.marketTableTitle') }}
                </h3>
              </div>
            </template>

            <div v-if="largestMarketsRows.length" class="grid gap-3">
              <NuxtLink
                v-for="item in largestMarketsRows.slice(0, 8)"
                :key="item.slug"
                :to="`/obcine/${item.slug}`"
                class="rounded-[1.35rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4 transition duration-200 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--ui-primary)_26%,var(--ui-border))]"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="space-y-1">
                    <p class="font-semibold text-[var(--ui-text)]">{{ item.municipality }}</p>
                    <p class="text-sm text-[var(--ui-text-muted)]">{{ item.region || '—' }}</p>
                  </div>

                  <div class="text-right">
                    <p class="text-sm font-semibold text-[var(--ui-text)]">{{ fmt(item.count) }}</p>
                    <p class="text-xs text-[var(--ui-text-muted)]">
                      {{ fmtCurrency(item.median_price_per_m2) }}/m²
                    </p>
                  </div>
                </div>
              </NuxtLink>
            </div>
            <p v-else class="text-sm text-[var(--ui-text-muted)]">{{ t('common.noData') }}</p>
          </UCard>

          <UCard
            variant="subtle"
            class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
          >
            <template #header>
              <div class="space-y-2">
                <p class="eyebrow">{{ t('dashboard.regionSnapshot') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ t('dashboard.regionTableTitle') }}
                </h3>
              </div>
            </template>

            <div v-if="regionSnapshotRows.length" class="grid gap-3">
              <div
                v-for="item in regionSnapshotRows.slice(0, 8)"
                :key="item.region"
                class="rounded-[1.35rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="font-semibold text-[var(--ui-text)]">{{ item.region || '—' }}</p>
                    <p class="mt-1 text-sm text-[var(--ui-text-muted)]">
                      {{ fmt(item.count) }} {{ t('dashboard.transactions') }}
                    </p>
                  </div>

                  <UBadge
                    color="warning"
                    variant="soft"
                    :label="fmtCurrency(item.median_price_per_m2)"
                    class="rounded-full"
                  />
                </div>
              </div>
            </div>
            <p v-else class="text-sm text-[var(--ui-text-muted)]">{{ t('common.noData') }}</p>
          </UCard>

          <UCard
            variant="subtle"
            class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
          >
            <template #header>
              <div class="space-y-2">
                <p class="eyebrow">{{ t('dashboard.priceLeaders') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ t('dashboard.priceLeadersTitle') }}
                </h3>
              </div>
            </template>

            <div v-if="priceLeaders.length" class="grid gap-3">
              <NuxtLink
                v-for="item in priceLeaders"
                :key="item.slug"
                :to="`/obcine/${item.slug}`"
                class="rounded-[1.35rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4 transition duration-200 hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--ui-primary)_26%,var(--ui-border))]"
              >
                <div class="space-y-2">
                  <div class="flex items-center justify-between gap-3">
                    <p class="font-semibold text-[var(--ui-text)]">{{ item.municipality }}</p>
                    <UBadge
                      color="success"
                      variant="soft"
                      :label="`${fmtCurrency(item.median_price_per_m2)}/m²`"
                      class="rounded-full"
                    />
                  </div>
                  <p class="text-sm text-[var(--ui-text-muted)]">{{ item.region || '—' }}</p>
                </div>
              </NuxtLink>
            </div>
            <p v-else class="text-sm text-[var(--ui-text-muted)]">{{ t('common.noData') }}</p>
          </UCard>
        </section>

        <UCard
          variant="subtle"
          class="rounded-[1.75rem] border border-[var(--ui-border)] bg-[var(--surface-panel)]"
        >
          <template #header>
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div class="space-y-2">
                <p class="eyebrow">{{ t('dashboard.recentSales') }}</p>
                <h3 class="text-xl font-semibold tracking-tight text-[var(--ui-text)]">
                  {{ t('dashboard.latestTransactions') }}
                </h3>
              </div>

              <UBadge
                color="neutral"
                variant="soft"
                :label="`${latestSalesRows.length}`"
                class="rounded-full"
              />
            </div>
          </template>

          <div v-if="latestSalesRows.length" class="grid gap-3">
            <div
              v-for="(item, index) in latestSalesRows.slice(0, 10)"
              :key="`${item.slug}-${item.year}-${index}`"
              class="grid gap-4 rounded-[1.4rem] border border-[var(--ui-border)] bg-[var(--surface-strong)] p-4 lg:grid-cols-[1.4fr_repeat(4,minmax(0,1fr))]"
            >
              <div class="space-y-1">
                <NuxtLink
                  :to="`/obcine/${item.slug}`"
                  class="font-semibold text-[var(--ui-text)] transition hover:text-[var(--ui-primary)]"
                >
                  {{ item.municipality }}
                </NuxtLink>
                <p class="text-sm text-[var(--ui-text-muted)]">
                  {{ propertyTypeLabel(item.property_type) }}
                </p>
              </div>

              <div>
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ t('predict.size') }}
                </p>
                <p class="mt-2 font-semibold text-[var(--ui-text)]">
                  {{ fmt(item.size_m2, 1) }} m²
                </p>
              </div>

              <div>
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ t('dashboard.medianPrice') }}
                </p>
                <p class="mt-2 font-semibold text-[var(--ui-text)]">
                  {{ fmtCurrency(item.price_eur) }}
                </p>
              </div>

              <div>
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ t('dashboard.pricePerM2') }}
                </p>
                <p class="mt-2 font-semibold text-[var(--ui-text)]">
                  {{ fmtCurrency(item.price_per_m2) }}
                </p>
              </div>

              <div>
                <p
                  class="text-xs font-medium uppercase tracking-[0.18em] text-[var(--ui-text-muted)]"
                >
                  {{ t('map.year') }}
                </p>
                <p class="mt-2 font-semibold text-[var(--ui-text)]">{{ item.year || '—' }}</p>
              </div>
            </div>
          </div>
          <p v-else class="text-sm text-[var(--ui-text-muted)]">{{ t('common.noData') }}</p>
        </UCard>
      </template>
    </div>
  </div>
</template>
