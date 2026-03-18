<script setup lang="ts">
  definePageMeta({ middleware: ['auth'] })

  const { t } = useI18n()
  const route = useRoute()
  const router = useRouter()
  const stats = useStatsStore()
  const api = useApi()

  // ---- Form state (persisted via useLocalStorage) ----
  const savedForm = useLocalStorage('napoved-form', {
    property_type: 'stanovanje',
    municipality: '',
    size_m2: null as number | null,
    uporabna_povrsina: null as number | null,
    rooms: null as number | null,
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
    latitude: null as number | null,
    longitude: null as number | null,
  })

  const form = reactive({ ...savedForm.value })
  watch(
    form,
    (v) => {
      Object.assign(savedForm.value, v)
    },
    { deep: true },
  )

  // ---- UI state ----
  const loading = ref(false)
  const contextLoading = ref(false)
  const error = ref('')
  const formErrors = ref<Record<string, string>>({})
  const showAdvancedLocation = ref(false)
  const result = ref<any>(null)
  const history = ref<any[]>([])

  // ---- Municipality autocomplete ----
  const allMunicipalities = ref<any[]>([])
  const municipalityQuery = ref(form.municipality)
  const municipalityOptions = computed(() => {
    const q = municipalityQuery.value.trim().toLowerCase()
    const list = q
      ? allMunicipalities.value.filter((m: any) => m.municipality.toLowerCase().includes(q))
      : allMunicipalities.value
    return list.slice(0, 14).map((m: any) => ({
      label: m.municipality,
      value: m.municipality,
    }))
  })

  watch(municipalityQuery, (v) => {
    form.municipality = v
  })

  // ---- Derived ----
  const municipalityIndex = computed(
    () => new Map(allMunicipalities.value.map((m: any) => [m.municipality.toLowerCase(), m])),
  )
  const selectedMunicipalityMeta = computed(() =>
    municipalityIndex.value.get(form.municipality.toLowerCase()),
  )
  const effectiveSize = computed(() => form.uporabna_povrsina || form.size_m2)
  const municipalityContext = computed(() => (stats as any).municipalityDetail)
  const comparables = computed(() => (stats as any).comparables)
  const comparableRows = computed(() => comparables.value?.items || [])
  const comparablesCountLabel = computed(
    () => `${comparables.value?.summary?.count || 0} ${t('dashboard.transactions')}`,
  )

  // ---- Property types ----
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
    propertyTypes.map((v) => ({ label: getPropertyTypeLabel(v, t), value: v })),
  )

  // ---- Location options ----
  const legaOptions = computed(() => [
    { label: t('common.noData'), value: '_none' },
    ...['pritlicje', 'nadstropje', 'klet', 'unknown'].map((o) => ({
      label: t(`predict.lega.${o}`),
      value: o,
    })),
  ])

  // ---- Flags ----
  const flags = computed(() => [
    { key: 'novogradnja', label: t('predict.novogradnja') },
    { key: 'has_garaza', label: t('predict.hasGaraza') },
    { key: 'has_klet', label: t('predict.hasKlet') },
    { key: 'has_shramba', label: t('predict.hasShramba') },
    { key: 'has_terasa', label: t('predict.hasTerasa') },
    { key: 'stavba_je_dokoncana', label: t('predict.stavbaDokoncana') },
    { key: 'ddv_vkljucen', label: t('predict.ddvVkljucen') },
  ])

  // ---- Validation ----
  function validate() {
    const errors: Record<string, string> = {}
    if (!form.size_m2 || form.size_m2 <= 0) errors.size_m2 = t('validation.minSize')
    if (!form.municipality?.trim()) errors.municipality = t('validation.required')
    formErrors.value = errors
    return Object.keys(errors).length === 0
  }

  // ---- API calls ----
  async function fetchMunicipalities() {
    try {
      const { data } = await api.get('/api/regions/municipalities')
      allMunicipalities.value = (data as any) || []
    } catch {
      allMunicipalities.value = []
    }
  }

  async function fetchHistory() {
    try {
      const { data } = await api.get('/api/predict/history', { params: { per_page: 12 } })
      history.value = (data as any)?.items || []
    } catch {
      history.value = []
    }
  }

  async function loadContext(estimatedPrice?: number) {
    if (!form.municipality || !form.property_type || !effectiveSize.value) {
      if ((stats as any).resetComparables) (stats as any).resetComparables()
      if ((stats as any).resetMunicipalityDetail) (stats as any).resetMunicipalityDetail()
      return
    }
    contextLoading.value = true
    try {
      const slug = form.municipality.toLowerCase().replace(/\s+/g, '-')
      await Promise.all([
        (stats as any).fetchMunicipalityDetail?.(slug),
        (stats as any).fetchComparables?.({
          municipality: form.municipality,
          property_type: form.property_type,
          size_m2: effectiveSize.value,
          year_built: form.year_built || undefined,
          price_eur: estimatedPrice || undefined,
          limit: 8,
        }),
      ])
    } catch {
      if ((stats as any).resetComparables) (stats as any).resetComparables()
      if ((stats as any).resetMunicipalityDetail) (stats as any).resetMunicipalityDetail()
    } finally {
      contextLoading.value = false
    }
  }

  async function predict() {
    if (!validate()) return
    loading.value = true
    error.value = ''
    result.value = null

    try {
      const payload: Record<string, unknown> = {}
      for (const [key, value] of Object.entries(form)) {
        if (value !== null && value !== '' && value !== undefined && value !== '_none') {
          payload[key] = value
        }
      }
      const { data } = await api.post('/api/predict', payload)
      result.value = data
      await Promise.all([fetchHistory(), loadContext((data as any).predicted_price_eur)])
    } catch (err) {
      error.value = getApiErrorMessage(err, t)
    } finally {
      loading.value = false
    }
  }

  function reuseComparable(item: any) {
    router.push({
      path: '/napoved',
      query: {
        municipality: item.municipality,
        property_type: item.property_type || form.property_type,
        size_m2: item.size_m2 || '',
        year_built: item.year_built || '',
        price_eur: item.price_eur || '',
      },
    })
  }

  function applyRouteQuery(q: Record<string, any>) {
    if (q.municipality) form.municipality = String(q.municipality)
    if (q.property_type) form.property_type = String(q.property_type)
    for (const field of ['size_m2', 'year_built'] as const) {
      if (q[field]) {
        const n = Number(q[field])
        if (!Number.isNaN(n)) (form as any)[field] = n
      }
    }
    if (q.price_eur) {
      const n = Number(q.price_eur)
      if (!Number.isNaN(n)) {
        result.value = { predicted_price_eur: n, model_used: 'prefill', features_used: {} }
      }
    }
  }

  watch(() => route.query, applyRouteQuery, { immediate: true })

  useLazyAsyncData('napoved-init', async () => {
    await Promise.all([fetchHistory(), fetchMunicipalities()])
    if (form.municipality && effectiveSize.value) {
      await loadContext(result.value?.predicted_price_eur || undefined)
    }
  })
</script>

<template>
  <div class="prediction-page">
    <section class="prediction-shell">
      <!-- Left: Input form -->
      <article class="panel input-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{{ t('predict.title') }}</p>
            <h1>{{ t('predict.avmTitle') }}</h1>
            <p class="muted">{{ t('predict.avmBody') }}</p>
          </div>
        </div>

        <form class="predict-form" @submit.prevent="predict">
          <!-- Basic inputs -->
          <div class="form-section">
            <h2>{{ t('predict.subjectBasics') }}</h2>
            <div class="form-grid">
              <label class="field">
                <span class="form-label">{{ t('predict.size') }} *</span>
                <UInput
                  v-model.number="form.size_m2"
                  type="number"
                  :min="1"
                  :placeholder="t('predict.size')"
                  :color="formErrors.size_m2 ? 'error' : undefined"
                  @input="formErrors.size_m2 = ''"
                />
                <small v-if="formErrors.size_m2" class="field-error">{{
                  formErrors.size_m2
                }}</small>
              </label>

              <label class="field">
                <span class="form-label">{{ t('predict.uporabnaPovrsina') }}</span>
                <UInput
                  v-model.number="form.uporabna_povrsina"
                  type="number"
                  :min="0"
                  :placeholder="t('predict.uporabnaPovrsina')"
                />
              </label>

              <label class="field">
                <span class="form-label">{{ t('predict.rooms') }}</span>
                <UInput
                  v-model.number="form.rooms"
                  type="number"
                  :min="0"
                  :placeholder="t('predict.rooms')"
                />
              </label>

              <label class="field">
                <span class="form-label">{{ t('predict.yearBuilt') }}</span>
                <UInput
                  v-model.number="form.year_built"
                  type="number"
                  :min="1800"
                  :max="2030"
                  :placeholder="t('predict.yearBuilt')"
                />
              </label>

              <label class="field">
                <span class="form-label">{{ t('predict.floor') }}</span>
                <UInput
                  v-model.number="form.floor"
                  type="number"
                  :min="-2"
                  :max="60"
                  :placeholder="t('predict.floor')"
                />
              </label>

              <label class="field">
                <span class="form-label">{{ t('predict.propertyType') }}</span>
                <USelect v-model="form.property_type" :items="propertyTypeOptions" />
              </label>
            </div>
          </div>

          <!-- Location -->
          <div class="form-section">
            <h2>{{ t('predict.locationContext') }}</h2>
            <div class="form-grid">
              <label class="field">
                <span class="form-label">{{ t('predict.municipality') }} *</span>
                <USelectMenu
                  v-model="municipalityQuery"
                  :items="municipalityOptions"
                  :search-input="{ placeholder: t('predict.municipalityPlaceholder') }"
                  value-key="value"
                  :color="formErrors.municipality ? 'error' : undefined"
                  @update:model-value="formErrors.municipality = ''"
                />
                <small v-if="formErrors.municipality" class="field-error">{{
                  formErrors.municipality
                }}</small>
              </label>

              <label class="field">
                <span class="form-label">{{ t('predict.legaVStavbi') }}</span>
                <USelect v-model="form.lega_v_stavbi" :items="legaOptions" />
              </label>

              <div class="field municipality-chip">
                <span class="form-label">{{ t('predict.marketContext') }}</span>
                <strong>{{
                  selectedMunicipalityMeta?.region || t('predict.coordsAutoHint')
                }}</strong>
                <small class="muted">
                  {{
                    selectedMunicipalityMeta?.region
                      ? t('predict.coordsAutoHint')
                      : t('predict.pickMunicipalityHint')
                  }}
                </small>
              </div>
            </div>

            <div class="advanced-toggle">
              <UButton
                type="button"
                icon="i-lucide-map-pin"
                :label="
                  showAdvancedLocation
                    ? t('predict.hideAdvancedLocation')
                    : t('predict.showAdvancedLocation')
                "
                color="neutral"
                variant="outline"
                size="sm"
                @click="showAdvancedLocation = !showAdvancedLocation"
              />
            </div>

            <div v-if="showAdvancedLocation" class="form-grid" style="margin-top: 0.85rem">
              <label class="field">
                <span class="form-label">{{ t('predict.latitude') }}</span>
                <UInput
                  v-model.number="form.latitude"
                  type="number"
                  step="0.0001"
                  :placeholder="t('predict.latitude')"
                />
              </label>
              <label class="field">
                <span class="form-label">{{ t('predict.longitude') }}</span>
                <UInput
                  v-model.number="form.longitude"
                  type="number"
                  step="0.0001"
                  :placeholder="t('predict.longitude')"
                />
              </label>
            </div>
          </div>

          <!-- Building flags -->
          <div class="form-section">
            <h2>{{ t('predict.buildingFlags') }}</h2>
            <div class="toggle-grid">
              <div
                v-for="flag in flags"
                :key="flag.key"
                class="toggle-chip"
                :class="{ active: (form as any)[flag.key] === 1 }"
              >
                <USwitch
                  :model-value="(form as any)[flag.key] === 1"
                  @update:model-value="(v: boolean) => ((form as any)[flag.key] = v ? 1 : 0)"
                />
                <span>{{ flag.label }}</span>
              </div>
            </div>
          </div>

          <UAlert
            v-if="error"
            :description="error"
            color="error"
            variant="soft"
            icon="i-lucide-alert-circle"
          />

          <div class="form-actions">
            <UButton
              type="submit"
              icon="i-lucide-bolt"
              :loading="loading"
              :label="loading ? t('common.loading') : t('predict.predictButton')"
              size="lg"
            />
          </div>
        </form>
      </article>

      <!-- Right: Results panel -->
      <article class="panel story-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">{{ t('predict.result') }}</p>
            <h2>{{ t('predict.valuationStory') }}</h2>
            <p class="muted">{{ t('predict.valuationBody') }}</p>
          </div>
        </div>

        <!-- Loading indicator -->
        <div v-if="loading || contextLoading" class="story-block">
          <div class="inline-loading">
            <USkeleton class="h-16 w-full rounded-xl" />
            <USkeleton class="h-8 w-2/3 rounded-xl mt-3" />
          </div>
        </div>

        <template v-else-if="result">
          <!-- Estimate card -->
          <section class="estimate-card">
            <span>{{ t('predict.predictedPrice') }}</span>
            <strong>{{ formatCurrency(result.predicted_price_eur) }}</strong>
            <p>{{ t('predict.modelUsed') }}: {{ result.model_used }}</p>
          </section>

          <!-- Features used -->
          <section class="story-block">
            <div class="story-head">
              <h3>{{ t('predict.featuresUsed') }}</h3>
              <UButton variant="link" size="xs" @click="loadContext(result.predicted_price_eur)">
                {{ t('common.retry') }}
              </UButton>
            </div>
            <div class="chip-grid">
              <span v-for="(value, key) in result.features_used" :key="key" class="data-chip">
                {{ key }}: {{ value }}
              </span>
            </div>
          </section>

          <!-- Municipality context -->
          <section v-if="municipalityContext" class="story-block context-card">
            <div class="story-head">
              <h3>{{ t('predict.marketContext') }}</h3>
              <NuxtLink
                v-if="municipalityContext.slug"
                :to="`/obcine/${municipalityContext.slug}`"
                class="ghost-link"
              >
                {{ t('predict.openMunicipality') }}
              </NuxtLink>
            </div>
            <div class="context-metrics">
              <article>
                <span>{{ t('dashboard.medianPrice') }}</span>
                <strong>{{ formatCurrency(municipalityContext.overview?.median_price) }}</strong>
              </article>
              <article>
                <span>{{ t('dashboard.pricePerM2') }}</span>
                <strong>{{
                  formatCurrency(municipalityContext.overview?.median_price_per_m2)
                }}</strong>
              </article>
              <article>
                <span>{{ t('dashboard.transactions') }}</span>
                <strong>{{ formatNumber(municipalityContext.overview?.count) }}</strong>
              </article>
            </div>
          </section>

          <!-- Comparables -->
          <section class="story-block">
            <div class="story-head">
              <h3>{{ t('predict.comparablesTitle') }}</h3>
              <small class="muted">{{ comparablesCountLabel }}</small>
            </div>
            <div v-if="comparableRows.length" class="comparables-list">
              <article
                v-for="item in comparableRows"
                :key="`${item.slug}-${item.price_eur}-${item.size_m2}`"
                class="comparable-card"
              >
                <div class="comparable-head">
                  <strong>{{ item.municipality }}</strong>
                  <span class="muted">{{ item.year || '—' }}</span>
                </div>
                <p class="muted">
                  {{ getPropertyTypeLabel(item.property_type, t) || '—' }} ·
                  {{ formatNumber(item.size_m2, { maximumFractionDigits: 1 }) }} m² ·
                  {{ formatCurrency(item.price_per_m2) }}/m²
                </p>
                <div class="comparable-foot">
                  <strong>{{ formatCurrency(item.price_eur) }}</strong>
                  <small class="muted"
                    >{{ t('predict.similarityLabel') }} {{ item.similarity_score }}</small
                  >
                </div>
                <UButton size="xs" icon="i-lucide-repeat" @click="reuseComparable(item)">
                  {{ t('predict.reuseComparable') }}
                </UButton>
              </article>
            </div>
            <p v-else class="muted">{{ t('predict.noComparables') }}</p>
          </section>
        </template>

        <div v-else class="story-block empty-state">
          <UIcon name="i-lucide-home" class="w-10 h-10 text-[var(--text-muted)]" />
          <p class="muted">{{ t('predict.emptyState') }}</p>
        </div>

        <!-- History -->
        <section class="story-block history-block">
          <div class="story-head">
            <h3>{{ t('predict.history') }}</h3>
          </div>
          <div v-if="history.length" class="history-list">
            <article v-for="item in history" :key="item.id" class="history-card">
              <div>
                <strong>{{ item.payload?.municipality || '—' }}</strong>
                <small class="muted">{{ formatDate(item.created_at) }}</small>
              </div>
              <div class="history-metric">
                <strong>{{ formatCurrency(item.predicted_price_eur) }}</strong>
                <small class="muted">{{
                  getPropertyTypeLabel(item.payload?.property_type, t) || '—'
                }}</small>
              </div>
            </article>
          </div>
          <p v-else class="muted">{{ t('predict.noHistory') }}</p>
        </section>
      </article>
    </section>
  </div>
</template>

<style scoped>
  .prediction-page {
    display: grid;
  }

  .prediction-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
    gap: 1.1rem;
  }

  .panel {
    border-radius: var(--radius-lg);
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-strong) 88%, transparent),
      color-mix(in srgb, var(--surface-soft) 84%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      var(--shadow-sm);
  }

  .input-panel,
  .story-panel {
    padding: 1.3rem;
    display: grid;
    gap: 1rem;
    align-content: start;
  }

  .panel-head {
    margin-bottom: 0.25rem;
  }

  .panel-head h1 {
    margin: 0.3rem 0 0.4rem;
    font-family: var(--font-display);
    font-size: clamp(1.35rem, 1rem + 1vw, 1.9rem);
    letter-spacing: -0.03em;
  }

  .panel-head h2 {
    margin: 0.3rem 0 0.4rem;
    font-family: var(--font-display);
    font-size: clamp(1.25rem, 0.9rem + 0.9vw, 1.7rem);
    letter-spacing: -0.03em;
  }

  .panel-head p {
    margin: 0;
  }

  .predict-form {
    display: grid;
    gap: 1.1rem;
  }

  .form-section {
    display: grid;
    gap: 0.75rem;
  }

  .form-section h2 {
    margin: 0;
    font-size: 0.88rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .municipality-chip {
    align-content: flex-start;
    padding: 1rem 1.05rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    border-radius: 1.15rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 86%, transparent),
      color-mix(in srgb, var(--surface-muted) 78%, transparent)
    );
  }

  .municipality-chip strong {
    font-size: 1rem;
  }

  .advanced-toggle {
    display: flex;
    justify-content: flex-start;
    margin-top: 0.5rem;
  }

  /* Toggle flags */
  .toggle-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 0.7rem;
  }

  .toggle-chip {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    min-height: 3.2rem;
    padding: 0.8rem 0.95rem;
    border-radius: 1.1rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft) 82%, transparent),
      color-mix(in srgb, var(--surface-muted) 80%, transparent)
    );
    font-weight: 600;
    line-height: 1.25;
    cursor: pointer;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 12px 20px rgb(15 23 42 / 5%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease,
      box-shadow 160ms ease;
  }

  .toggle-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 28%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 18px 28px rgb(15 23 42 / 10%);
  }

  .toggle-chip.active {
    border-color: color-mix(in srgb, var(--primary) 34%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 16%, transparent),
      color-mix(in srgb, var(--secondary) 12%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 18px 30px rgb(15 23 42 / 12%);
  }

  .form-actions {
    display: flex;
    justify-content: flex-start;
  }

  /* Story panel */
  .story-panel {
    gap: 1rem;
  }

  .story-block {
    padding: 1.05rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    border-radius: 1.35rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-strong) 90%, transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 16px 28px rgb(15 23 42 / 6%);
    display: grid;
    gap: 0.85rem;
  }

  .story-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }

  .story-head h3 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1rem;
  }

  .estimate-card {
    padding: 1.25rem;
    border-radius: 1.5rem;
    background:
      radial-gradient(
        circle at top left,
        color-mix(in srgb, var(--primary) 28%, transparent),
        transparent 32%
      ),
      radial-gradient(
        circle at bottom right,
        color-mix(in srgb, var(--secondary) 18%, transparent),
        transparent 26%
      ),
      linear-gradient(
        145deg,
        color-mix(in srgb, var(--ui-bg-inverted) 88%, var(--ui-bg) 12%),
        color-mix(in srgb, var(--ui-bg-inverted) 80%, transparent)
      );
    color: var(--ui-text-inverted);
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 26px 56px rgb(15 23 42 / 24%);
  }

  .estimate-card span {
    display: inline-block;
    margin-bottom: 0.35rem;
    color: color-mix(in srgb, var(--ui-text-inverted) 72%, transparent);
    font-size: 0.82rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .estimate-card strong {
    display: block;
    font-size: clamp(2rem, 4vw, 3rem);
    line-height: 1.05;
  }

  .estimate-card p {
    margin: 0.45rem 0 0;
    color: color-mix(in srgb, var(--ui-text-inverted) 76%, transparent);
    font-size: 0.88rem;
  }

  .chip-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .data-chip {
    display: inline-flex;
    padding: 0.4rem 0.7rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-subtle) 92%, transparent),
      color-mix(in srgb, var(--primary) 7%, transparent)
    );
    font-size: 0.8rem;
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 12%);
  }

  .context-card {
    border-color: color-mix(in srgb, var(--primary) 14%, var(--border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--primary) 8%, transparent),
      color-mix(in srgb, var(--secondary) 9%, transparent)
    );
  }

  .context-metrics {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .context-metrics article span {
    display: block;
    margin-bottom: 0.25rem;
    font-size: 0.8rem;
    color: var(--text-soft);
  }

  .context-metrics article strong {
    display: block;
    font-size: 1.05rem;
  }

  .comparables-list {
    display: grid;
    gap: 0.8rem;
  }

  .comparable-card {
    display: grid;
    gap: 0.4rem;
    padding: 1rem;
    border-radius: 1.2rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-muted) 90%, transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 12%),
      0 12px 22px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      box-shadow 160ms ease;
  }

  .comparable-card:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--primary) 24%, var(--border));
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 30px rgb(15 23 42 / 10%);
  }

  .comparable-head,
  .comparable-foot {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .comparable-card p {
    margin: 0;
    font-size: 0.88rem;
  }
  .comparable-foot strong {
    display: block;
    font-size: 1.05rem;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    padding: 2rem;
    text-align: center;
  }

  .history-list {
    display: grid;
    gap: 0.7rem;
  }

  .history-card {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.9rem 1rem;
    border-radius: 1.1rem;
    border: 1px solid color-mix(in srgb, var(--border) 92%, transparent);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--surface-soft-muted) 90%, transparent),
      color-mix(in srgb, var(--surface-soft) 82%, transparent)
    );
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 12%);
  }

  .history-card strong {
    display: block;
    font-size: 0.9rem;
  }
  .history-card small {
    display: block;
    font-size: 0.78rem;
    margin-top: 0.15rem;
  }
  .history-metric {
    text-align: right;
  }
  .history-metric strong {
    font-size: 1rem;
  }

  @media (max-width: 1100px) {
    .prediction-shell {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 720px) {
    .form-grid,
    .context-metrics {
      grid-template-columns: 1fr;
    }
    .input-panel,
    .story-panel {
      padding: 1rem;
    }
    .toggle-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
