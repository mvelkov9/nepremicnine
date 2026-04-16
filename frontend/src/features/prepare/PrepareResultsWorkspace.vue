<script setup lang="ts">
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import MetricCard from '../../components/MetricCard.vue'
  import PageHeader from '../../components/PageHeader.vue'
  import SectionPanel from '../../components/SectionPanel.vue'
  import { useFormat } from '../../composables/useFormat'
  import type { GursEnrichmentRow } from '../../utils/enrichmentSummary'
  import type {
    PreparePerYearRow,
    PrepareReportSummary,
    PrepareResultPayload,
    PrepareTrainingDatasetRow,
    PrepareEnrichmentTotals,
  } from './types'

  const props = defineProps<{
    result: PrepareResultPayload
    selectedVariantLabel: string
    perYearRows: PreparePerYearRow[]
    trainingDatasetRows: PrepareTrainingDatasetRow[]
    enrichmentRows: GursEnrichmentRow[]
    enrichmentTotals: PrepareEnrichmentTotals
  }>()

  const emit = defineEmits<{
    openModel: []
  }>()

  const { t } = useI18n()
  const { fmt } = useFormat()

  function getReportDetail(report: PrepareReportSummary) {
    return (
      report.reason ||
      report.used_size_column ||
      report.used_property_type_column ||
      t('common.noData')
    )
  }

  function enrichmentRunLabel(label: string) {
    return label === 'single' ? t('prepare.currentRun') : String(label)
  }

  function enrichmentSeverity(available: boolean, matched: boolean) {
    if (matched) return 'success'
    if (available) return 'warn'
    return 'contrast'
  }

  function enrichmentSourcesLabel(row: GursEnrichmentRow) {
    if (row.matchedSources.length) return row.matchedSources.join(', ')
    if (row.sources.length) {
      return t('prepare.detectedOnlySources', { sources: row.sources.join(', ') })
    }
    return t('common.noData')
  }
</script>

<template>
  <SectionPanel tag="section" class="prepare-results-panel">
    <PageHeader compact :eyebrow="t('prepare.result')" :title="t('prepare.readyForModel')" />

    <div class="prepare-result-metrics prepare-result-metrics--primary">
      <MetricCard
        :label="t('prepare.outputRows')"
        :value="fmt(result.rows || result.total_rows || 0)"
        tone="success"
      />
      <MetricCard
        v-if="result.columns"
        :label="t('prepare.outputColumns')"
        :value="fmt(result.columns?.length || 0)"
      />
      <MetricCard
        v-if="result.per_year"
        :label="t('prepare.yearsCovered')"
        :value="fmt(Object.keys(result.per_year).length)"
      />
      <MetricCard :label="t('prepare.variantLabel')" :value="selectedVariantLabel" />
    </div>

    <div v-if="perYearRows.length" class="prepare-table-shell">
      <DataTable :value="perYearRows" striped-rows size="small">
        <Column :header="t('prepare.year')">
          <template #body="{ data: row }">
            <Tag :value="String(row.year)" severity="info" />
          </template>
        </Column>
        <Column :header="t('data.rows')">
          <template #body="{ data: row }">
            {{ fmt(row.rows) }}
          </template>
        </Column>
      </DataTable>
    </div>

    <div v-if="result.reports?.length" class="prepare-table-shell">
      <DataTable :value="result.reports" striped-rows size="small">
        <Column :header="t('prepare.year')">
          <template #body="{ data: report }">
            <Tag :value="String(report.label)" severity="info" />
          </template>
        </Column>
        <Column :header="t('prepare.reportStatus')">
          <template #body="{ data: report }">
            <Tag :value="report.status" :severity="report.status === 'ok' ? 'success' : 'danger'" />
          </template>
        </Column>
        <Column :header="t('data.rows')">
          <template #body="{ data: report }">
            {{ fmt(report.rows || 0) }}
          </template>
        </Column>
        <Column :header="t('prepare.reportDetail')">
          <template #body="{ data: report }">
            <span class="muted">{{ getReportDetail(report) }}</span>
          </template>
        </Column>
      </DataTable>
    </div>

    <SectionPanel
      v-if="enrichmentRows.length"
      tag="section"
      class="prepare-results-panel__section"
      :eyebrow="t('prepare.result')"
      :title="t('prepare.gursEnrichment')"
      :description="t('prepare.gursEnrichmentDesc')"
    >
      <div class="prepare-result-metrics prepare-result-metrics--secondary">
        <MetricCard
          :label="t('prepare.exactAddressMatches')"
          :value="fmt(enrichmentTotals.rnExactAddress)"
        />
        <MetricCard
          :label="t('prepare.regionIdsRecovered')"
          :value="fmt(enrichmentTotals.rnRegionId)"
        />
        <MetricCard
          :label="t('prepare.evBuildingMatches')"
          :value="fmt(enrichmentTotals.evBuildingMatch)"
        />
        <MetricCard
          :label="t('prepare.evParcelMatches')"
          :value="fmt(enrichmentTotals.evParcelMatch)"
        />
        <MetricCard
          :label="t('prepare.knPolygonMatches')"
          :value="fmt(enrichmentTotals.knPolygonMatch)"
        />
        <MetricCard
          :label="t('prepare.gjiVodovodMatches')"
          :value="fmt(enrichmentTotals.gjiVodovodNearby)"
        />
        <MetricCard
          :label="t('prepare.gjiKanalizacijaMatches')"
          :value="fmt(enrichmentTotals.gjiKanalizacijaNearby)"
        />
        <MetricCard
          :label="t('prepare.emvZoneMatches')"
          :value="fmt(enrichmentTotals.emvZoneMatch)"
        />
      </div>

      <div class="prepare-table-shell">
        <DataTable :value="enrichmentRows" striped-rows size="small">
          <Column :header="t('prepare.year')">
            <template #body="{ data: row }">
              <Tag :value="enrichmentRunLabel(row.label)" severity="info" />
            </template>
          </Column>
          <Column :header="t('prepare.sourceCoverage')">
            <template #body="{ data: row }">
              <div class="prepare-coverage-tags">
                <Tag
                  :value="t('prepare.rnRegister')"
                  :severity="
                    enrichmentSeverity(
                      row.rnAvailable,
                      row.rnExactAddress > 0 || row.rnRegionId > 0,
                    )
                  "
                />
                <Tag
                  :value="t('prepare.evBuildings')"
                  :severity="enrichmentSeverity(row.evBuildingAvailable, row.evBuildingMatch > 0)"
                />
                <Tag
                  :value="t('prepare.evParcels')"
                  :severity="enrichmentSeverity(row.evParcelAvailable, row.evParcelMatch > 0)"
                />
                <Tag
                  :value="t('prepare.knPolygons')"
                  :severity="enrichmentSeverity(row.knAvailable, row.knPolygonMatch > 0)"
                />
                <Tag
                  :value="t('prepare.gjiInfrastructure')"
                  :severity="
                    enrichmentSeverity(
                      row.gjiAvailable,
                      row.gjiVodovodNearby > 0 || row.gjiKanalizacijaNearby > 0,
                    )
                  "
                />
                <Tag
                  :value="t('prepare.emvZones')"
                  :severity="
                    enrichmentSeverity(
                      row.emvAvailable || row.emvSpatialEnabled,
                      row.emvZoneMatch > 0,
                    )
                  "
                />
              </div>
            </template>
          </Column>
          <Column field="rnExactAddress" :header="t('prepare.exactAddressMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.rnExactAddress) }}
            </template>
          </Column>
          <Column field="rnRegionId" :header="t('prepare.regionIdsRecovered')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.rnRegionId) }}
            </template>
          </Column>
          <Column field="evBuildingMatch" :header="t('prepare.evBuildingMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.evBuildingMatch) }}
            </template>
          </Column>
          <Column field="evParcelMatch" :header="t('prepare.evParcelMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.evParcelMatch) }}
            </template>
          </Column>
          <Column field="knPolygonMatch" :header="t('prepare.knPolygonMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.knPolygonMatch) }}
            </template>
          </Column>
          <Column field="gjiVodovodNearby" :header="t('prepare.gjiVodovodMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.gjiVodovodNearby) }}
            </template>
          </Column>
          <Column
            field="gjiKanalizacijaNearby"
            :header="t('prepare.gjiKanalizacijaMatches')"
            sortable
          >
            <template #body="{ data: row }">
              {{ fmt(row.gjiKanalizacijaNearby) }}
            </template>
          </Column>
          <Column field="emvZoneMatch" :header="t('prepare.emvZoneMatches')" sortable>
            <template #body="{ data: row }">
              {{ fmt(row.emvZoneMatch) }}
            </template>
          </Column>
          <Column :header="t('prepare.enrichmentSources')">
            <template #body="{ data: row }">
              <span class="muted prepare-source-cell">{{ enrichmentSourcesLabel(row) }}</span>
            </template>
          </Column>
        </DataTable>
      </div>
    </SectionPanel>

    <SectionPanel
      v-if="result.training_dataset"
      tag="section"
      class="prepare-results-panel__section"
      :eyebrow="t('prepare.result')"
      :title="t('prepare.readyForModel')"
    >
      <div class="prepare-table-shell">
        <DataTable :value="trainingDatasetRows" striped-rows size="small">
          <Column :header="t('prepare.datasetPath')" field="path" />
          <Column :header="t('data.rows')">
            <template #body="{ data: row }">
              {{ fmt(row.rows) }}
            </template>
          </Column>
          <Column :header="t('data.columns')">
            <template #body="{ data: row }">
              {{ fmt(row.columns) }}
            </template>
          </Column>
          <Column :header="t('prepare.yearsCovered')">
            <template #body="{ data: row }">
              {{ row.years }}
            </template>
          </Column>
        </DataTable>
      </div>

      <div class="prepare-results-actions">
        <Button
          icon="pi pi-arrow-right"
          :label="t('prepare.openModel')"
          @click="emit('openModel')"
        />
      </div>
    </SectionPanel>
  </SectionPanel>
</template>

<style scoped>
  .prepare-results-panel {
    display: grid;
    gap: 1rem;
  }

  .prepare-result-metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
  }

  .prepare-result-metrics :deep(.metric-card) {
    min-width: 0;
  }

  .prepare-table-shell {
    overflow-x: auto;
    border: 1px solid color-mix(in srgb, var(--border) 80%, var(--content-border-strong) 20%);
    border-radius: var(--radius-sm);
    background: var(--surface);
  }

  .prepare-table-shell :deep(.p-datatable) {
    min-width: 100%;
  }

  .prepare-coverage-tags {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .prepare-source-cell {
    display: inline-block;
    max-width: 28rem;
    white-space: normal;
    word-break: break-word;
  }

  .prepare-results-panel__section {
    padding: 0;
    border: 0;
    box-shadow: none;
    background: transparent;
  }

  .prepare-results-actions {
    display: flex;
    justify-content: flex-end;
  }

  @media (max-width: 720px) {
    .prepare-results-actions {
      justify-content: stretch;
    }

    .prepare-results-actions :deep(.p-button) {
      width: 100%;
    }
  }
</style>
