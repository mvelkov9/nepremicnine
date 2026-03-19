"""Dataset file schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class DatasetFileResponse(BaseModel):
    id: int
    original_name: str
    relative_path: str
    source_type: str
    row_count: int | None = None
    columns_json: str | None = None
    file_hash: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DatasetUploadResponse(BaseModel):
    uploaded: list[DatasetFileResponse]
    skipped: list[str]
    message: str


class DatasetPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict]
    total_rows: int


class TrainingDatasetResponse(BaseModel):
    exists: bool
    relative_path: str
    rows: int | None = None
    columns: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    size_bytes: int | None = None
    preparation_metadata: dict | None = None
