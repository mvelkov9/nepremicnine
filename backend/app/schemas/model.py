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


class BenchmarkMetricSummary(BaseModel):
    mae: float | None = None
    rmse: float | None = None
    r2: float | None = None
    mape: float | None = None
    median_ae: float | None = None


class BenchmarkImprovementSummary(BaseModel):
    mae: float | None = None
    rmse: float | None = None
    median_ae: float | None = None
    mape: float | None = None
    r2: float | None = None
    avg_gain_eur: float | None = None
    median_gain_eur: float | None = None


class BenchmarkWinnerSummary(BaseModel):
    model: int = 0
    gurs: int = 0
    tie: int = 0


class BenchmarkSegmentSummary(BaseModel):
    segment: str
    count: int
    model_win_rate: float
    avg_gain_eur: float
    median_gain_eur: float
    model_mae: float | None = None
    gurs_mae: float | None = None


class BenchmarkSummaryResponse(BaseModel):
    coverage_rows: int = 0
    model_metrics: BenchmarkMetricSummary | None = None
    gurs_metrics: BenchmarkMetricSummary | None = None
    improvement_vs_gurs: BenchmarkImprovementSummary | None = None
    winners: BenchmarkWinnerSummary = Field(default_factory=BenchmarkWinnerSummary)
    top_regions: list[BenchmarkSegmentSummary] = Field(default_factory=list)
    top_property_types: list[BenchmarkSegmentSummary] = Field(default_factory=list)
    top_years: list[BenchmarkSegmentSummary] = Field(default_factory=list)
    methodology: str = "shared_gurs_coverage_holdout"
    status: str = "ready"
    detail: str | None = None


class BenchmarkProofRow(BaseModel):
    id: str
    municipality: str | None = None
    slug: str | None = None
    region: str | None = None
    property_type: str | None = None
    vrsta_kupoprodajnega_posla: str | None = None
    transaction_year: int | None = None
    year_built: int | None = None
    size_m2: float | None = None
    price_eur: float
    model_price_eur: float
    gurs_price_eur: float
    model_abs_error: float
    gurs_abs_error: float
    improvement_eur: float
    improvement_pct: float
    winner: str
    source_label: str | None = None
    ev_benchmark_source: str | None = None


class BenchmarkProofResponse(BaseModel):
    items: list[BenchmarkProofRow]
    total: int
    page: int
    page_size: int
    pages: int
    filters: dict
    sort: str
    order: str
