"""Dataset file schemas."""

from datetime import datetime

from pydantic import BaseModel


class DatasetFileResponse(BaseModel):
    id: int
    original_name: str
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
