<script setup lang="ts">
  definePageMeta({ middleware: ['auth'] })

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const api = useApi()

  // Filters
  const ALL = '_all'
  const selectedYear = ref(route.query.year ? String(route.query.year) : ALL)
  const selectedRegion = ref(route.query.region ? String(route.query.region) : ALL)
  const selectedType = ref(route.query.type ? String(route.query.type) : ALL)
  const selectedMunicipality = ref(route.query.municipality ? String(route.query.municipality) : ALL)

  // Data
  const loading = ref(false)
  const error = ref('')
  const transactions = ref<any[]>([])
  const availableYears = ref<string[]>([])
  const regionStats = ref<any[]>([])
  const allMunicipalities = ref<any[]>([])
  const propertyTypes = ref<any[]>([])
  const mapLegend = ref<any>(null)

  // Detail panel
  const selectedRecord = ref<any>(null)
  const detailOpen = ref(false)

  // Legend thresholds derived from transactions
  const legendThresholds = computed(() => {
    if (mapLegend.value?.thresholds) return mapLegend.value.thresholds
    const prices = transactions.value
      .map((t) => t.price_per_m2)
      .filter(Boolean)
      .sort((a: number, b: number) => a - b)
    if (!prices.length) return { low_max: 2000, mid_max: 3500 }
    return {
      low_max: prices[Math.floor(prices.length * 0.33)],
      mid_max: prices[Math.floor(prices.length * 0.66)],
    }
  })

  const mapTransactions = computed(() =>
    transactions.value
      .filter((t) => t.lat != null && t.lon != null)
      .map((t) => ({ ...t, lng: t.lon })),
  )

  const yearOptions = computed(() => [
    { label: t('map.allYears'), value: ALL },
    ...availableYears.value.map((y) => ({ label: String(y), value: String(y) })),
  ])

  const regionOptions = computed(() => [
    { label: t('map.allRegions'), value: ALL },
    ...regionStats.value.map((r) => ({ label: r.region, value: r.region })),
  ])

  const typeOptions = computed(() => [
    { label: t('map.allTypes'), value: ALL },
    ...propertyTypes.value.map((p) => ({
      label: `${getPropertyTypeLabel(p.type, t)} (${formatNumber(p.count)})`,
      value: p.type,
    })),
  ])

  const municipalityOptions = computed(() => {
    const base = selectedRegion.value && selectedRegion.value !== ALL
      ? allMunicipalities.value.filter((m) => m.region === selectedRegion.value)
      : allMunicipalities.value
    return [
      { label: t('map.allMunicipalities'), value: ALL },
      ...base.map((m) => ({ label: m.municipality, value: m.municipality })),
    ]
  })

  const statsCards = computed(() => {
    const count = transactions.value.length
    const prices = transactions.value.map((t) => t.price_eur).filter(Boolean)
    const avg = prices.length
      ? prices.reduce((a: number, b: number) => a + b, 0) / prices.length
      : null
    const ppm2s = transactions.value.map((t) => t.price_per_m2).filter(Boolean)
    const avgPpm2 = ppm2s.length
      ? ppm2s.reduce((a: number, b: number) => a + b, 0) / ppm2s.length
      : null
    return [
      { label: t('dashboard.transactions'), value: formatNumber(count) },
      { label: t('dashboard.medianPrice'), value: formatCurrency(avg) },
      { label: t('dashboard.pricePerM2'), value: formatCurrency(avgPpm2) },
    ]
  })

  const metaLoaded = ref(false)

  async function loadFilterMeta() {
    try {
      const [overviewRes, regionsRes, muniRes] = await Promise.all([
        api.get('/api/stats/overview'),
        api.get('/api/stats/regions'),
        api.get('/api/stats/municipalities-by-region'),
      ])

      const overview = overviewRes.data as any
      availableYears.value = overview?.data_years ?? []
      propertyTypes.value = overview?.property_types ?? []

      regionStats.value = (regionsRes.data as any[]) ?? []

      const muniByRegion = muniRes.data as Record<string, string[]>
      const munis: { municipality: string; region: string }[] = []
      for (const [region, municipalities] of Object.entries(muniByRegion || {})) {
        for (const muni of municipalities) {
          munis.push({ municipality: muni, region })
        }
      }
      allMunicipalities.value = munis

      // Default year to last completed year
      if (selectedYear.value === ALL && availableYears.value.length) {
        const currentYear = new Date().getFullYear()
        selectedYear.value =
          availableYears.value.find((y) => Number(y) < currentYear) ?? availableYears.value[0] ?? ALL
      }

      metaLoaded.value = true
    } catch (e: any) {
      error.value = getApiErrorMessage(e, t)
    }
  }

  async function loadTransactions() {
    loading.value = true
    error.value = ''
    try {
      const params: Record<string, string> = {}
      if (selectedYear.value && selectedYear.value !== ALL) params.year = selectedYear.value
      if (selectedRegion.value && selectedRegion.value !== ALL) params.statistical_region = selectedRegion.value
      if (selectedType.value && selectedType.value !== ALL) params.property_type = selectedType.value
      if (selectedMunicipality.value && selectedMunicipality.value !== ALL) params.municipality = selectedMunicipality.value

      const txRes = await api.get('/api/stats/map-transactions', { params })
      transactions.value = (txRes.data as any)?.transactions ?? []
      mapLegend.value = (txRes.data as any)?.meta?.legend ?? null
    } catch (e: any) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  function onMarkerSelect(tx: any) {
    selectedRecord.value = tx
    detailOpen.value = true
  }

  function openMunicipality() {
    if (!selectedRecord.value?.municipality) return
    const slug = selectedRecord.value.municipality.toLowerCase().replace(/\s+/g, '-')
    router.push(`/obcine/${slug}`)
  }

  function openPrediction() {
    if (!selectedRecord.value) return
    router.push({
      path: '/napoved',
      query: {
        municipality: selectedRecord.value.municipality,
        property_type: selectedRecord.value.property_type,
        size_m2: selectedRecord.value.size_m2,
      },
    })
  }

  watchDebounced(
    [selectedYear, selectedRegion, selectedType, selectedMunicipality],
    () => {
      void loadTransactions()
    },
    { debounce: 300 },
  )

  useLazyAsyncData('map-init', async () => {
    await loadFilterMeta()
    await loadTransactions()
  })
</script>

<template>
  <div class="map-page">
    <!-- Filter bar -->
    <section class="panel filter-bar">
      <div class="filter-head">
        <div>
          <p class="eyebrow">{{ t('nav.map') }}</p>
          <h1>{{ t('map.title') }}</h1>
        </div>
        <div class="filter-stats">
          <article v-for="card in statsCards" :key="card.label" class="stat-chip">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
          </article>
        </div>
      </div>

      <div class="filter-row">
        <label class="filter-field">
          <span>{{ t('map.yearFilter') }}</span>
          <USelectMenu v-model="selectedYear" :items="yearOptions" value-key="value" />
        </label>
        <label class="filter-field">
          <span>{{ t('map.regionFilter') }}</span>
          <USelectMenu v-model="selectedRegion" :items="regionOptions" value-key="value" />
        </label>
        <label class="filter-field">
          <span>{{ t('predict.propertyType') }}</span>
          <USelectMenu v-model="selectedType" :items="typeOptions" value-key="value" />
        </label>
        <label class="filter-field">
          <span>{{ t('dashboard.municipality') }}</span>
          <USelectMenu v-model="selectedMunicipality" :items="municipalityOptions" value-key="value" />
        </label>
      </div>
    </section>

    <UAlert
      v-if="error"
      :description="error"
      color="error"
      variant="soft"
      icon="i-lucide-alert-circle"
    />

    <!-- Map + detail -->
    <section class="map-shell">
      <!-- Legend overlay -->
      <div class="map-legend">
        <p class="eyebrow">{{ t('map.legend') }}</p>
        <div class="legend-item">
          <span class="dot dot-low" />
          <span>{{ t('map.low') }} ≤ {{ formatCurrency(legendThresholds.low_max) }}</span>
        </div>
        <div class="legend-item">
          <span class="dot dot-mid" />
          <span>{{ t('map.mid') }}</span>
        </div>
        <div class="legend-item">
          <span class="dot dot-high" />
          <span>{{ t('map.high') }} ≥ {{ formatCurrency(legendThresholds.mid_max) }}</span>
        </div>
      </div>

      <div v-if="loading" class="map-placeholder">
        <USkeleton class="h-full w-full" />
      </div>
      <ClientOnly v-else>
        <MapLeafletMap :transactions="mapTransactions" @select="onMarkerSelect" />
      </ClientOnly>
    </section>

    <!-- Detail slide panel -->
    <Transition name="slide-panel">
      <section v-if="detailOpen && selectedRecord" class="detail-panel">
        <div class="detail-head">
          <div>
            <p class="eyebrow">{{ t('map.transactionDetail') }}</p>
            <h2>{{ selectedRecord.municipality }}</h2>
            <p class="muted">
              {{ getPropertyTypeLabel(selectedRecord.property_type, t) }}
              <span v-if="selectedRecord.year"> · {{ selectedRecord.year }}</span>
            </p>
          </div>
          <UButton
            icon="i-lucide-x"
            color="neutral"
            variant="ghost"
            size="sm"
            :aria-label="t('common.close')"
            @click="detailOpen = false"
          />
        </div>

        <div class="detail-kpis">
          <KpiCard :label="t('dashboard.medianPrice')" :value="formatCurrency(selectedRecord.price_eur)" />
          <KpiCard :label="t('dashboard.pricePerM2')" :value="formatCurrency(selectedRecord.price_per_m2)" />
          <KpiCard :label="t('predict.size')" :value="`${formatNumber(selectedRecord.size_m2, { maximumFractionDigits: 1 })} m²`" />
          <KpiCard v-if="selectedRecord.year" :label="t('map.yearFilter')" :value="selectedRecord.year" />
        </div>

        <div v-if="selectedRecord.region" class="detail-meta">
          <span class="muted">{{ t('map.region') }}:</span>
          <strong>{{ selectedRecord.region }}</strong>
        </div>

        <div class="detail-actions">
          <UButton
            icon="i-lucide-bolt"
            :label="t('municipality.openPrediction')"
            @click="openPrediction"
          />
          <UButton
            icon="i-lucide-map-pin"
            variant="outline"
            color="neutral"
            :label="t('municipality.openMunicipality')"
            @click="openMunicipality"
          />
        </div>
      </section>
    </Transition>

    <!-- Activity feed -->
    <section class="panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow subtle">{{ t('map.recentActivity') }}</p>
          <h2>{{ t('map.latestTransactions') }}</h2>
        </div>
        <UBadge
          :label="`${formatNumber(transactions.length)} ${t('dashboard.transactions')}`"
          color="neutral"
          variant="soft"
        />
      </div>

      <div v-if="loading" class="grid gap-2">
        <USkeleton v-for="i in 6" :key="i" class="h-10" />
      </div>
      <div v-else-if="!transactions.length" class="muted">{{ t('empty.noResults') }}</div>
      <div v-else class="table-wrap">
        <UTable
          :columns="[
            { accessorKey: 'municipality', header: t('dashboard.municipality') },
            { accessorKey: 'property_type', header: t('predict.propertyType') },
            { accessorKey: 'size_m2', header: t('predict.size') },
            { accessorKey: 'price_eur', header: t('dashboard.medianPrice') },
            { accessorKey: 'price_per_m2', header: '€/m²' },
            { accessorKey: 'year', header: t('map.yearFilter') },
          ]"
          :data="transactions.slice(0, 50)"
        >
          <template #property_type-cell="{ row }">
            {{ getPropertyTypeLabel(row.original.property_type, t) }}
          </template>
          <template #size_m2-cell="{ row }">
            {{ formatNumber(row.original.size_m2, { maximumFractionDigits: 1 }) }} m²
          </template>
          <template #price_eur-cell="{ row }">
            {{ formatCurrency(row.original.price_eur) }}
          </template>
          <template #price_per_m2-cell="{ row }">
            {{ formatCurrency(row.original.price_per_m2) }}
          </template>
        </UTable>
      </div>
    </section>
  </div>
</template>

<style scoped>
  .map-page {
    display: grid;
    gap: 1rem;
  }

  .panel {
    padding: 1.15rem;
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

  .filter-bar {
    display: grid;
    gap: 1rem;
  }

  .filter-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .filter-head h1 {
    margin: 0;
    font-family: var(--font-display);
  }

  .filter-stats {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .stat-chip {
    display: grid;
    gap: 0.2rem;
    padding: 0.7rem 0.9rem;
    border-radius: 1.1rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 90%, transparent),
      color-mix(in srgb, var(--primary) 6%, transparent)
    );
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 12%);
    min-width: 9rem;
  }

  .stat-chip span {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .stat-chip strong {
    font-size: 1.1rem;
  }

  .map-shell {
    position: relative;
    height: min(520px, 70vh);
    border-radius: 1.5rem;
    overflow: clip;
    border: 1px solid var(--border);
    background: var(--surface-soft);
  }

  .map-placeholder {
    height: 100%;
  }

  .map-legend {
    position: absolute;
    top: 1rem;
    right: 1rem;
    z-index: 1000;
    display: grid;
    gap: 0.5rem;
    padding: 0.85rem 1rem;
    border-radius: 1.1rem;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface-strong) 92%, transparent);
    backdrop-filter: blur(8px);
    box-shadow: 0 12px 22px rgb(15 23 42 / 12%);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    font-size: 0.82rem;
  }

  .dot {
    display: block;
    width: 0.8rem;
    height: 0.8rem;
    border-radius: 999px;
    border: 1.5px solid #fff;
  }

  .dot-low {
    background: #22c55e;
  }
  .dot-mid {
    background: #f59e0b;
  }
  .dot-high {
    background: #ef4444;
  }

  .detail-panel {
    display: grid;
    gap: 1rem;
    padding: 1.25rem;
    border-radius: 1.5rem;
    border: 1px solid color-mix(in srgb, var(--primary) 20%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--primary) 8%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .detail-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .detail-head h2 {
    margin: 0.25rem 0 0;
    font-family: var(--font-display);
    font-size: 1.5rem;
  }

  .detail-kpis {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .detail-meta {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-size: 0.88rem;
  }

  .detail-actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .slide-panel-enter-active,
  .slide-panel-leave-active {
    transition:
      opacity 200ms ease,
      transform 200ms ease;
  }

  .slide-panel-enter-from,
  .slide-panel-leave-to {
    opacity: 0;
    transform: translateY(-8px);
  }

  @media (max-width: 900px) {
    .filter-head {
      flex-direction: column;
    }

    .detail-kpis {
      grid-template-columns: 1fr 1fr;
    }
  }
</style>
