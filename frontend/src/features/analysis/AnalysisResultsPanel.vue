<script setup lang="ts">
  import { computed, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import IconField from 'primevue/iconfield'
  import InputIcon from 'primevue/inputicon'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import EmptyState from '../../components/EmptyState.vue'
  import SectionPanel from '../../components/SectionPanel.vue'
  import { useFormat } from '../../composables/useFormat'
  import type { AnalysisListing, AnalysisResultPayload, AnalysisSummaryCard } from './types'

  const props = defineProps<{
    eyebrow: string
    title: string
    result: AnalysisResultPayload
    primaryListing: AnalysisListing | null
    summaryCards: AnalysisSummaryCard[]
    comparisonUrl: string
  }>()

  const emit = defineEmits<{
    export: []
    'open-prediction': [listing: AnalysisListing]
    'open-municipality': [listing: AnalysisListing]
  }>()

  const { t } = useI18n()
  const { fmt, fmtCurrency, formatType } = useFormat()

  const search = ref('')
  const labelFilter = ref<'all' | 'market_aligned' | 'overpriced' | 'underpriced'>('all')

  const labelOptions = computed(() => [
    { label: 'All labels', value: 'all' },
    { label: t('analysis.marketAligned'), value: 'market_aligned' },
    { label: t('analysis.overpriced'), value: 'overpriced' },
    { label: t('analysis.underpriced'), value: 'underpriced' },
  ])

  const filteredListings = computed(() => {
    const query = search.value.trim().toLowerCase()
    return (props.result.listings || []).filter((item) => {
      if (labelFilter.value !== 'all' && item.label !== labelFilter.value) return false
      if (!query) return true
      return [
        item.municipality,
        item.naselje,
        item.property_type,
        item.label,
        item.floor == null ? '' : String(item.floor),
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(query))
    })
  })

  const hasFilters = computed(() => Boolean(search.value.trim() || labelFilter.value !== 'all'))

  function clearFilters() {
    search.value = ''
    labelFilter.value = 'all'
  }

  function labelSeverity(label?: string | null) {
    if (label === 'overpriced') return 'danger'
    if (label === 'underpriced') return 'success'
    return 'info'
  }

  function labelText(label?: string | null) {
    if (label === 'market_aligned') return t('analysis.marketAligned')
    if (!label) return t('common.noData')
    return t(`analysis.${label}`)
  }
</script>

<template>
  <SectionPanel :eyebrow="eyebrow" :title="title">
    <template #actions>
      <div class="analysis-results-toolbar">
        <IconField class="toolbar-search">
          <InputIcon class="pi pi-search" />
          <InputText v-model="search" :placeholder="t('common.search')" />
        </IconField>

        <Select
          v-model="labelFilter"
          class="toolbar-select"
          :options="labelOptions"
          option-label="label"
          option-value="value"
        />

        <Button
          severity="secondary"
          text
          icon="pi pi-filter-slash"
          :disabled="!hasFilters"
          :label="t('map.clearFilter')"
          @click="clearFilters"
        />

        <a :href="comparisonUrl" target="_blank" rel="noreferrer" class="toolbar-link">
          <Button
            severity="contrast"
            outlined
            icon="pi pi-external-link"
            :label="t('analysis.compareOnPortal')"
          />
        </a>

        <Button
          v-if="result.listings?.length"
          severity="secondary"
          outlined
          icon="pi pi-download"
          :label="t('analysis.export')"
          @click="emit('export')"
        />
      </div>
    </template>

    <section v-if="primaryListing" class="analysis-primary-band">
      <article class="analysis-primary-card">
        <span>{{ t('analysis.askingPrice') }}</span>
        <strong>{{ fmtCurrency(primaryListing.asking_price) }}</strong>
      </article>
      <article class="analysis-primary-card is-emphasis">
        <span>{{ t('analysis.predictedPrice') }}</span>
        <strong>{{ fmtCurrency(primaryListing.predicted_price) }}</strong>
      </article>
      <article class="analysis-primary-card is-warning">
        <span>{{ t('analysis.deviation') }}</span>
        <strong>{{ fmt(primaryListing.deviation_pct ?? primaryListing.deviation_percent, 1) }}%</strong>
      </article>
      <article class="analysis-primary-card">
        <span>{{ t('analysis.label') }}</span>
        <Tag
          :severity="labelSeverity(primaryListing.label)"
          :value="labelText(primaryListing.label)"
        />
      </article>
    </section>

    <div class="analysis-summary-grid">
      <article v-for="card in summaryCards" :key="card.key" class="analysis-summary-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <p>{{ card.hint }}</p>
      </article>
    </div>

    <div class="analysis-table-shell">
      <DataTable
        v-if="filteredListings.length"
        :value="filteredListings"
        paginator
        :rows="10"
        striped-rows
        responsive-layout="scroll"
        table-style="min-width: 100%"
      >
        <Column :header="t('dashboard.municipality')">
          <template #body="{ data }">{{ data.municipality || '—' }}</template>
        </Column>
        <Column :header="t('predict.propertyType')">
          <template #body="{ data }">{{ formatType(data.property_type) }}</template>
        </Column>
        <Column :header="t('predict.size')">
          <template #body="{ data }">{{ fmt(data.uporabna_povrsina || data.size_m2, 1) }} m²</template>
        </Column>
        <Column :header="t('predict.floor')">
          <template #body="{ data }">{{ data.floor ?? '—' }}</template>
        </Column>
        <Column :header="t('analysis.askingPrice')">
          <template #body="{ data }">{{ fmtCurrency(data.asking_price) }}</template>
        </Column>
        <Column :header="t('analysis.predictedPrice')">
          <template #body="{ data }">{{ fmtCurrency(data.predicted_price) }}</template>
        </Column>
        <Column :header="t('analysis.deviation')">
          <template #body="{ data }">
            {{ fmt(data.deviation_pct ?? data.deviation_percent, 1) }}%
          </template>
        </Column>
        <Column :header="t('analysis.label')">
          <template #body="{ data }">
            <Tag :severity="labelSeverity(data.label)" :value="labelText(data.label)" />
          </template>
        </Column>
        <Column :header="t('common.actions')">
          <template #body="{ data }">
            <div class="row-actions">
              <Button
                size="small"
                severity="secondary"
                text
                icon="pi pi-calculator"
                :label="t('predict.title')"
                @click="emit('open-prediction', data)"
              />
              <Button
                v-if="data.municipality"
                size="small"
                severity="secondary"
                text
                icon="pi pi-building"
                :label="t('map.openMunicipality')"
                @click="emit('open-municipality', data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>

      <EmptyState v-else icon="pi pi-search" :message="t('common.noData')" />
    </div>
  </SectionPanel>
</template>

<style scoped>
  .analysis-results-toolbar,
  .row-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem;
  }

  .analysis-results-toolbar {
    justify-content: flex-end;
  }

  .toolbar-search {
    width: min(100%, 18rem);
  }

  .toolbar-select {
    width: 13rem;
  }

  .toolbar-link {
    text-decoration: none;
  }

  .analysis-primary-band {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 0.85rem;
  }

  .analysis-primary-card,
  .analysis-summary-card {
    display: grid;
    gap: 0.3rem;
    padding: 1rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 74%, var(--primary) 26%);
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 94%, var(--primary) 6%);
    box-shadow: var(--shadow-sm);
  }

  .analysis-primary-card span,
  .analysis-summary-card span {
    color: var(--text-soft);
    font-size: var(--text-xs);
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .analysis-primary-card strong {
    font-size: 1.2rem;
    line-height: 1.1;
  }

  .analysis-primary-card.is-emphasis {
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 92%, var(--secondary) 8%);
  }

  .analysis-primary-card.is-warning {
    background: color-mix(in srgb, var(--surface-card-strong, var(--surface-strong)) 92%, var(--warning) 8%);
  }

  .analysis-summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
    gap: 0.85rem;
    margin: 1rem 0;
  }

  .analysis-summary-card strong {
    font-size: 1.35rem;
    line-height: 1.05;
  }

  .analysis-summary-card p {
    margin: 0.2rem 0 0;
    color: var(--text-soft);
    line-height: 1.55;
  }

  .analysis-table-shell {
    display: grid;
    gap: 0.85rem;
  }

  .analysis-table-shell :deep(.p-datatable-wrapper) {
    overflow-x: auto;
  }

  .analysis-table-shell :deep(.p-datatable-table) {
    min-width: 62rem;
    width: 100%;
  }

  .analysis-table-shell :deep(.p-datatable-thead > tr > th) {
    white-space: nowrap;
  }

  @media (max-width: 980px) {
    .analysis-primary-band,
    .analysis-summary-grid {
      grid-template-columns: 1fr;
    }

    .analysis-results-toolbar {
      justify-content: stretch;
    }

    .toolbar-search,
    .toolbar-select {
      width: 100%;
    }
  }
</style>
