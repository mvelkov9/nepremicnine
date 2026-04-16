import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReferenceDataStore } from '../stores/referenceData'
import { useFormat } from './useFormat'

export interface SelectOption {
  label: string
  value: string
}

export interface FilterOptionLabels {
  allPropertyTypes?: string
  allRegions?: string
  allMunicipalities?: string
  allYears?: string
}

export interface UseFilterOptionsParams {
  /** Optional reactive source for the currently selected region (used to scope municipalities). */
  region?: Ref<string> | ComputedRef<string>
  /** Override any of the "All ..." labels with a specific i18n key. */
  labels?: FilterOptionLabels
}

/**
 * Shared computed option lists for the common filter controls used across
 * DashboardView, MapView, MarketView, RegionsView, MunicipalitiesView, BenchmarkView, etc.
 *
 * All lists are prepended with an empty-value "All" option. The default
 * "All" labels come from the existing i18n keys, but any individual label
 * can be overridden via the `labels` option (useful when a view uses a
 * page-specific wording like `dashboard.filterAllTypes`).
 */
export function useFilterOptions(params: UseFilterOptionsParams = {}) {
  const { t } = useI18n()
  const { formatType } = useFormat()
  const referenceData = useReferenceDataStore()

  const propertyTypeOptions = computed<SelectOption[]>(() => [
    { label: t(params.labels?.allPropertyTypes ?? 'market.allPropertyTypes'), value: '' },
    ...referenceData.propertyTypes.map((value) => ({
      label: formatType(value),
      value,
    })),
  ])

  const regionOptions = computed<SelectOption[]>(() => [
    { label: t(params.labels?.allRegions ?? 'municipalities.allRegions'), value: '' },
    ...referenceData.regions.map((region) => ({
      label: region as string,
      value: region as string,
    })),
  ])

  const municipalityOptions = computed<SelectOption[]>(() => {
    const selectedRegion = params.region?.value ?? ''
    const rows = selectedRegion
      ? referenceData.municipalities.filter((item) => item.region === selectedRegion)
      : referenceData.municipalities
    return [
      { label: t(params.labels?.allMunicipalities ?? 'map.allMunicipalities'), value: '' },
      ...rows.map((item) => ({ label: item.municipality, value: item.municipality })),
    ]
  })

  const yearOptions = computed<SelectOption[]>(() => [
    { label: t(params.labels?.allYears ?? 'map.allYears'), value: '' },
    ...referenceData.years.map((year) => ({ label: String(year), value: String(year) })),
  ])

  return {
    propertyTypeOptions,
    regionOptions,
    municipalityOptions,
    yearOptions,
  }
}
