<script setup lang="ts">
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import type { DataTableSortEvent } from 'primevue/datatable'
  import { useI18n } from 'vue-i18n'
  import EmptyState from '../EmptyState.vue'
  import LoadingSpinner from '../LoadingSpinner.vue'
  import SectionPanel from '../SectionPanel.vue'
  import TableWorkbenchToolbar from '../workbench/TableWorkbenchToolbar.vue'
  import type {
    DatasetRow,
    DatasetTablePageEvent,
    DatasetTableSortEvent,
  } from '../../features/data/types'
  import type { TableViewState } from '../../types/api'

  const props = defineProps<{
    page: string
    state: TableViewState
    searchValue: string
    datasets: DatasetRow[]
    loading: boolean
    first: number
    rows: number
    totalRecords: number
    sortField: string
    sortOrder: 'asc' | 'desc'
    activeFilters?: string[]
    formatDate?: (value: string) => string
    canDelete?: boolean
  }>()

  const emit = defineEmits<{
    'update:searchValue': [value: string]
    export: []
    clear: []
    page: [event: DatasetTablePageEvent]
    sort: [event: DatasetTableSortEvent]
    preview: [row: DatasetRow]
    delete: [row: DatasetRow]
  }>()

  const { t } = useI18n()

  function handlePage(event: DatasetTablePageEvent) {
    emit('page', event)
  }

  function handleSort(event: DataTableSortEvent) {
    emit('sort', {
      sortField: typeof event.sortField === 'string' ? event.sortField : undefined,
      sortOrder:
        event.sortOrder === 1 || event.sortOrder === -1 || event.sortOrder === 0
          ? event.sortOrder
          : undefined,
    })
  }
</script>

<template>
  <SectionPanel
    class="data-dataset-library"
    :eyebrow="t('data.datasets')"
    :title="t('data.datasetLibrary')"
  >
    <p class="data-dataset-library__description">{{ t('data.datasetLibraryHint') }}</p>

    <TableWorkbenchToolbar
      page="data"
      :state="state"
      :search-value="searchValue"
      :active-filters="activeFilters"
      @update:search-value="emit('update:searchValue', $event)"
      @export="emit('export')"
      @clear="emit('clear')"
    >
      <template #actions>
        <slot name="toolbar-actions" />
      </template>
    </TableWorkbenchToolbar>

    <LoadingSpinner v-if="loading" :label="t('common.loading')" />
    <EmptyState
      v-else-if="!datasets.length"
      icon="pi pi-folder-open"
      :message="t('empty.noDatasets')"
    />
    <DataTable
      v-else
      :value="datasets"
      lazy
      paginator
      :first="first"
      :rows="rows"
      :total-records="totalRecords"
      :sort-field="sortField"
      :sort-order="sortOrder === 'asc' ? 1 : -1"
      size="small"
      striped-rows
      responsive-layout="scroll"
      @page="handlePage"
      @sort="handleSort"
    >
      <Column field="original_name" :header="t('data.fileName')" sortable />
      <Column field="relative_path" :header="t('data.relativePath')" sortable />
      <Column field="row_count" :header="t('data.rows')" sortable>
        <template #body="{ data }">{{ data.row_count.toLocaleString() }}</template>
      </Column>
      <Column field="uploaded_at" :header="t('data.uploaded')" sortable>
        <template #body="{ data }">
          {{ formatDate ? formatDate(data.uploaded_at) : data.uploaded_at }}
        </template>
      </Column>
      <Column :header="t('data.actions')">
        <template #body="{ data }">
          <div class="dataset-row-actions">
            <Button
              size="small"
              severity="secondary"
              outlined
              icon="pi pi-eye"
              :label="t('data.preview')"
              @click="emit('preview', data)"
            />
            <Button
              v-if="canDelete"
              size="small"
              severity="danger"
              outlined
              icon="pi pi-trash"
              :label="t('common.delete')"
              @click="emit('delete', data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>
  </SectionPanel>
</template>

<style scoped>
  .data-dataset-library {
    gap: 1rem;
  }

  .data-dataset-library__description {
    margin: -0.25rem 0 0;
    color: var(--text-muted);
  }

  .dataset-row-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .dataset-row-actions :deep(.p-button) {
    justify-content: center;
  }

  @media (max-width: 720px) {
    .dataset-row-actions {
      display: grid;
      grid-template-columns: 1fr;
      width: 100%;
    }

    .dataset-row-actions :deep(.p-button) {
      width: 100%;
    }
  }
</style>
