// Domain types matching the FastAPI Pydantic schemas

export interface User {
  id: number
  email: string
  full_name: string | null
  avatar_url: string | null
  role: 'admin' | 'viewer'
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface Dataset {
  id: number
  original_name: string
  stored_path: string
  source_type: string
  row_count: number
  columns_json: string[]
  file_hash: string
  uploaded_by: number | null
  uploaded_at: string
}

export interface TrainingJob {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  stage: string | null
  progress: number
  current_model: string | null
  current_model_index: number
  total_models: number
  elapsed_sec: number
  eta_sec: number | null
  error: string | null
}

export interface ModelRun {
  id: number
  model_type: string
  rows: number
  mae: number
  rmse: number
  r2: number
  mape: number | null
  median_ae: number | null
  duration_sec: number
  trained_by: number | null
  created_at: string
}

export interface ModelInfo {
  version: string
  trained_at: string
  algorithm: string
  r2: number
  mae: number
  rmse: number
  row_count: number
  property_types: string[]
}

export interface PredictionPayload {
  property_type: string
  obcina: string
  površina: number
  leto_izgradnje?: number | null
  lega_v_stavbi?: string | null
  nadstropje?: number | null
  stevilo_sob?: number | null
}

export interface PredictionResult {
  predicted_price_eur: number
  confidence_interval?: [number, number]
  used_features: Record<string, unknown>
}

export interface RegionLookup {
  obcina_sifra: number
  obcina_naziv: string
  regija_naziv: string
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'error'
  version: string
  database: string
  redis: string
  model: string | null
}

export interface TrendPoint {
  year: number | string
  count?: number
  avg_price?: number
  median_price?: number
  avg_price_per_m2?: number
  median_price_per_m2?: number
  by_type?: Record<string, { count?: number; avg_price?: number; median_price?: number }>
}

export interface RegionStat {
  region: string
  count: number
  avg_price?: number
  median_price?: number
  avg_price_per_m2?: number
  median_price_per_m2?: number
}

export interface FeatureImportance {
  feature: string
  label: string
  importance: number
}

export interface MunicipalityStat {
  municipality: string
  slug: string
  region?: string
  count: number
  median_price?: number
  median_price_per_m2?: number
}

export interface PropertyTypeMix {
  property_type: string
  count: number
  share: number
}

export interface PriceDistribution {
  bins: number[]
  counts: number[]
  bin_labels: string[]
}

export interface TransactionRecord {
  id: string
  municipality: string
  slug: string
  naselje?: string | null
  region?: string | null
  property_type?: string | null
  price_eur?: number | null
  size_m2?: number | null
  uporabna_povrsina?: number | null
  price_per_m2?: number | null
  year?: string | null
  source_label?: string | null
  year_built?: number | null
  rooms?: number | null
  floor?: number | null
  num_prostori?: number | null
  lega_v_stavbi?: string | null
  lat?: number | null
  lon?: number | null
  novogradnja?: number | null
  has_garaza?: number | null
  has_klet?: number | null
  has_terasa?: number | null
  has_shramba?: number | null
  stavba_je_dokoncana?: number | null
  ddv_vkljucen?: number | null
  similarity_score?: number | null
  size_delta_m2?: number | null
  price_delta_eur?: number | null
  price_delta_pct?: number | null
}

export interface ExplorerFilters {
  property_type?: string | null
  region?: string | null
  municipality?: string | null
  year?: string | null
  search?: string | null
}

export interface ExplorerResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
  filters: ExplorerFilters
  sort: string
  order: string
}

export interface ServerTableState {
  page: number
  pageSize: number
  sort: string
  order: 'asc' | 'desc'
  search: string
  filters: Record<string, string>
  visibleColumns?: string[]
}

export interface ServerTableResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
  filters: Record<string, unknown>
  sort: string
  order: string
}

export interface MunicipalityExplorerItem extends MunicipalityStat {
  avg_price?: number | null
  avg_price_per_m2?: number | null
  latest_year?: string | null
}

export interface RegionExplorerItem extends RegionStat {
  municipality_count?: number
  latest_year?: string | null
}

export interface BenchmarkMetricSummary {
  mae?: number | null
  rmse?: number | null
  r2?: number | null
  mape?: number | null
  median_ae?: number | null
}

export interface BenchmarkImprovementSummary {
  mae?: number | null
  rmse?: number | null
  median_ae?: number | null
  mape?: number | null
  r2?: number | null
  avg_gain_eur?: number | null
  median_gain_eur?: number | null
}

export interface BenchmarkWinnerSummary {
  model: number
  gurs: number
  tie: number
}

export interface BenchmarkSegmentSummary {
  segment: string
  count: number
  model_win_rate: number
  avg_gain_eur: number
  median_gain_eur: number
  model_mae?: number | null
  gurs_mae?: number | null
}

export interface BenchmarkSummaryResponse {
  coverage_rows: number
  model_metrics: BenchmarkMetricSummary | null
  gurs_metrics: BenchmarkMetricSummary | null
  improvement_vs_gurs: BenchmarkImprovementSummary | null
  winners: BenchmarkWinnerSummary
  top_regions: BenchmarkSegmentSummary[]
  top_property_types: BenchmarkSegmentSummary[]
  top_years: BenchmarkSegmentSummary[]
  methodology: string
  status?: string
  detail?: string | null
}

export interface BenchmarkProofRow {
  id: string
  municipality?: string | null
  slug?: string | null
  region?: string | null
  property_type?: string | null
  vrsta_kupoprodajnega_posla?: string | null
  transaction_year?: number | null
  year_built?: number | null
  size_m2?: number | null
  price_eur: number
  model_price_eur: number
  gurs_price_eur: number
  model_abs_error: number
  gurs_abs_error: number
  improvement_eur: number
  improvement_pct: number
  winner: string
  source_label?: string | null
  ev_benchmark_source?: string | null
}

export interface SavedWorkspace {
  id: number
  name: string
  scope: string
  page: string
  filters: Record<string, unknown>
  tab?: string | null
  sort?: string | null
  columns: string[]
  pinned: boolean
  created_at: string
  updated_at: string
}

export interface WatchlistItem {
  id: number
  entity_type: string
  entity_key: string
  display_label: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface WatchlistFeedItem {
  id: string
  entity_type: string
  entity_key: string
  display_label: string
  headline_value?: number | null
  headline_label?: string | null
  trend_value?: number | null
  trend_label?: string | null
  link?: string | null
  context: Record<string, unknown>
}

export interface ActivityFeedItem {
  id: string
  category: string
  title: string
  body?: string | null
  link?: string | null
  scope: string
  is_read: boolean
  created_at: string
  payload: Record<string, unknown>
}

export interface AdminRunSummary {
  id: string
  run_type: string
  status: string
  stage?: string | null
  progress?: number | null
  title: string
  summary?: string | null
  created_at: string
  updated_at?: string | null
}

export interface AdminRunDetail extends AdminRunSummary {
  timeline: Array<Record<string, unknown>>
  metrics: Array<Record<string, unknown>>
  artifacts: Array<Record<string, unknown>>
  context: Record<string, unknown>
}

export interface TableViewState {
  page?: string
  filters: Record<string, unknown>
  tab?: string | null
  sort?: string | null
  columns?: string[]
  pinned?: boolean
}

export interface CompareTrayItem {
  id: string
  entity_type: string
  label: string
  slug?: string
  region?: string | null
  metadata?: Record<string, unknown>
}

export interface NotificationItem extends ActivityFeedItem {}
