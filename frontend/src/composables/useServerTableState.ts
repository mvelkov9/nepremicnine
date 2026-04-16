import { computed } from 'vue'
import { useViewerQueryState } from './useViewerQueryState'

type TableQueryState = Record<string, string>

interface UseServerTableStateOptions {
  filterKeys?: string[]
}

export function useServerTableState<T extends TableQueryState>(
  defaults: T,
  options: UseServerTableStateOptions = {},
) {
  const query = useViewerQueryState(defaults)
  const filterKeys = options.filterKeys || []

  function patchTableState(patch: Partial<TableQueryState>) {
    void query.patchState(patch as unknown as Partial<T>)
  }

  const page = computed({
    get: () => Math.max(Number.parseInt(query.state.page || '1', 10) || 1, 1),
    set: (value: number) => {
      patchTableState({ page: String(Math.max(value, 1)) })
    },
  })

  const pageSize = computed({
    get: () => Math.max(Number.parseInt(query.state.page_size || '25', 10) || 25, 1),
    set: (value: number) => {
      patchTableState({ page_size: String(Math.max(value, 1)), page: '1' })
    },
  })

  const sort = computed({
    get: () => query.state.sort || 'id',
    set: (value: string) => {
      patchTableState({ sort: value, page: '1' })
    },
  })

  const order = computed({
    get: () => (query.state.order === 'asc' ? 'asc' : 'desc'),
    set: (value: 'asc' | 'desc') => {
      patchTableState({ order: value, page: '1' })
    },
  })

  const search = computed({
    get: () => query.state.search || '',
    set: (value: string) => {
      patchTableState({ search: value, page: '1' })
    },
  })

  const filters = computed(() => {
    const next: Record<string, string> = {}
    for (const key of filterKeys) {
      const value = query.state[key]
      if (value) next[key] = value
    }
    return next
  })

  const activeFilterCount = computed(() => {
    let count = search.value ? 1 : 0
    for (const key of filterKeys) {
      if (query.state[key]) count += 1
    }
    return count
  })

  function setFilter(key: string, value: string) {
    patchTableState({ [key]: value, page: '1' })
  }

  function resetFilters(extraPatch: Partial<T> = {}) {
    const patch = { page: '1', ...extraPatch } as Partial<T>
    for (const key of filterKeys) patch[key as keyof T] = '' as T[keyof T]
    void query.patchState(patch)
  }

  function toParams(extra: Record<string, unknown> = {}) {
    return {
      page: page.value,
      page_size: pageSize.value,
      sort: sort.value,
      order: order.value,
      search: search.value || undefined,
      ...filters.value,
      ...extra,
    }
  }

  return {
    state: query.state,
    page,
    pageSize,
    sort,
    order,
    search,
    filters,
    activeFilterCount,
    patchState: query.patchState,
    resetState: query.resetState,
    setFilter,
    resetFilters,
    toParams,
  }
}
