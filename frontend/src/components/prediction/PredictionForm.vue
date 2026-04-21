<script setup lang="ts">
  import { onBeforeUnmount, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import AutoComplete from 'primevue/autocomplete'
  import Button from 'primevue/button'
  import InputNumber from 'primevue/inputnumber'
  import Select from 'primevue/select'
  import ToggleSwitch from 'primevue/toggleswitch'
  import EmptyState from '../EmptyState.vue'
  import api from '../../composables/useApi'
  import { useReferenceDataStore } from '../../stores/referenceData'
  import { useFormat } from '../../composables/useFormat'
  import { normalizeMunicipalityName } from '../../utils/municipality'
  import type { PredictionFormData } from './types'

  interface NaseljeOption {
    label: string
    naselje: string
    municipality: string
    region?: string | null
    latitude?: number | null
    longitude?: number | null
    sample_count?: number
  }

  type BinaryField =
    | 'novogradnja'
    | 'has_garaza'
    | 'has_klet'
    | 'has_shramba'
    | 'has_terasa'
    | 'stavba_je_dokoncana'
    | 'ddv_vkljucen'

  const form = defineModel<PredictionFormData>({ required: true })
  const props = defineProps<{
    loading: boolean
    error?: string
    municipalityRegion?: string
  }>()
  const emit = defineEmits<{ submit: [] }>()

  const { t } = useI18n()
  const referenceData = useReferenceDataStore()

  const propertyTypes = [
    'stanovanje',
    'hisa',
    'poslovni_prostor',
    'industrijski',
    'turisticni',
    'gostinstvo',
    'garaza',
    'kmetijsko',
    'parcela',
  ]

  const legaOptions = ['pritlicje', 'nadstropje', 'klet', 'unknown']

  const scenarioPresets = [
    {
      key: 'apartment',
      label: 'workbench.apartmentPreset',
      values: {
        property_type: 'stanovanje',
        size_m2: 68,
        rooms: 2.5,
        floor: 3,
        stavba_je_dokoncana: 1,
      },
    },
    {
      key: 'house',
      label: 'workbench.housePreset',
      values: {
        property_type: 'hisa',
        size_m2: 150,
        rooms: 5,
        floor: 1,
        has_garaza: 1,
        stavba_je_dokoncana: 1,
      },
    },
    {
      key: 'newbuild',
      label: 'workbench.newBuildPreset',
      values: {
        property_type: 'stanovanje',
        size_m2: 82,
        rooms: 3,
        year_built: new Date().getFullYear(),
        novogradnja: 1,
        ddv_vkljucen: 1,
        stavba_je_dokoncana: 0,
      },
    },
  ]

  interface NaseljeApiItem {
    naselje: string
    municipality: string
    region?: string | null
    latitude?: number | null
    longitude?: number | null
    sample_count?: number
  }

  const municipalitySuggestions = ref<string[]>([])
  const naseljeSuggestions = ref<string[]>([])
  const naseljeOptions = ref<NaseljeOption[]>([])
  const showAdvancedLocation = ref(false)
  const formErrors = ref<{ size_m2?: string | null; location?: string | null }>({})
  let activeNaseljeController: AbortController | null = null
  let naseljeRequestToken = 0

  const { formatType } = useFormat()

  function toggleValue(field: BinaryField) {
    return form.value[field] === 1
  }

  function updateToggle(field: BinaryField, checked: boolean) {
    form.value[field] = checked ? 1 : 0
  }

  function applyScenario(values: Partial<PredictionFormData>) {
    form.value = { ...form.value, ...values }
  }

  function searchMunicipalities(event: { query: string }) {
    const query = normalizeMunicipalityName(event.query || '')
    municipalitySuggestions.value = query
      ? referenceData.municipalities
          .filter((item) => normalizeMunicipalityName(item.municipality).includes(query))
          .map((item) => item.municipality)
          .slice(0, 12)
      : referenceData.municipalities.map((item) => item.municipality).slice(0, 12)
  }

  async function searchNaselja(event: { query: string }) {
    const requestToken = ++naseljeRequestToken
    const query = String(event.query || '').trim()
    activeNaseljeController?.abort()
    const controller = new AbortController()
    activeNaseljeController = controller

    try {
      const { data } = await api.get<NaseljeApiItem[]>('/api/stats/naselja', {
        params: {
          q: query || undefined,
          municipality: form.value.municipality || undefined,
          limit: 12,
        },
        signal: controller.signal,
      })

      if (requestToken !== naseljeRequestToken || controller.signal.aborted) return

      naseljeOptions.value = (data || []).map((item) => ({
        ...item,
        label: `${item.naselje} (${item.municipality})`,
      }))
      naseljeSuggestions.value = naseljeOptions.value.map((item) => item.label)
    } catch {
      if (requestToken !== naseljeRequestToken || controller.signal.aborted) return
      naseljeOptions.value = []
      naseljeSuggestions.value = []
    } finally {
      if (activeNaseljeController === controller) {
        activeNaseljeController = null
      }
    }
  }

  function resolveSubjectSize() {
    const candidates = [form.value.size_m2, form.value.uporabna_povrsina]
    return candidates.find((value) => typeof value === 'number' && value > 0) ?? null
  }

  function validateAndSubmit() {
    const errors: { size_m2?: string | null; location?: string | null } = {}
    if (!resolveSubjectSize()) {
      errors.size_m2 = t('validation.minSize')
    }
    const hasLocationContext = Boolean(
      form.value.naselje?.trim() ||
      form.value.municipality?.trim() ||
      (form.value.latitude != null && form.value.longitude != null),
    )
    if (!hasLocationContext) {
      errors.location = t('validation.required')
    }
    formErrors.value = errors
    if (Object.keys(errors).length === 0) {
      emit('submit')
    }
  }

  watch(
    () => form.value.naselje,
    (value) => {
      formErrors.value.location = null
      const target = String(value || '')
        .trim()
        .toLowerCase()
      const match = naseljeOptions.value.find(
        (item) =>
          item.naselje.trim().toLowerCase() === target ||
          item.label.trim().toLowerCase() === target,
      )
      if (!match) return
      if (form.value.naselje !== match.naselje) {
        form.value.naselje = match.naselje
      }
      form.value.municipality = match.municipality
      if (form.value.latitude == null && match.latitude != null) {
        form.value.latitude = match.latitude
      }
      if (form.value.longitude == null && match.longitude != null) {
        form.value.longitude = match.longitude
      }
    },
  )

  watch(
    () => form.value.municipality,
    () => {
      naseljeRequestToken += 1
      activeNaseljeController?.abort()
      activeNaseljeController = null
      naseljeOptions.value = []
      naseljeSuggestions.value = []
    },
  )

  onBeforeUnmount(() => {
    activeNaseljeController?.abort()
  })

  defineExpose({ formErrors })
</script>

<template>
  <div class="scenario-row">
    <Button
      v-for="preset in scenarioPresets"
      :key="preset.key"
      severity="secondary"
      outlined
      :label="t(preset.label)"
      @click="applyScenario(preset.values)"
    />
  </div>

  <form class="predict-form" @submit.prevent="validateAndSubmit">
    <div class="form-section">
      <div class="section-intro">
        <div>
          <p class="section-eyebrow">{{ t('predict.subjectBasics') }}</p>
          <h2>{{ t('predict.subjectBasics') }}</h2>
        </div>
        <p class="section-copy">
          {{ t('predict.previewBody') }}
        </p>
      </div>
      <div class="form-grid">
        <label class="field">
          <span>{{ t('predict.size') }}</span>
          <InputNumber
            v-model="form.size_m2"
            input-class="form-input"
            :min="1"
            :min-fraction-digits="0"
            :max-fraction-digits="1"
            fluid
            :invalid="!!formErrors.size_m2"
            @update:model-value="formErrors.size_m2 = null"
          />
          <small class="field-help">Either size or usable area can satisfy validation.</small>
          <small v-if="formErrors.size_m2" class="field-error">{{ formErrors.size_m2 }}</small>
        </label>

        <label class="field">
          <span>{{ t('predict.uporabnaPovrsina') }}</span>
          <InputNumber
            v-model="form.uporabna_povrsina"
            input-class="form-input"
            :min="0"
            :min-fraction-digits="0"
            :max-fraction-digits="1"
            fluid
          />
          <small class="field-help">Used as the fallback size.</small>
        </label>

        <label class="field">
          <span>{{ t('predict.rooms') }}</span>
          <InputNumber
            v-model="form.rooms"
            input-class="form-input"
            :min="0"
            :min-fraction-digits="0"
            :max-fraction-digits="1"
            fluid
          />
        </label>

        <label class="field">
          <span>{{ t('predict.yearBuilt') }}</span>
          <InputNumber
            v-model="form.year_built"
            input-class="form-input"
            :min="1800"
            :max="2030"
            fluid
          />
        </label>

        <label class="field">
          <span>{{ t('predict.floor') }}</span>
          <InputNumber v-model="form.floor" input-class="form-input" :min="-2" :max="60" fluid />
        </label>

        <label class="field">
          <span>{{ t('predict.propertyType') }}</span>
          <Select
            v-model="form.property_type"
            :options="propertyTypes.map((item) => ({ label: formatType(item), value: item }))"
            option-label="label"
            option-value="value"
          />
        </label>
      </div>
    </div>

    <div class="form-section">
      <div class="section-intro">
        <div>
          <p class="section-eyebrow">{{ t('predict.locationContext') }}</p>
          <h2>{{ t('predict.locationContext') }}</h2>
        </div>
        <p class="section-copy">
          {{ t('predict.pickMunicipalityHint') }}
        </p>
      </div>
      <div class="form-grid">
        <label class="field">
          <span>{{ t('predict.naselje') }}</span>
          <AutoComplete
            v-model="form.naselje"
            :suggestions="naseljeSuggestions"
            :placeholder="t('predict.naseljePlaceholder')"
            input-class="form-input"
            dropdown
            :force-selection="false"
            fluid
            :invalid="!!formErrors.location"
            @complete="searchNaselja"
            @update:model-value="formErrors.location = null"
          />
          <small v-if="formErrors.location" class="field-error">{{ formErrors.location }}</small>
        </label>

        <label class="field">
          <span>{{ t('predict.municipality') }}</span>
          <AutoComplete
            v-model="form.municipality"
            :suggestions="municipalitySuggestions"
            :placeholder="t('predict.municipalityPlaceholder')"
            input-class="form-input"
            dropdown
            :force-selection="false"
            fluid
            @complete="searchMunicipalities"
            @update:model-value="formErrors.location = null"
          />
        </label>

        <label class="field">
          <span>{{ t('predict.legaVStavbi') }}</span>
          <Select
            v-model="form.lega_v_stavbi"
            :options="[
              { label: t('common.noData'), value: '' },
              ...legaOptions.map((option) => ({
                label: t(`predict.lega.${option}`),
                value: option,
              })),
            ]"
            option-label="label"
            option-value="value"
          />
        </label>

        <div class="field municipality-chip">
          <span>{{ t('predict.marketContext') }}</span>
          <strong>{{ municipalityRegion || t('predict.coordsAutoHint') }}</strong>
          <small class="muted">
            {{
              municipalityRegion ? t('predict.coordsAutoHint') : t('predict.pickMunicipalityHint')
            }}
          </small>
        </div>
      </div>

      <div class="advanced-toggle">
        <Button
          severity="secondary"
          outlined
          icon="pi pi-map-marker"
          :label="
            showAdvancedLocation
              ? t('predict.hideAdvancedLocation')
              : t('predict.showAdvancedLocation')
          "
          @click="showAdvancedLocation = !showAdvancedLocation"
        />
      </div>

      <div v-if="showAdvancedLocation" class="form-grid advanced-grid">
        <label class="field">
          <span>{{ t('predict.latitude') }}</span>
          <InputNumber
            v-model="form.latitude"
            input-class="form-input"
            :min-fraction-digits="0"
            :max-fraction-digits="4"
            fluid
            @update:model-value="formErrors.location = null"
          />
        </label>

        <label class="field">
          <span>{{ t('predict.longitude') }}</span>
          <InputNumber
            v-model="form.longitude"
            input-class="form-input"
            :min-fraction-digits="0"
            :max-fraction-digits="4"
            fluid
            @update:model-value="formErrors.location = null"
          />
        </label>
      </div>
    </div>

    <div class="form-section">
      <div class="section-intro">
        <div>
          <p class="section-eyebrow">{{ t('predict.buildingFlags') }}</p>
          <h2>{{ t('predict.buildingFlags') }}</h2>
        </div>
        <p class="section-copy">
          {{ t('predict.previewSignalsDetail') }}
        </p>
      </div>
      <div class="toggle-grid">
        <label class="toggle-chip">
          <ToggleSwitch
            :model-value="toggleValue('novogradnja')"
            @update:model-value="updateToggle('novogradnja', $event)"
          />
          <span>{{ t('predict.novogradnja') }}</span>
        </label>
        <label class="toggle-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_garaza')"
            @update:model-value="updateToggle('has_garaza', $event)"
          />
          <span>{{ t('predict.hasGaraza') }}</span>
        </label>
        <label class="toggle-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_klet')"
            @update:model-value="updateToggle('has_klet', $event)"
          />
          <span>{{ t('predict.hasKlet') }}</span>
        </label>
        <label class="toggle-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_shramba')"
            @update:model-value="updateToggle('has_shramba', $event)"
          />
          <span>{{ t('predict.hasShramba') }}</span>
        </label>
        <label class="toggle-chip">
          <ToggleSwitch
            :model-value="toggleValue('has_terasa')"
            @update:model-value="updateToggle('has_terasa', $event)"
          />
          <span>{{ t('predict.hasTerasa') }}</span>
        </label>
        <label class="toggle-chip">
          <ToggleSwitch
            :model-value="toggleValue('stavba_je_dokoncana')"
            @update:model-value="updateToggle('stavba_je_dokoncana', $event)"
          />
          <span>{{ t('predict.stavbaDokoncana') }}</span>
        </label>
        <label class="toggle-chip">
          <ToggleSwitch
            :model-value="toggleValue('ddv_vkljucen')"
            @update:model-value="updateToggle('ddv_vkljucen', $event)"
          />
          <span>{{ t('predict.ddvVkljucen') }}</span>
        </label>
      </div>
    </div>

    <div v-if="error" class="state-card" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
    </div>

    <div class="form-actions">
      <Button
        class="submit-btn"
        type="submit"
        icon="pi pi-bolt"
        :loading="loading"
        :label="loading ? t('common.loading') : t('predict.predictButton')"
      />
    </div>
  </form>
</template>

<style scoped>
  .scenario-row {
    display: flex;
    gap: 0.65rem;
    flex-wrap: wrap;
    margin: 0 0 1.15rem;
  }

  .predict-form,
  .form-section {
    display: grid;
    gap: 1rem;
  }

  .section-intro {
    display: flex;
    align-items: start;
    justify-content: space-between;
    gap: 1rem;
  }

  .section-eyebrow {
    margin: 0 0 0.2rem;
    color: var(--primary);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
  }

  .form-section h2 {
    margin: 0 0 0.15rem;
    font-size: 1rem;
    font-family: var(--font-display);
    letter-spacing: -0.02em;
  }

  .section-copy,
  .field-help {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.88rem;
    line-height: 1.45;
  }

  .form-section {
    padding: 1.15rem;
    border: 1px solid color-mix(in srgb, var(--border) 76%, var(--content-border-strong) 24%);
    border-radius: var(--radius-md);
    background: var(--surface-panel);
    box-shadow: var(--shadow-sm);
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
  }

  .field {
    display: grid;
    gap: 0.38rem;
    min-width: 0;
  }

  .field span {
    font-size: 0.8rem;
    font-weight: 800;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .field :deep(.p-autocomplete),
  .field :deep(.p-inputnumber),
  .field :deep(.p-select),
  .field :deep(.p-inputtext),
  .field :deep(textarea) {
    width: 100%;
  }

  .field :deep(.p-autocomplete),
  .field :deep(.p-inputnumber),
  .field :deep(.p-select) {
    min-height: 3.15rem;
  }

  .field :deep(.p-inputtext),
  .field :deep(.p-autocomplete-input),
  .field :deep(.p-inputnumber-input),
  .field :deep(.p-select-label) {
    min-height: 3.15rem;
    font-size: 1rem;
  }

  .field :deep(.p-select-label) {
    padding-block: 0.82rem;
  }

  .field :deep(textarea) {
    min-height: 8rem;
  }

  .municipality-chip {
    align-content: flex-start;
    min-height: 100%;
    padding: 0.95rem 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    border-radius: 1rem;
    background: var(--surface-subtle);
    box-shadow: var(--shadow-sm);
  }

  .municipality-chip strong {
    font-size: 1rem;
  }

  .advanced-toggle {
    display: flex;
    justify-content: flex-start;
  }

  .advanced-grid {
    margin-top: 0.85rem;
  }

  .toggle-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.7rem;
  }

  .toggle-chip {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.65rem;
    min-height: 3.4rem;
    padding: 0.85rem 0.95rem;
    border-radius: 1rem;
    border: 1px solid color-mix(in srgb, var(--border) 78%, var(--content-border-strong) 22%);
    background: var(--surface-subtle);
    box-shadow: var(--shadow-sm);
    font-weight: 600;
    line-height: 1.25;
    cursor: pointer;
    transition:
      border-color 0.18s ease,
      transform 0.18s ease,
      box-shadow 0.18s ease,
      background-color 0.18s ease;
  }

  .toggle-chip:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--primary) 22%, var(--border) 78%);
    box-shadow: var(--accent-shadow);
  }

  .toggle-chip :deep(.p-toggleswitch) {
    flex: 0 0 auto;
  }

  .toggle-chip :deep(.p-toggleswitch-slider) {
    border-radius: 999px;
  }

  .form-actions {
    display: flex;
    justify-content: flex-start;
    margin-top: 0.15rem;
  }

  .submit-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 11.5rem;
    justify-content: center;
    padding: 0.95rem 1.15rem;
    border-radius: 999px;
    border: 1px solid var(--primary-border);
    background: linear-gradient(135deg, var(--primary), var(--primary-strong));
    color: var(--primary-contrast);
    box-shadow: var(--accent-shadow);
  }

  .field-error {
    color: var(--danger);
  }

  @media (max-width: 720px) {
    .section-intro {
      align-items: start;
      flex-direction: column;
    }

    .scenario-row,
    .form-actions {
      width: 100%;
    }

    .scenario-row :deep(.p-button),
    .submit-btn {
      width: 100%;
    }

    .form-grid,
    .toggle-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
