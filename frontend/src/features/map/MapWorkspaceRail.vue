<script setup lang="ts">
  import { computed } from 'vue'
  import { useI18n } from 'vue-i18n'
  import FilterBar from '../../components/FilterBar.vue'
  import FilterField from '../../components/FilterField.vue'
  import SectionPanel from '../../components/SectionPanel.vue'

  interface MapChoiceOption {
    label: string
    value: string
  }

  interface MapBandOption {
    label: string
    value: string
    count: number
    range?: string
  }

  const viewMode = defineModel<'transactions' | 'overview'>('viewMode', { required: true })
  const selectedType = defineModel<string>('selectedType', { required: true })
  const selectedRegion = defineModel<string>('selectedRegion', { required: true })
  const selectedYear = defineModel<string>('selectedYear', { required: true })
  const selectedMunicipality = defineModel<string>('selectedMunicipality', { required: true })
  const selectedPriceBand = defineModel<string>('selectedPriceBand', { required: true })

  defineProps<{
    selectedFilterCount: number
    selectedFilterTag: string
    propertyTypeOptions: MapChoiceOption[]
    regionOptions: MapChoiceOption[]
    yearOptions: MapChoiceOption[]
    municipalityOptions: MapChoiceOption[]
    bandOptions: MapBandOption[]
    heroActionCanUse: boolean
    heroActionReason: string
  }>()

  const emit = defineEmits<{
    clearFilters: []
    openMarket: []
    openAnalysis: []
  }>()

  const { t } = useI18n()

  const modeOptions = computed(() => [
    { label: t('map.transactionView'), value: 'transactions' },
    { label: t('map.overviewMode'), value: 'overview' },
  ])

  const bandColors: Record<string, string> = {
    low: 'var(--success)',
    mid: 'var(--warning)',
    high: 'var(--danger)',
  }
</script>

<template>
  <aside class="map-rail">
    <SectionPanel :eyebrow="t('dashboard.activeFilters')" :title="t('map.filterTitle')" compact>
      <template #actions>
        <div class="map-filter-actions">
          <Tag
            :severity="selectedFilterCount > 0 ? 'contrast' : 'secondary'"
            :value="selectedFilterTag"
          />
          <Button
            severity="secondary"
            outlined
            icon="pi pi-filter-slash"
            :label="t('map.clearFilter')"
            @click="emit('clearFilters')"
          />
        </div>
      </template>

      <FilterBar :columns="5">
        <FilterField :label="t('map.viewMode')">
          <Select
            v-model="viewMode"
            :options="modeOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>

        <FilterField :label="t('map.propertyType')">
          <Select
            v-model="selectedType"
            :options="propertyTypeOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>

        <FilterField :label="t('map.regionFilter')">
          <Select
            v-model="selectedRegion"
            :options="regionOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>

        <FilterField :label="t('map.yearFilter')">
          <Select
            v-model="selectedYear"
            :options="yearOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>

        <FilterField :label="t('map.municipalityFilter')">
          <Select
            v-model="selectedMunicipality"
            :options="municipalityOptions"
            option-label="label"
            option-value="value"
          />
        </FilterField>
      </FilterBar>

      <div class="legend-strip">
        <Button
          v-for="band in bandOptions"
          :key="band.value || 'all'"
          class="legend-chip"
          :severity="selectedPriceBand === band.value ? undefined : 'secondary'"
          :outlined="selectedPriceBand !== band.value"
          :aria-pressed="selectedPriceBand === band.value"
          :aria-label="
            band.value
              ? `${band.label}${band.range ? ` ${band.range}` : ''} (${band.count})`
              : `${band.label} (${band.count})`
          "
          @click="selectedPriceBand = band.value"
        >
          <span
            v-if="band.value"
            class="legend-dot"
            :style="{ backgroundColor: bandColors[band.value] || 'var(--primary)' }"
          ></span>
          <span class="legend-copy">
            <strong>{{ band.label }}</strong>
            <small>{{ band.range || t('map.allBandsHint') }} | {{ band.count }}</small>
          </span>
        </Button>
      </div>
    </SectionPanel>

    <SectionPanel :eyebrow="t('common.explore')" :title="t('map.explorerTitle')" compact>
      <div class="map-explore-actions">
        <Button
          severity="secondary"
          outlined
          icon="pi pi-table"
          :label="t('market.viewMarket')"
          @click="emit('openMarket')"
        />
        <Button
          severity="secondary"
          outlined
          icon="pi pi-compass"
          :label="t('analysis.title')"
          :disabled="!heroActionCanUse"
          :title="heroActionReason || undefined"
          @click="emit('openAnalysis')"
        />
      </div>
    </SectionPanel>
  </aside>
</template>

<style scoped>
  .map-rail {
    display: grid;
    gap: 1rem;
    position: sticky;
    top: calc(var(--space-lg) + 0.25rem);
    align-self: start;
  }

  .map-filter-actions,
  .map-explore-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .legend-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
    gap: 0.75rem;
    align-items: stretch;
  }

  :deep(.legend-chip.p-button) {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.9rem 0.95rem;
    border-radius: var(--radius-sm);
    text-align: left;
    white-space: normal;
    height: auto;
  }

  :deep(.legend-chip.p-button:not(.p-button-outlined)) {
    border-color: color-mix(in srgb, var(--primary) 34%, transparent);
    box-shadow: 0 18px 36px color-mix(in srgb, var(--primary) 12%, transparent);
    color: var(--primary-contrast);
  }

  :deep(.legend-chip.p-button:not(.p-button-outlined) .p-button-label),
  :deep(.legend-chip.p-button:not(.p-button-outlined) .legend-copy strong) {
    color: var(--primary-contrast);
  }

  :deep(.legend-chip.p-button:not(.p-button-outlined) .legend-copy small) {
    color: color-mix(in srgb, var(--primary-contrast) 76%, transparent);
  }

  .legend-dot {
    width: 0.8rem;
    height: 0.8rem;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .legend-copy {
    display: grid;
    gap: 0.1rem;
  }

  .legend-copy strong {
    font-size: 0.9rem;
  }

  .legend-copy small {
    color: var(--text-muted);
  }

  @media (max-width: 1220px) {
    .map-rail {
      position: static;
    }
  }
</style>
