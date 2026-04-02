"""Training, prediction, and model schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrainRequest(BaseModel):
    csv_path: str


class TrainStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    progress: int = 0
    rows: int | None = None
    current_model: str | None = None
    current_model_index: int | None = None
    total_models: int | None = None
    current_model_progress: int | None = None
    fitted_trees: int | None = None
    total_trees: int | None = None
    elapsed_sec: float | None = None
    eta_sec: float | None = None
    result: dict | None = None
    error: str | None = None


class TrainJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    status: str
    stage: str | None = None
    progress: int = 0
    rows: int | None = None
    current_model: str | None = None
    current_model_index: int | None = None
    total_models: int | None = None
    current_model_progress: int | None = None
    fitted_trees: int | None = None
    total_trees: int | None = None
    elapsed_sec: float | None = None
    eta_sec: float | None = None
    duration_sec: float | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class PredictRequest(BaseModel):
    size_m2: float = Field(..., ge=1, le=50000)
    rooms: float | None = Field(default=None, ge=0, le=100)
    year_built: int | None = Field(default=None, ge=1800, le=2030)
    floor: int | None = Field(default=None, ge=-5, le=100)
    latitude: float | None = None
    longitude: float | None = None
    municipality: str | None = None
    property_type: str = "stanovanje"
    novogradnja: int | None = None
    has_klet: int | None = None
    has_garaza: int | None = None
    has_terasa: int | None = None
    has_shramba: int | None = None
    num_prostori: int | None = None
    transaction_year: int | None = None
    uporabna_povrsina: float | None = None
    parcela_m2: float | None = Field(default=None, ge=0)
    prodani_delez_parcele: float | None = Field(default=None, ge=0)
    prodani_delez_dela_stavbe: float | None = Field(default=None, ge=0)
    gradbena_faza: int | None = Field(default=None, ge=1, le=6)
    stopnja_ddv: float | None = Field(default=None, ge=0, le=100)
    evidentiranost_dela_stavbe: int | None = Field(default=None, ge=0, le=1)
    atrij: int | None = Field(default=None, ge=0, le=1)
    ime_ko: str | None = None
    naselje: str | None = None
    vrsta_dela_stavbe: str | None = None
    vrsta_zemljisca: str | None = None
    vrsta_kupoprodajnega_posla: str | None = None
    lega_v_stavbi: str | None = None
    stavba_je_dokoncana: int | None = None
    ddv_vkljucen: int | None = None


class PredictResponse(BaseModel):
    predicted_price_eur: float
    model_used: str
    routing_mode: str | None = None
    type_blend_weight: float | None = None
    calibration_factor: float | None = None
    calibration_source: str | None = None
    features_used: dict


class ModelInfoResponse(BaseModel):
    version: str | None = None
    trained_at: str | None = None
    rows: int | None = None
    train_rows: int | None = None
    test_rows: int | None = None
    duration_sec: float | None = None
    global_metrics: dict | None = None
    per_type_metrics: dict | None = None
    per_region_metrics: dict | None = None
    global_importance: dict | None = None
    feature_labels: dict | None = None
    per_type_features: dict | None = None
    per_type_count: int = 0
    coords_by_municipality: dict[str, dict] | None = None
    combined_metrics: dict | None = None
    deploy_window: dict | None = None
    holdout: dict | None = None
    calibration: dict | None = None
    variant_matrix: dict | None = None
    variant_benchmarks: dict | None = None
    type_models_trained: list[str] | None = None
    used_features: list[str] | None = None
    model_type: str | None = None
    source_csv_path: str | None = None
    data_preparation: dict | None = None
    segment_diagnostics: dict | None = None
