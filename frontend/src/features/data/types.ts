export type UploadItemStatus =
  | 'queued'
  | 'uploading'
  | 'processing'
  | 'uploaded'
  | 'skipped'
  | 'partial'
  | 'error'

export interface UploadItem {
  key: string
  file: File
  status: UploadItemStatus
  progress: number
  uploadedNames: string[]
  skippedNames: string[]
  summary: string
  errorMessage: string
}

export interface UploadFileResult {
  file: File
  uploaded: Array<{
    id?: number
    original_name: string
    relative_path: string
    row_count?: number
  }>
  skipped: string[]
  message: string
  errorMessage?: string
}

export interface UploadBatchResult {
  uploaded: Array<{
    id?: number
    original_name: string
    relative_path: string
    row_count?: number
  }>
  skipped: string[]
  message: string
  fileResults: UploadFileResult[]
}

export interface DatasetRow {
  id: number
  original_name: string
  relative_path: string
  row_count: number
  uploaded_at: string
  source_type?: string
}

export interface DatasetPreviewData {
  columns?: string[]
  rows?: Array<Record<string, unknown>>
  total_rows?: number
}

export interface DatasetTablePageEvent {
  page?: number
  rows?: number
}

export interface DatasetTableSortEvent {
  sortField?: string
  sortOrder?: 1 | 0 | -1
}

export interface QualitySummary {
  covered_municipalities?: number
  canonical_reference_total?: number
  coverage_ratio?: number
  unresolved_rows?: number
  unresolved_labels?: Array<{
    label: string
    count: number
  }>
  alias_collisions?: Array<{
    canonical: string
    variant_count: number
    variants?: string[]
  }>
}

export interface TrainingDatasetSummary {
  exists?: boolean
  rows?: number
  relative_path?: string
  updated_at?: string
}

export interface UploadCapacitySummary {
  max_upload_size_bytes?: number
  free_disk_bytes?: number
  recommended_max_upload_bytes?: number
  reserve_disk_bytes?: number
}
