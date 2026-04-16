export interface ModelSourceOption {
  label: string
  value: string
}

export interface ModelSourceMeta {
  name?: string
  original_name?: string | null
  row_count?: number | null
  rows?: number | null
  updated_at?: string | null
  uploaded_at?: string | null
  relative_path?: string | null
}

export interface ModelTrainingCard {
  label: string
  value: string
  meta?: string
  tone?: 'default' | 'success' | 'warning'
}

export interface ModelTrainingStatus {
  status: string
  stage?: string | null
  progress?: number | null
  current_model?: string | null
  current_model_index?: number | null
  total_models?: number | null
  current_model_progress?: number | null
  fitted_trees?: number | null
  total_trees?: number | null
  elapsed_sec?: number | null
  eta_sec?: number | null
  error?: string | null
}

export interface ModelGlobalMetrics {
  mae?: number | null
  rmse?: number | null
  r2?: number | null
  mape?: number | null
  median_ae?: number | null
}

export interface ModelPerTypeMetrics {
  mae?: number | null
  rmse?: number | null
  r2?: number | null
  mape?: number | null
  n_train?: number | null
}

export interface ModelInfo {
  trained_at?: string | null
  rows?: number | null
  duration_sec?: number | null
  source_csv_path?: string | null
  global_metrics?: ModelGlobalMetrics | null
  per_type_metrics?: Record<string, ModelPerTypeMetrics> | null
}

export interface ModelResearchDraggingRow {
  property_type: string
  r2?: number | null
  mape?: number | null
  n_test?: number | null
  top_features?: Array<{ feature?: string | null }> | null
}

export interface ModelResearchAuditRow {
  property_type: string
  feature_load?: string | null
  selected_total?: number | null
  selected_numeric?: number | null
  selected_categorical?: number | null
  chosen_feature_variant?: string | null
  chosen_target_transform?: string | null
  training_policy?: string | null
  routing_mode?: string | null
  blend_weight?: number | null
  top_features?: Array<{ feature?: string | null }> | null
}

export interface ModelResearchImpact {
  generated_at?: string | null
  best_run?: {
    label?: string | null
    combined_metrics?: {
      r2?: number | null
      mape?: number | null
    } | null
  } | null
  dragging_segments?: ModelResearchDraggingRow[]
  per_type_feature_audit?: ModelResearchAuditRow[]
}

export interface ModelFeatureImportance {
  label: string
  importance: number
}
