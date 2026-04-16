import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getApiErrorMessage } from '../utils/apiError'

export interface UsePageDataOptions {
  /** Initial value for `loading`. Views that render an initial skeleton pass `true`. */
  initialLoading?: boolean
}

/**
 * Standard loading/error wrapper for view-level data fetches.
 *
 * Replaces the repeated try/catch/finally + loading.value + pageError.value
 * boilerplate in DashboardView, MarketView, MunicipalitiesView, RegionsView,
 * BenchmarkView, MunicipalityView, etc.
 *
 * Usage:
 *   const { loading, pageError, run } = usePageData()
 *   async function loadPage() {
 *     await run(async () => {
 *       await Promise.all([...])
 *     })
 *   }
 */
export function usePageData(options: UsePageDataOptions = {}) {
  const { t } = useI18n()
  const loading = ref(options.initialLoading ?? true)
  const pageError = ref('')

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    loading.value = true
    pageError.value = ''
    try {
      return await fn()
    } catch (error) {
      pageError.value = getApiErrorMessage(error, t)
      return undefined
    } finally {
      loading.value = false
    }
  }

  function clearError() {
    pageError.value = ''
  }

  return {
    loading,
    pageError,
    run,
    clearError,
  }
}
