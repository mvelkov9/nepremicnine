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
    duration_sec: float | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class PredictRequest(BaseModel):
    size_m2: float = Field(..., ge=1, le=50000)
    rooms: float | None = Field(default=None, ge=0, le=100)
    year_built: int | None = Field(default=None, ge=1800, le=2030)
    floor: int | None = Field(default=None, ge=-5, le=100)
    latitude: float | None = Field(default=None, ge=45.0, le=47.0)
    longitude: float | None = Field(default=None, ge=13.0, le=17.0)
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
    lega_v_stavbi: str | None = None
    stavba_je_dokoncana: int | None = None
    ddv_vkljucen: int | None = None


class PredictResponse(BaseModel):
    predicted_price_eur: float
    model_used: str
    features_used: dict


class ModelInfoResponse(BaseModel):
    version: str | None = None
    trained_at: str | None = None
    rows: int | None = None
    duration_sec: float | None = None
    global_metrics: dict | None = None
    per_type_metrics: dict | None = None
    per_region_metrics: dict | None = None
    global_importance: dict | None = None
    feature_labels: dict | None = None
    per_type_count: int = 0
    coords_by_municipality: dict[str, dict] | None = None
    combined_metrics: dict | None = None
    type_models_trained: list[str] | None = None
