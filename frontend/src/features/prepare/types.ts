export type PrepareMode = 'bulk' | 'single' | 'manual'

export type PrepareStepState = 'pending' | 'active' | 'done' | 'error'

export type PrepareEnrichmentOptionKey =
  | 'enable_rn'
  | 'enable_ev'
  | 'enable_kn'
  | 'enable_gji'
  | 'enable_dtm'
  | 'enable_emv'

export interface PrepareEnrichmentState {
  enable_rn: boolean
  enable_ev: boolean
  enable_kn: boolean
  enable_gji: boolean
  enable_dtm: boolean
  enable_emv: boolean
  variant_label: string
}

export interface PrepareEnrichmentOptionDefinition {
  key: PrepareEnrichmentOptionKey
  titleKey: string
  descKey: string
  filesKey: string
  icon: string
}

export interface PrepareDatasetRef {
  id?: number
  original_name: string
  relative_path: string
}

export interface PrepareDetectedPair {
  year: number
  posli: PrepareDatasetRef | null
  delistavb: PrepareDatasetRef | null
  zemljisca: PrepareDatasetRef | null
}

export interface PrepareTrainingDataset {
  relative_path?: string | null
  path?: string | null
  rows?: number | null
  columns?: string[] | null
  num_columns?: number | null
}

export interface PrepareReportSummary {
  label?: string | number | null
  status?: string | null
  rows?: number | null
  reason?: string | null
  used_size_column?: string | null
  used_property_type_column?: string | null
}

export interface PrepareResultPayload {
  rows?: number | null
  total_rows?: number | null
  columns?: string[] | null
  per_year?: Record<string, number>
  reports?: PrepareReportSummary[]
  enrichment_summary?: unknown
  enrichment_options?: Record<string, unknown>
  training_dataset?: PrepareTrainingDataset | null
}

export interface PrepareJobStatus {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  stage: string | null
  progress: number
  total_pairs?: number | null
  current_pair_index?: number | null
  current_label?: string | null
  pairs_completed?: number | null
  rows?: number | null
  spatial_phase?: string | null
  result?: PrepareResultPayload | null
  error?: string | null
}

export interface PrepareTimelineSubStep {
  key: string
  label: string
  state: PrepareStepState
}

export interface PrepareTimelineStep {
  key: string
  label: string
  state: PrepareStepState
  meta?: string
  detail?: string
  substeps?: PrepareTimelineSubStep[]
}

export interface PrepareTrainingDatasetRow {
  path: string
  rows: number
  columns: number
  years: string
}

export interface PreparePerYearRow {
  year: string
  rows: number
}

export interface PrepareEnrichmentTotals {
  runs: number
  rnExactAddress: number
  rnRegionId: number
  evBuildingMatch: number
  evParcelMatch: number
  knPolygonMatch: number
  gjiVodovodNearby: number
  gjiKanalizacijaNearby: number
  emvZoneMatch: number
}
