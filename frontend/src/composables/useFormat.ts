import { useI18n } from 'vue-i18n'
import { formatCurrency, formatNumber, formatPercent } from '../utils/format'
import { getPropertyTypeLabel } from '../utils/propertyType'

/**
 * Composable that provides shorthand formatting helpers bound to the current locale.
 *
 * Replaces the identical `fmt()`, `fmtCurrency()`, and `formatType()` functions
 * previously copy-pasted across 8+ views and components.
 */
export function useFormat() {
  const { t } = useI18n()

  function fmt(value: number | null | undefined, decimals = 0) {
    return formatNumber(value, { maximumFractionDigits: decimals })
  }

  function fmtCurrency(value: number | null | undefined, decimals = 0) {
    return formatCurrency(value, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
  }

  function formatType(value: string) {
    return getPropertyTypeLabel(value, t)
  }

  return {
    fmt,
    fmtCurrency,
    formatCurrency: fmtCurrency,
    formatPercent,
    formatType,
  }
}
