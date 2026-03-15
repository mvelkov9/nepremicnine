"""Data management routes: upload, list, delete, preview."""

import hashlib
import json
import os
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.dataset import DatasetFile
from app.models.user import User
from app.schemas.dataset import DatasetFileResponse, DatasetPreviewResponse, DatasetUploadResponse

router = APIRouter(prefix="/data", tags=["data"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_files(
    files: list[UploadFile],
    source_type: str = "csv",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    uploaded = []
    skipped = []

    for file in files:
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()

        # Dedup check
        existing = await db.execute(
            select(DatasetFile).where(DatasetFile.file_hash == file_hash)
        )
        if existing.scalar_one_or_none():
            skipped.append(file.filename or "unknown")
            continue

        # Save to disk
        ext = os.path.splitext(file.filename or "file.csv")[1]
        stored_name = f"{uuid.uuid4().hex}_{file.filename}"
        stored_path = os.path.join(UPLOAD_DIR, stored_name)
        with open(stored_path, "wb") as f:
            f.write(content)

        # Try to read CSV metadata
        row_count = None
        columns_json = None
        if ext.lower() == ".csv":
            try:
                df = pd.read_csv(stored_path, nrows=0)
                columns_json = json.dumps(list(df.columns))
                df_full = pd.read_csv(stored_path)
                row_count = len(df_full)
            except Exception:
                pass

        record = DatasetFile(
            original_name=file.filename or "unknown",
            stored_path=stored_path,
            source_type=source_type,
            row_count=row_count,
            columns_json=columns_json,
            file_hash=file_hash,
            uploaded_by=user.id,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        uploaded.append(record)

    msg = f"{len(uploaded)} uploaded, {len(skipped)} skipped (duplicate)"
    return DatasetUploadResponse(
        uploaded=[DatasetFileResponse.model_validate(r) for r in uploaded],
        skipped=skipped,
        message=msg,
    )


@router.get("/datasets", response_model=list[DatasetFileResponse])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DatasetFile).order_by(DatasetFile.uploaded_at.desc())
    )
    return result.scalars().all()


@router.get("/preview/{dataset_id}", response_model=DatasetPreviewResponse)
async def preview_dataset(
    dataset_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(DatasetFile).where(DatasetFile.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not os.path.exists(dataset.stored_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    try:
        df = pd.read_csv(dataset.stored_path, nrows=limit)
        return DatasetPreviewResponse(
            columns=list(df.columns),
            rows=df.fillna("").to_dict(orient="records"),
            total_rows=dataset.row_count or len(df),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot read file: {e}")


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    result = await db.execute(select(DatasetFile).where(DatasetFile.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Remove file from disk
    if os.path.exists(dataset.stored_path):
        os.remove(dataset.stored_path)

    await db.delete(dataset)
