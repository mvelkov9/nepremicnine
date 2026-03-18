<script setup>
  import { computed, ref, watch } from 'vue'
  import EmptyState from './EmptyState.vue'

  const props = defineProps({
    rows: { type: Array, default: () => [] },
    columns: { type: Array, default: () => [] },
    rowKey: { type: String, default: 'id' },
    pageSize: { type: Number, default: 10 },
    emptyMessage: { type: String, default: '' },
    emptyIcon: { type: String, default: '📄' },
  })

  const currentPage = ref(1)
  const sortKey = ref('')
  const sortDirection = ref('asc')

  watch(
    () => props.rows.length,
    () => {
      const totalPages = Math.max(1, Math.ceil(props.rows.length / props.pageSize))
      if (currentPage.value > totalPages) {
        currentPage.value = totalPages
      }
    },
  )

  function resolveValue(row, column) {
    if (typeof column.value === 'function') {
      return column.value(row)
    }
    return row?.[column.key]
  }

  function compareValues(left, right) {
    if (left == null && right == null) return 0
    if (left == null) return 1
    if (right == null) return -1

    if (typeof left === 'number' && typeof right === 'number') {
      return left - right
    }

    const leftDate = Date.parse(left)
    const rightDate = Date.parse(right)
    if (!Number.isNaN(leftDate) && !Number.isNaN(rightDate)) {
      return leftDate - rightDate
    }

    return String(left).localeCompare(String(right), undefined, {
      numeric: true,
      sensitivity: 'base',
    })
  }

  const sortedRows = computed(() => {
    if (!sortKey.value) {
      return props.rows
    }

    const column = props.columns.find((item) => item.key === sortKey.value)
    if (!column) {
      return props.rows
    }

    const sorted = [...props.rows].sort((left, right) => {
      const comparison = compareValues(resolveValue(left, column), resolveValue(right, column))
      return sortDirection.value === 'asc' ? comparison : -comparison
    })

    return sorted
  })

  const totalPages = computed(() => Math.max(1, Math.ceil(sortedRows.value.length / props.pageSize)))

  const pagedRows = computed(() => {
    const startIndex = (currentPage.value - 1) * props.pageSize
    return sortedRows.value.slice(startIndex, startIndex + props.pageSize)
  })

  const rangeLabel = computed(() => {
    if (!sortedRows.value.length) {
      return '0-0'
    }

    const startIndex = (currentPage.value - 1) * props.pageSize + 1
    const endIndex = Math.min(currentPage.value * props.pageSize, sortedRows.value.length)
    return `${startIndex}-${endIndex}`
  })

  function toggleSort(column) {
    if (!column.sortable) {
      return
    }

    if (sortKey.value === column.key) {
      sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
      return
    }

    sortKey.value = column.key
    sortDirection.value = 'asc'
  }

  function formatCell(row, column) {
    const value = resolveValue(row, column)
    if (typeof column.formatter === 'function') {
      return column.formatter(value, row)
    }
    return value == null || value === '' ? '—' : value
  }

  function rowIdentifier(row, index) {
    return row?.[props.rowKey] ?? `${index}-${JSON.stringify(row)}`
  }
</script>

<template>
  <div class="app-data-table">
    <EmptyState
      v-if="!rows.length"
      :icon="emptyIcon"
      :message="emptyMessage"
    />

    <template v-else>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th
                v-for="column in columns"
                :key="column.key"
                :class="[
                  column.headerClass,
                  column.sortable ? 'sortable' : '',
                  sortKey === column.key ? `sorted-${sortDirection}` : '',
                ]"
              >
                <button
                  v-if="column.sortable"
                  type="button"
                  class="sort-button"
                  @click="toggleSort(column)"
                >
                  <span>{{ column.label }}</span>
                  <span class="sort-indicator">
                    {{ sortKey === column.key ? (sortDirection === 'asc' ? '↑' : '↓') : '↕' }}
                  </span>
                </button>
                <span v-else>{{ column.label }}</span>
              </th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="(row, index) in pagedRows" :key="rowIdentifier(row, index)">
              <td v-for="column in columns" :key="column.key" :class="column.cellClass">
                <slot :name="`cell-${column.key}`" :row="row" :value="resolveValue(row, column)">
                  {{ formatCell(row, column) }}
                </slot>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="totalPages > 1" class="table-footer">
        <span class="table-summary">{{ rangeLabel }} / {{ sortedRows.length }}</span>
        <div class="pagination-actions">
          <button type="button" :disabled="currentPage === 1" @click="currentPage -= 1">
            {{ $t('pagination.previous') }}
          </button>
          <span>{{ $t('pagination.page') }} {{ currentPage }} {{ $t('pagination.of') }} {{ totalPages }}</span>
          <button type="button" :disabled="currentPage === totalPages" @click="currentPage += 1">
            {{ $t('pagination.next') }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
  .app-data-table {
    display: grid;
    gap: 0.85rem;
  }

  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 1rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    min-width: 42rem;
    background: var(--surface-soft);
  }

  th,
  td {
    padding: 0.85rem 0.9rem;
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid var(--border);
  }

  th {
    color: var(--text-soft);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    background: var(--surface-elevated);
  }

  tbody tr:nth-child(even) {
    background: rgb(15 23 42 / 2%);
  }

  tbody tr:last-child td {
    border-bottom: none;
  }

  .sort-button {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    border: none;
    background: none;
    padding: 0;
    color: inherit;
    font: inherit;
    text-transform: inherit;
    letter-spacing: inherit;
    cursor: pointer;
  }

  .sort-indicator {
    color: var(--text-muted);
    font-size: 0.72rem;
  }

  .table-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .table-summary,
  .pagination-actions span {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .pagination-actions {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
  }

  .pagination-actions button {
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface-elevated);
    padding: 0.45rem 0.8rem;
    color: var(--text);
    font: inherit;
  }

  .pagination-actions button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  @media (max-width: 720px) {
    table {
      min-width: 36rem;
    }

    .table-footer {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>