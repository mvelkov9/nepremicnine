<script setup lang="ts">
  import Button from 'primevue/button'
  import IconField from 'primevue/iconfield'
  import InputIcon from 'primevue/inputicon'
  import InputText from 'primevue/inputtext'
  import { useI18n } from 'vue-i18n'
  import SavedWorkspaceMenu from './SavedWorkspaceMenu.vue'
  import type { TableViewState } from '../../types/api'

  const props = defineProps<{
    page: string
    state: TableViewState
    searchValue?: string
    searchPlaceholder?: string
    activeFilters?: string[]
    exportLabel?: string
  }>()

  const emit = defineEmits<{
    'update:searchValue': [value: string]
    export: []
    clear: []
  }>()

  const { t } = useI18n()
</script>

<template>
  <div class="table-workbench-toolbar">
    <div class="table-workbench-toolbar__left">
      <IconField class="toolbar-search">
        <InputIcon class="pi pi-search" />
        <InputText
          :model-value="searchValue"
          :placeholder="searchPlaceholder || t('common.search')"
          @update:model-value="emit('update:searchValue', $event)"
        />
      </IconField>

      <div v-if="activeFilters?.length" class="filter-chips">
        <span v-for="item in activeFilters" :key="item" class="filter-chip">{{ item }}</span>
      </div>
    </div>

    <div class="table-workbench-toolbar__actions">
      <SavedWorkspaceMenu :page="page" :state="state" />
      <Button
        severity="secondary"
        outlined
        icon="pi pi-download"
        :label="exportLabel || t('common.export')"
        @click="emit('export')"
      />
      <Button
        severity="secondary"
        text
        icon="pi pi-filter-slash"
        :label="t('map.clearFilter')"
        @click="emit('clear')"
      />
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
  .table-workbench-toolbar,
  .table-workbench-toolbar__left,
  .table-workbench-toolbar__actions,
  .filter-chips {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .table-workbench-toolbar {
    justify-content: space-between;
    margin-bottom: 1rem;
    padding: 1rem 1.05rem;
    border-radius: var(--radius-md);
    border: 1px solid color-mix(in srgb, var(--border) 66%, var(--primary) 34%);
    background:
      linear-gradient(
        180deg,
        color-mix(in srgb, var(--glass-highlight) 100%, transparent),
        transparent 42%
      ),
      var(--surface-panel-muted, var(--surface-soft));
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      var(--shadow-sm);
  }

  .toolbar-search {
    width: min(100%, 22rem);
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    min-height: 2.1rem;
    padding: 0.35rem 0.8rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--border) 60%, var(--primary) 40%);
    background: color-mix(
      in srgb,
      var(--surface-card-strong, var(--surface-soft)) 72%,
      var(--primary) 28%
    );
    color: var(--text);
    font-size: 0.8rem;
    font-weight: 700;
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }

  @media (max-width: 860px) {
    .table-workbench-toolbar {
      align-items: stretch;
      flex-direction: column;
    }

    .table-workbench-toolbar__actions {
      width: 100%;
      display: grid;
      grid-template-columns: 1fr;
    }

    .toolbar-search {
      width: 100%;
    }
  }
</style>
