import { computed, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type QueryState = Record<string, string>

function queryValue(value: unknown, fallback: string) {
  return typeof value === 'string' ? value : fallback
}

export function useViewerQueryState<T extends QueryState>(defaults: T) {
  const route = useRoute()
  const router = useRouter()
  const state = reactive({ ...defaults }) as T

  let syncingFromRoute = false

  function syncFromRoute(query = route.query) {
    syncingFromRoute = true
    for (const [key, fallback] of Object.entries(defaults)) {
      state[key as keyof T] = queryValue(query[key], fallback) as T[keyof T]
    }
    syncingFromRoute = false
  }

  function currentQuerySubset() {
    const subset: Record<string, string> = {}
    for (const [key, fallback] of Object.entries(defaults)) {
      const value = queryValue(route.query[key], fallback)
      if (value && value !== fallback) subset[key] = value
    }
    return subset
  }

  function nextQuerySubset() {
    const subset: Record<string, string> = {}
    for (const [key, fallback] of Object.entries(defaults)) {
      const value = state[key as keyof T]
      if (value && value !== fallback) subset[key] = value
    }
    return subset
  }

  function replaceQuery() {
    const nextSubset = nextQuerySubset()
    const currentSubset = currentQuerySubset()
    if (JSON.stringify(nextSubset) === JSON.stringify(currentSubset)) return Promise.resolve()

    const nextQuery = { ...route.query }
    for (const key of Object.keys(defaults)) delete nextQuery[key]
    for (const [key, value] of Object.entries(nextSubset)) nextQuery[key] = value
    return router.replace({ path: route.path, query: nextQuery })
  }

  function patchState(patch: Partial<T>) {
    Object.assign(state, patch)
    if (!syncingFromRoute) return replaceQuery()
  }

  function resetState() {
    Object.assign(state, defaults)
    if (!syncingFromRoute) return replaceQuery()
  }

  watch(
    () => route.query,
    (query) => {
      syncFromRoute(query)
    },
    { immediate: true },
  )

  watch(
    state,
    () => {
      if (syncingFromRoute) return
      void replaceQuery()
    },
    { deep: true },
  )

  const activeFilterCount = computed(
    () =>
      Object.entries(state).filter(([key, value]) => !['tab', 'view'].includes(key) && value)
        .length,
  )

  return {
    state,
    patchState,
    resetState,
    activeFilterCount,
  }
}
