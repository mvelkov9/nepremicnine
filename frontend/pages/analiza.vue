<script setup lang="ts">
  definePageMeta({ middleware: ['auth'] })

  const { t } = useI18n()
  const auth = useAuthStore()
  const api = useApi()

  // Mode tabs
  const tabItems = computed(() => [
    { label: t('analysis.guidedCheck'), slot: 'guided' },
    ...(auth.isAdmin ? [{ label: t('analysis.bulkMode'), slot: 'bulk' }] : []),
  ])

  // Guided form
  const guidedForm = reactive({
    municipality: '',
    property_type: 'stanovanje',
    size_m2: 65 as number | null,
    uporabna_povrsina: null as number | null,
    rooms: 2.5 as number | null,
    year_built: null as number | null,
    floor: null as number | null,
    lega_v_stavbi: '_none',
    novogradnja: 0,
    has_garaza: 0,
    has_klet: 0,
    has_shramba: 0,
    has_terasa: 0,
    stavba_je_dokoncana: 1,
    ddv_vkljucen: 0,
    asking_price: null as number | null,
    notes: '',
  })

  const threshold = ref(15)
  const loading = ref(false)
  const error = ref('')
  const result = ref<any>(null)
  const advancedJson = ref('')

  // Municipality autocomplete
  const allMunicipalities = ref<any[]>([])
  const municipalityQuery = ref('')
  const municipalityOptions = computed(() => {
    const q = municipalityQuery.value.trim().toLowerCase()
    const list = q
      ? allMunicipalities.value.filter((m: any) => m.municipality.toLowerCase().includes(q))
      : allMunicipalities.value
    return list.slice(0, 14).map((m: any) => ({ label: m.municipality, value: m.municipality }))
  })

  watch(municipalityQuery, (v) => {
    guidedForm.municipality = v
  })

  // Property types
  const propertyTypes = [
    'stanovanje',
    'hisa',
    'poslovni_prostor',
    'industrijski',
    'turisticni',
    'gostinstvo',
    'garaza',
    'kmetijsko',
  ]
  const propertyTypeOptions = computed(() =>
    propertyTypes.map((value) => ({ label: getPropertyTypeLabel(value, t), value })),
  )

  const legaOptions = computed(() => [
    { label: t('common.noData'), value: '_none' },
    ...['pritlicje', 'nadstropje', 'klet', 'unknown'].map((o) => ({
      label: t(`predict.lega.${o}`),
      value: o,
    })),
  ])

  const flags = [
    { key: 'novogradnja', label: 'novogradnja' },
    { key: 'has_garaza', label: 'hasGaraza' },
    { key: 'has_klet', label: 'hasKlet' },
    { key: 'has_shramba', label: 'hasShramba' },
    { key: 'has_terasa', label: 'hasTerasa' },
    { key: 'stavba_je_dokoncana', label: 'stavbaDokoncana' },
    { key: 'ddv_vkljucen', label: 'ddvVkljucen' },
  ]

  // Results
  const primaryListing = computed(() => result.value?.listings?.[0] ?? null)
  const resultColumns = [
    { accessorKey: 'municipality', header: t('dashboard.municipality') },
    { accessorKey: 'property_type', header: t('predict.propertyType') },
    { accessorKey: 'size_m2', header: t('predict.size') },
    { accessorKey: 'floor', header: t('predict.floor') },
    { accessorKey: 'asking_price', header: t('analysis.askingPrice') },
    { accessorKey: 'predicted_price', header: t('analysis.predictedPrice') },
    { accessorKey: 'deviation_percent', header: t('analysis.deviation') },
    { accessorKey: 'label', header: t('analysis.label'), enableSorting: false },
  ]

  function labelColor(label: string): 'error' | 'success' | 'info' {
    if (label === 'overpriced') return 'error'
    if (label === 'underpriced') return 'success'
    return 'info'
  }

  function labelText(label: string): string {
    if (label === 'market_aligned') return t('analysis.marketAligned')
    return t(`analysis.${label}`) ?? label
  }

  function buildGuidedPayload() {
    return Object.fromEntries(
      Object.entries(guidedForm).filter(
        ([key, value]) => key !== 'notes' && value !== null && value !== '' && value !== '_none',
      ),
    )
  }

  async function fetchMunicipalities() {
    try {
      const { data } = await api.get('/api/regions/municipalities')
      allMunicipalities.value = (data as any) ?? []
    } catch {
      allMunicipalities.value = []
    }
  }

  async function analyzeGuided() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const { data } = await api.post('/api/analysis/score', {
        listings: [buildGuidedPayload()],
        threshold: threshold.value,
      })
      result.value = data
    } catch (e) {
      error.value = getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  async function analyzeAdvanced() {
    loading.value = true
    error.value = ''
    result.value = null
    try {
      const parsed = JSON.parse(advancedJson.value)
      const listings = Array.isArray(parsed) ? parsed : [parsed]
      const { data } = await api.post('/api/analysis/score', {
        listings,
        threshold: threshold.value,
      })
      result.value = data
    } catch (e) {
      error.value = e instanceof SyntaxError ? t('analysis.invalidJson') : getApiErrorMessage(e, t)
    } finally {
      loading.value = false
    }
  }

  function loadSample() {
    advancedJson.value = JSON.stringify(
      [
        {
          size_m2: 65,
          uporabna_povrsina: 60,
          rooms: 2.5,
          year_built: 2005,
          floor: 3,
          municipality: 'Ljubljana',
          property_type: 'stanovanje',
          has_terasa: 1,
          asking_price: 250000,
        },
        {
          size_m2: 120,
          uporabna_povrsina: 114,
          rooms: 4,
          year_built: 1990,
          floor: 1,
          municipality: 'Maribor',
          property_type: 'hisa',
          has_garaza: 1,
          asking_price: 180000,
        },
      ],
      null,
      2,
    )
  }

  await useAsyncData('analiza-init', fetchMunicipalities)
</script>

<template>
  <div class="analysis-page">
    <!-- Hero -->
    <section class="panel hero-shell">
      <div>
        <p class="eyebrow">{{ t('analysis.consumerKicker') }}</p>
        <h1>{{ t('analysis.consumerTitle') }}</h1>
        <p class="muted">{{ t('analysis.consumerBody') }}</p>
      </div>
    </section>

    <!-- Tabs -->
    <UTabs :items="tabItems">
      <!-- Guided tab -->
      <template #guided>
        <section class="panel" style="margin-top: 1rem">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('analysis.guidedCheck') }}</p>
              <h2>{{ t('analysis.guidedTitle') }}</h2>
            </div>
            <div class="threshold-field">
              <label class="form-label">{{ t('analysis.threshold') }}</label>
              <UInput v-model.number="threshold" type="number" :min="1" :max="100" />
            </div>
          </div>

          <div class="form-grid">
            <label class="field">
              <span class="form-label">{{ t('predict.municipality') }}</span>
              <USelectMenu
                v-model="municipalityQuery"
                :items="municipalityOptions"
                :search-input="{ placeholder: t('predict.municipalityPlaceholder') }"
                value-key="value"
              />
            </label>

            <label class="field">
              <span class="form-label">{{ t('predict.propertyType') }}</span>
              <USelect v-model="guidedForm.property_type" :items="propertyTypeOptions" />
            </label>

            <label class="field">
              <span class="form-label">{{ t('predict.size') }}</span>
              <UInput v-model.number="guidedForm.size_m2" type="number" :min="1" />
            </label>

            <label class="field">
              <span class="form-label">{{ t('predict.uporabnaPovrsina') }}</span>
              <UInput v-model.number="guidedForm.uporabna_povrsina" type="number" :min="0" />
            </label>

            <label class="field">
              <span class="form-label">{{ t('predict.rooms') }}</span>
              <UInput v-model.number="guidedForm.rooms" type="number" :min="0" :step="0.5" />
            </label>

            <label class="field">
              <span class="form-label">{{ t('predict.yearBuilt') }}</span>
              <UInput
                v-model.number="guidedForm.year_built"
                type="number"
                :min="1800"
                :max="2100"
              />
            </label>

            <label class="field">
              <span class="form-label">{{ t('predict.floor') }}</span>
              <UInput v-model.number="guidedForm.floor" type="number" :min="-2" :max="60" />
            </label>

            <label class="field">
              <span class="form-label">{{ t('predict.legaVStavbi') }}</span>
              <USelect v-model="guidedForm.lega_v_stavbi" :items="legaOptions" />
            </label>

            <label class="field">
              <span class="form-label">{{ t('analysis.askingPrice') }}</span>
              <UInput v-model.number="guidedForm.asking_price" type="number" :min="0" />
            </label>

            <label class="field" style="grid-column: span 2">
              <span class="form-label">{{ t('analysis.contextNotes') }}</span>
              <UInput v-model="guidedForm.notes" />
            </label>
          </div>

          <!-- Flags -->
          <div class="flag-row">
            <label
              v-for="flag in flags"
              :key="flag.key"
              class="focus-chip"
              :class="{ active: (guidedForm as any)[flag.key] === 1 }"
            >
              <input
                type="checkbox"
                class="sr-only"
                :checked="(guidedForm as any)[flag.key] === 1"
                @change="
                  (guidedForm as any)[flag.key] = (guidedForm as any)[flag.key] === 1 ? 0 : 1
                "
              />
              <span
                class="toggle-indicator"
                :class="{ on: (guidedForm as any)[flag.key] === 1 }"
                aria-hidden="true"
              />
              <span>{{ t(`predict.${flag.label}`) }}</span>
            </label>
          </div>

          <div class="actions-row">
            <UButton
              icon="i-lucide-search"
              :loading="loading"
              :label="t('analysis.analyzeButton')"
              @click="analyzeGuided"
            />
          </div>
        </section>
      </template>

      <!-- Bulk tab (admin only) -->
      <template v-if="auth.isAdmin" #bulk>
        <section class="panel" style="margin-top: 1rem">
          <div class="panel-head">
            <div>
              <p class="eyebrow subtle">{{ t('analysis.bulkMode') }}</p>
              <h2>{{ t('analysis.advancedTitle') }}</h2>
            </div>
          </div>

          <UTextarea
            v-model="advancedJson"
            :rows="8"
            :placeholder="t('analysis.jsonPlaceholder')"
            class="code-textarea"
          />

          <div class="actions-row">
            <UButton
              icon="i-lucide-file-code"
              color="neutral"
              variant="outline"
              :label="t('analysis.loadSample')"
              @click="loadSample"
            />
            <UButton
              icon="i-lucide-play"
              :loading="loading"
              :label="t('analysis.runBulk')"
              @click="analyzeAdvanced"
            />
          </div>
        </section>
      </template>
    </UTabs>

    <UAlert
      v-if="error"
      :description="error"
      color="error"
      variant="soft"
      icon="i-lucide-alert-circle"
    />

    <!-- Results -->
    <template v-if="result">
      <!-- Primary result summary -->
      <section v-if="primaryListing" class="result-band">
        <article class="result-card">
          <span>{{ t('analysis.askingPrice') }}</span>
          <strong>{{ formatCurrency(primaryListing.asking_price) }}</strong>
        </article>
        <article class="result-card">
          <span>{{ t('analysis.predictedPrice') }}</span>
          <strong>{{ formatCurrency(primaryListing.predicted_price) }}</strong>
        </article>
        <article class="result-card">
          <span>{{ t('analysis.deviation') }}</span>
          <strong
            >{{
              formatNumber(primaryListing.deviation_percent, { maximumFractionDigits: 1 })
            }}%</strong
          >
        </article>
        <article class="result-card">
          <span>{{ t('analysis.label') }}</span>
          <UBadge
            :label="labelText(primaryListing.label)"
            :color="labelColor(primaryListing.label)"
            variant="soft"
          />
        </article>
      </section>

      <!-- Full results table -->
      <section class="panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow subtle">{{ t('analysis.results') }}</p>
            <h2>{{ t('analysis.scoredListings') }}</h2>
          </div>
        </div>

        <div class="table-wrap">
          <UTable :columns="resultColumns" :data="result.listings ?? []">
            <template #property_type-cell="{ row }">
              {{ getPropertyTypeLabel(row.original.property_type, t) }}
            </template>
            <template #size_m2-cell="{ row }">
              {{
                formatNumber(row.original.uporabna_povrsina || row.original.size_m2, {
                  maximumFractionDigits: 1,
                })
              }}
              m²
            </template>
            <template #floor-cell="{ row }">
              {{ row.original.floor ?? '—' }}
            </template>
            <template #asking_price-cell="{ row }">
              {{ formatCurrency(row.original.asking_price) }}
            </template>
            <template #predicted_price-cell="{ row }">
              {{ formatCurrency(row.original.predicted_price) }}
            </template>
            <template #deviation_percent-cell="{ row }">
              {{ formatNumber(row.original.deviation_percent, { maximumFractionDigits: 1 }) }}%
            </template>
            <template #label-cell="{ row }">
              <UBadge
                :label="labelText(row.original.label)"
                :color="labelColor(row.original.label)"
                variant="soft"
              />
            </template>
          </UTable>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
  .analysis-page {
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

  .hero-shell {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
  }

  .hero-shell h1 {
    margin: 0;
    font-family: var(--font-display);
  }

  .threshold-field {
    min-width: 8rem;
    display: grid;
    gap: 0.35rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.9rem;
  }

  .field {
    display: grid;
    gap: 0.35rem;
  }

  .actions-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    margin-top: 1rem;
  }

  .flag-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .focus-chip {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.7rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 90%, transparent),
      color-mix(in srgb, var(--surface-muted) 82%, transparent)
    );
    color: var(--text);
    padding: 0.7rem 0.9rem;
    font-weight: 700;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 20px rgb(15 23 42 / 5%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease;
    cursor: pointer;
  }

  .focus-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
  }

  .focus-chip.active {
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 16%, transparent),
      color-mix(in srgb, var(--secondary) 11%, transparent)
    );
  }

  .toggle-indicator {
    width: 2.4rem;
    height: 1.4rem;
    border-radius: 999px;
    background: var(--surface-muted);
    border: 1px solid var(--border);
    position: relative;
    transition: background 160ms ease;
    flex-shrink: 0;
  }

  .toggle-indicator::after {
    content: '';
    position: absolute;
    top: 0.16rem;
    left: 0.16rem;
    width: 1rem;
    height: 1rem;
    border-radius: 999px;
    background: var(--surface-strong);
    box-shadow: 0 4px 8px rgb(15 23 42 / 14%);
    transition: transform 160ms ease;
  }

  .toggle-indicator.on {
    background: color-mix(in srgb, var(--primary) 22%, transparent);
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border));
  }

  .toggle-indicator.on::after {
    transform: translateX(1rem);
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .result-band {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .result-card {
    padding: 1rem;
    display: grid;
    gap: 0.35rem;
    border-radius: 1.35rem;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 92%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 16px 26px rgb(15 23 42 / 6%);
  }

  .result-card span {
    color: var(--text-muted);
    font-size: 0.84rem;
  }

  .result-card strong {
    font-size: 1.25rem;
  }

  .code-textarea {
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
  }

  @media (max-width: 900px) {
    .hero-shell {
      flex-direction: column;
      align-items: stretch;
    }
    .form-grid {
      grid-template-columns: 1fr;
    }
    .result-band {
      grid-template-columns: 1fr 1fr;
    }
  }
</style>
