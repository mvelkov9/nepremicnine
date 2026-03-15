"""Training, prediction, and model schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
    size_m2: float
    rooms: float | None = None
    year_built: int | None = None
    floor: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    municipality: str | None = None
    property_type: str = "stanovanje"


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
