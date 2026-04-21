<script setup lang="ts">
  import Button from 'primevue/button'
  import Column from 'primevue/column'
  import DataTable from 'primevue/datatable'
  import type { DataTableSortEvent } from 'primevue/datatable'
  import IconField from 'primevue/iconfield'
  import InputIcon from 'primevue/inputicon'
  import InputText from 'primevue/inputtext'
  import Select from 'primevue/select'
  import Tag from 'primevue/tag'
  import { useI18n } from 'vue-i18n'
  import FilterBar from '../../components/FilterBar.vue'
  import EmptyState from '../../components/EmptyState.vue'
  import type { User } from '../../types/api'
  import { formatDate } from '../../utils/format'

  interface SelectOption {
    label: string
    value: string
  }

  interface AdminPageEvent {
    page?: number
    rows?: number
  }

  defineProps<{
    eyebrow: string
    title: string
    description?: string
    statusLabel: string
    statusSeverity: 'secondary' | 'contrast' | 'success' | 'danger' | 'warn' | 'info'
    visibleUsersLabel: string
    tableWindowLabel: string
    loading?: boolean
    error?: string
    users: User[]
    totalRecords: number
    page: number
    pageSize: number
    sortField: string
    sortOrder: 'asc' | 'desc'
    searchValue: string
    roleValue: string
    statusValue: string
    roleOptions: SelectOption[]
    statusOptions: SelectOption[]
    pageSizeOptions: string[]
  }>()

  const emit = defineEmits<{
    'update:searchValue': [value: string]
    'update:roleValue': [value: string]
    'update:statusValue': [value: string]
    'update:pageSizeValue': [value: number]
    clear: []
    export: []
    page: [event: AdminPageEvent]
    sort: [event: DataTableSortEvent]
    retry: []
    openActions: [event: Event, user: User]
  }>()

  const { t } = useI18n()

  function roleLabel(role: User['role']) {
    return role === 'admin' ? t('layout.roleAdmin') : t('layout.roleViewer')
  }

  function roleSeverity(role: User['role']): 'info' | 'secondary' {
    return role === 'admin' ? 'info' : 'secondary'
  }

  function userStatusSeverity(active: boolean): 'success' | 'danger' {
    return active ? 'success' : 'danger'
  }

  function formatCreatedAt(value: string) {
    return formatDate(value, { dateStyle: 'medium' })
  }

  function onPage(event: AdminPageEvent) {
    emit('page', event)
  }

  function onSort(event: DataTableSortEvent) {
    emit('sort', event)
  }

  function onPageSizeChange(value: unknown) {
    const next = Number.parseInt(String(value), 10) || 25
    emit('update:pageSizeValue', next)
  }
</script>

<template>
  <section class="card admin-users-panel">
    <div class="panel-toolbar panel-toolbar--stacked">
      <div class="panel-heading">
        <p class="eyebrow subtle">{{ eyebrow }}</p>
        <div class="panel-title-row">
          <h2>{{ title }}</h2>
          <Tag :value="statusLabel" :severity="statusSeverity" />
        </div>
        <p v-if="description" class="muted table-meta">{{ description }}</p>
        <p class="muted table-meta">{{ visibleUsersLabel }}</p>
        <p class="muted table-window">{{ tableWindowLabel }}</p>
      </div>

      <div class="toolbar-actions toolbar-actions--primary">
        <Button
          icon="pi pi-filter-slash"
          severity="secondary"
          outlined
          :disabled="!searchValue && !roleValue && !statusValue"
          :label="t('common.clear')"
          @click="emit('clear')"
        />
        <Button
          icon="pi pi-download"
          severity="secondary"
          outlined
          :disabled="!users.length"
          :label="`${t('common.export')} CSV`"
          @click="emit('export')"
        />
      </div>
    </div>

    <FilterBar :columns="4">
      <IconField class="search-field">
        <InputIcon class="pi pi-search" />
        <InputText
          :model-value="searchValue"
          :placeholder="t('common.search')"
          @update:model-value="emit('update:searchValue', String($event || ''))"
        />
      </IconField>

      <Select
        :model-value="roleValue"
        :options="roleOptions"
        option-label="label"
        option-value="value"
        class="toolbar-select"
        @update:model-value="emit('update:roleValue', String($event || ''))"
      />

      <Select
        :model-value="statusValue"
        :options="statusOptions"
        option-label="label"
        option-value="value"
        class="toolbar-select"
        @update:model-value="emit('update:statusValue', String($event || ''))"
      />

      <Select
        :model-value="String(pageSize)"
        :options="pageSizeOptions"
        class="toolbar-select rows-select"
        @update:model-value="onPageSizeChange"
      />
    </FilterBar>

    <div v-if="error" class="state-card state-card-stack" role="alert">
      <EmptyState icon="pi pi-exclamation-triangle" :message="error" />
      <div class="state-card-actions">
        <Button
          size="small"
          severity="secondary"
          outlined
          icon="pi pi-refresh"
          :label="t('common.retry')"
          @click="emit('retry')"
        />
      </div>
    </div>

    <div v-else class="table-shell">
      <DataTable
        :value="users"
        :loading="loading"
        lazy
        paginator
        striped-rows
        responsive-layout="scroll"
        :rows="pageSize"
        :first="(page - 1) * pageSize"
        :total-records="totalRecords"
        :sort-field="sortField"
        :sort-order="sortOrder === 'asc' ? 1 : -1"
        @page="onPage"
        @sort="onSort"
      >
        <template #empty>
          <EmptyState icon="pi pi-users" :message="t('empty.noUsers')" />
        </template>

        <Column field="id" :header="t('common.id')" sortable />
        <Column field="full_name" :header="t('admin.name')" sortable />
        <Column field="email" :header="t('admin.email')" sortable />

        <Column field="role" :header="t('admin.role')" sortable>
          <template #body="{ data }">
            <Tag :value="roleLabel(data.role)" :severity="roleSeverity(data.role)" />
          </template>
        </Column>

        <Column field="is_active" :header="t('admin.status')" sortable>
          <template #body="{ data }">
            <Tag
              :value="data.is_active ? t('admin.active') : t('admin.disabled')"
              :severity="userStatusSeverity(data.is_active)"
            />
          </template>
        </Column>

        <Column field="created_at" :header="t('admin.created')" sortable>
          <template #body="{ data }">
            {{ formatCreatedAt(data.created_at) }}
          </template>
        </Column>

        <Column :header="t('data.actions')">
          <template #body="{ data }">
            <div class="row-actions">
              <Button
                icon="pi pi-ellipsis-v"
                severity="secondary"
                outlined
                size="small"
                :aria-label="`${t('data.actions')} - ${data.full_name || data.email}`"
                aria-haspopup="menu"
                @click="emit('openActions', $event, data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>
  </section>
</template>

<style scoped>
  .admin-users-panel {
    display: grid;
    gap: 1rem;
    border-radius: var(--radius-lg);
    border: 1px solid color-mix(in srgb, var(--border) 72%, var(--content-border-strong) 28%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 88%, transparent),
        transparent 38%
      ),
      var(--surface-panel);
    box-shadow: var(--accent-shadow, var(--shadow-sm));
    padding: 1.3rem;
    min-width: 0;
  }

  .panel-toolbar {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .panel-toolbar--stacked {
    align-items: stretch;
  }

  .panel-heading {
    display: grid;
    gap: 0.2rem;
    min-width: 0;
  }

  .panel-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .panel-toolbar h2 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.24rem, 1.8vw, 1.55rem);
    line-height: 1.04;
    text-wrap: balance;
  }

  .table-meta {
    margin: 0.1rem 0 0;
  }

  .table-window {
    margin: 0;
    font-size: 0.94rem;
  }

  .toolbar-actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .toolbar-actions--primary {
    justify-content: flex-end;
    align-self: start;
  }

  .search-field {
    width: min(100%, 24rem);
    flex: 1 1 18rem;
  }

  .toolbar-select {
    min-width: 10.5rem;
    flex: 1 1 10.5rem;
  }

  .rows-select {
    min-width: 7rem;
    flex-basis: 7rem;
  }

  .state-card-stack {
    display: grid;
    gap: 0.85rem;
  }

  .state-card-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  .table-shell {
    min-width: 0;
    overflow-x: auto;
    border-radius: var(--radius-md);
  }

  .row-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
  }

  @media (max-width: 980px) {
    .toolbar-actions--primary,
    .panel-toolbar {
      width: 100%;
    }

    .panel-title-row {
      align-items: flex-start;
    }

    .toolbar-actions {
      width: 100%;
      justify-content: stretch;
    }

    .toolbar-actions :deep(.p-button) {
      flex: 1 1 0;
    }

    .search-field,
    .toolbar-select,
    .rows-select {
      width: 100%;
      min-width: 0;
    }
  }
</style>
