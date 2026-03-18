// Domain types matching the FastAPI Pydantic schemas

export interface User {
  id: number
  email: string
  full_name: string | null
  avatar_url: string | null
  role: 'admin' | 'viewer'
  is_active: boolean
  created_at: string
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
