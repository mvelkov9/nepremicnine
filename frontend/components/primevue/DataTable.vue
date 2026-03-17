<script setup>
  import { provide, ref, computed } from 'vue'

  const props = defineProps({
    value: { type: Array, default: () => [] },
    rows: { type: Number, default: 10 },
    paginator: { type: Boolean, default: false },
  })

  const columns = ref([])
  const page = ref(0)

  function registerColumn(column) {
    if (columns.value.some((item) => item.id === column.id)) return
    columns.value.push(column)
  }

  function updateColumn(column) {
    const index = columns.value.findIndex((item) => item.id === column.id)
    if (index >= 0) columns.value[index] = column
  }

  function unregisterColumn(id) {
    columns.value = columns.value.filter((column) => column.id !== id)
  }

  provide('datatable-register-column', registerColumn)
  provide('datatable-update-column', updateColumn)
  provide('datatable-unregister-column', unregisterColumn)

  const totalPages = computed(() => {
    if (!props.paginator || !props.rows) return 1
    return Math.max(1, Math.ceil((props.value?.length || 0) / props.rows))
  })

  const paginatedRows = computed(() => {
    if (!props.paginator || !props.rows) return props.value || []
    const start = page.value * props.rows
    return (props.value || []).slice(start, start + props.rows)
  })

  function resolveField(row, field) {
    if (!field) return null
    return field.split('.').reduce((acc, key) => acc?.[key], row)
  }

  const CellRenderer = {
    props: {
      slotFn: { type: Function, default: null },
      row: { type: Object, required: true },
    },
    setup(props) {
      return () => (props.slotFn ? props.slotFn({ data: props.row }) : null)
    },
  }
</script>

<template>
  <div class="datatable-shell">
    <div class="hidden">
      <slot />
    </div>

    <div class="datatable-scroll overflow-x-auto">
      <table class="datatable-table min-w-full text-sm">
        <thead class="datatable-head text-left text-[var(--ui-text-muted)]">
          <tr>
            <th
              v-for="column in columns"
              :key="`${column.id.toString()}-header`"
              class="datatable-head-cell px-4 py-3 font-medium"
            >
              {{ column.props.header }}
            </th>
          </tr>
        </thead>
        <tbody class="datatable-body">
          <tr v-if="!paginatedRows.length">
            <td
              :colspan="Math.max(columns.length, 1)"
              class="px-4 py-6 text-center text-[var(--ui-text-muted)]"
            >
              <slot name="empty">No data</slot>
            </td>
          </tr>
          <tr
            v-for="(row, rowIndex) in paginatedRows"
            :key="row.id || row.slug || rowIndex"
            class="datatable-row align-top"
          >
            <td
              v-for="column in columns"
              :key="`${column.id.toString()}-${row.id || rowIndex}`"
              class="datatable-cell px-4 py-3 text-[var(--ui-text)]"
            >
              <CellRenderer v-if="column.slots.body" :slot-fn="column.slots.body" :row="row" />
              <template v-else>
                {{ resolveField(row, column.props.field) ?? '—' }}
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="paginator && totalPages > 1"
      class="datatable-pagination flex items-center justify-between gap-3 px-4 py-3 text-sm text-[var(--ui-text-muted)]"
    >
      <span>{{ page + 1 }} / {{ totalPages }}</span>
      <div class="flex gap-2">
        <button
          type="button"
          class="datatable-page-button"
          :disabled="page === 0"
          @click="page -= 1"
        >
          Prev
        </button>
        <button
          type="button"
          class="datatable-page-button"
          :disabled="page >= totalPages - 1"
          @click="page += 1"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .datatable-shell {
    overflow: hidden;
    border: 1px solid var(--ui-border);
    border-radius: 1.5rem;
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-bg-elevated) 92%, transparent),
      color-mix(in srgb, var(--ui-bg) 72%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 18px 32px rgb(15 23 42 / 7%);
  }

  .datatable-table {
    border-collapse: separate;
    border-spacing: 0;
  }

  .datatable-head {
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-bg) 84%, transparent),
      color-mix(in srgb, var(--ui-primary) 6%, transparent)
    );
  }

  .datatable-head-cell {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .datatable-body {
    border-top: 1px solid var(--ui-border);
  }

  .datatable-row td {
    border-top: 1px solid var(--ui-border);
    transition:
      background 160ms ease,
      border-color 160ms ease;
  }

  .datatable-row:first-child td {
    border-top: 0;
  }

  .datatable-row:hover td {
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-primary) 8%, transparent),
      color-mix(in srgb, var(--ui-secondary) 6%, transparent)
    );
  }

  .datatable-pagination {
    border-top: 1px solid var(--ui-border);
    background: color-mix(in srgb, var(--ui-bg) 78%, transparent);
  }

  .datatable-page-button {
    min-height: 2.25rem;
    padding: 0.4rem 0.85rem;
    border-radius: 999px;
    border: 1px solid var(--ui-border);
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-bg-elevated) 94%, transparent),
      color-mix(in srgb, var(--ui-bg) 78%, transparent)
    );
    color: var(--ui-text);
    font-weight: 700;
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 14%),
      0 8px 16px rgb(15 23 42 / 6%);
    transition:
      transform 160ms ease,
      border-color 160ms ease,
      background 160ms ease,
      box-shadow 160ms ease;
  }

  .datatable-page-button:hover:not(:disabled) {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--ui-primary) 24%, var(--ui-border));
    background: linear-gradient(
      145deg,
      color-mix(in srgb, var(--ui-primary) 8%, transparent),
      color-mix(in srgb, var(--ui-secondary) 6%, transparent)
    );
    box-shadow:
      inset 0 1px 0 rgb(255 255 255 / 16%),
      0 12px 20px rgb(15 23 42 / 10%);
  }

  .datatable-page-button:disabled {
    opacity: 0.45;
  }
</style>
