"""Data management routes: upload, list, delete, preview, ETN prepare."""

import hashlib
import json
import os
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.dataset import DatasetFile
from app.models.user import User
from app.schemas.dataset import (
    DatasetFileResponse,
    DatasetPreviewResponse,
    DatasetUploadResponse,
)
from app.services.data_processing_service import (
    extract_zip_csvs,
    import_rpe_rn,
    inspect_csv,
    prepare_training_csv_from_etn_kpp,
    prepare_training_csv_from_etn_kpp_bulk,
    read_csv_flexible,
)

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
        existing = await db.execute(select(DatasetFile).where(DatasetFile.file_hash == file_hash))
        if existing.scalar_one_or_none():
            skipped.append(file.filename or "unknown")
            continue

        # Save to disk
        ext = os.path.splitext(file.filename or "file.csv")[1].lower()
        stored_name = f"{uuid.uuid4().hex}_{file.filename}"
        stored_path = os.path.join(UPLOAD_DIR, stored_name)
        with open(stored_path, "wb") as f:
            f.write(content)

        # Handle ZIP files: extract CSVs
        if ext == ".zip":
            try:
                csv_paths = extract_zip_csvs(stored_path, UPLOAD_DIR)
            except Exception as exc:
                os.remove(stored_path)
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Bad ZIP: {exc}") from exc
            os.remove(stored_path)  # remove original zip

            for csv_path in csv_paths:
                with open(csv_path, "rb") as fh:
                    csv_hash = hashlib.sha256(fh.read()).hexdigest()
                dup = await db.execute(select(DatasetFile).where(DatasetFile.file_hash == csv_hash))
                if dup.scalar_one_or_none():
                    os.remove(csv_path)
                    skipped.append(os.path.basename(csv_path))
                    continue

                row_count = None
                columns_json = None
                try:
                    df = read_csv_flexible(csv_path)
                    columns_json = json.dumps(list(df.columns))
                    row_count = len(df)
                except Exception:
                    pass

                record = DatasetFile(
                    original_name=os.path.basename(csv_path),
                    stored_path=csv_path,
                    source_type="csv",
                    row_count=row_count,
                    columns_json=columns_json,
                    file_hash=csv_hash,
                    uploaded_by=user.id,
                )
                db.add(record)
                await db.flush()
                await db.refresh(record)
                uploaded.append(record)
            continue

        # Regular CSV
        row_count = None
        columns_json = None
        if ext == ".csv":
            try:
                df = read_csv_flexible(stored_path)
                columns_json = json.dumps(list(df.columns))
                row_count = len(df)
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
    result = await db.execute(select(DatasetFile).order_by(DatasetFile.uploaded_at.desc()))
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
        raise HTTPException(status_code=500, detail=f"Cannot read file: {e}") from e


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


class BulkDeleteRequest(BaseModel):
    dataset_ids: list[int]


@router.post("/datasets/delete-bulk", status_code=status.HTTP_200_OK)
async def delete_datasets_bulk(
    req: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Delete multiple datasets at once."""
    deleted = 0
    for did in req.dataset_ids:
        result = await db.execute(select(DatasetFile).where(DatasetFile.id == did))
        dataset = result.scalar_one_or_none()
        if dataset:
            if os.path.exists(dataset.stored_path):
                os.remove(dataset.stored_path)
            await db.delete(dataset)
            deleted += 1
    await db.commit()
    return {"deleted": deleted}


TRAIN_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw", "train.csv")


class EtnPrepareRequest(BaseModel):
    posli_csv_path: str
    delistavb_csv_path: str


@router.post("/prepare-etn-kpp")
async def prepare_etn_kpp(
    req: EtnPrepareRequest,
    _user: User = Depends(require_admin),
):
    """Prepare training CSV from a single ETN KPP posli+delistavb pair."""
    try:
        result = prepare_training_csv_from_etn_kpp(req.posli_csv_path, req.delistavb_csv_path, TRAIN_CSV)
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return result


class EtnBulkPair(BaseModel):
    posli_csv_path: str
    delistavb_csv_path: str
    zemljisca_csv_path: str | None = None
    label: str | None = None
    year: str | None = None


class EtnBulkRequest(BaseModel):
    pairs: list[EtnBulkPair]


@router.post("/prepare-etn-kpp-bulk")
async def prepare_etn_kpp_bulk(
    req: EtnBulkRequest,
    _user: User = Depends(require_admin),
):
    """Prepare training CSV from multiple ETN KPP pairs (multi-year)."""
    try:
        pairs_dicts = [p.model_dump() for p in req.pairs]
        result = prepare_training_csv_from_etn_kpp_bulk(pairs_dicts, TRAIN_CSV)
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return result


class RpeRnImportRequest(BaseModel):
    rn_csv_path: str
    stat_regije_csv_path: str | None = None


@router.post("/regions/import-rpe-rn")
async def import_rpe_rn_endpoint(
    req: RpeRnImportRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Import RPE + RN data, store municipality→region mappings in DB."""
    from app.models.region import RegionLookup as RegionLookupModel

    try:
        result = import_rpe_rn(req.rn_csv_path, req.stat_regije_csv_path, UPLOAD_DIR)
    except Exception as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    for m in result["mappings"]:
        record = RegionLookupModel(
            obcina_sifra=m.get("obcina_sifra"),
            obcina_naziv=m["obcina_naziv"],
            regija_naziv=m["regija_naziv"],
            vir=m.get("vir", "RPE/RN"),
        )
        db.add(record)
    await db.commit()

    return {"imported": result["count"], "regije": result["regije"]}


@router.get("/inspect/{dataset_id}")
async def inspect_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Inspect a dataset: columns, row count, preview rows."""
    result = await db.execute(select(DatasetFile).where(DatasetFile.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not os.path.exists(dataset.stored_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    try:
        return inspect_csv(dataset.stored_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot inspect: {e}") from e
