"""Data management routes: upload, list, delete, preview, ETN prepare."""

import contextlib
import hashlib
import json
import logging
import os
import pathlib
import re
import sqlite3
import uuid
import zipfile
from collections import Counter
from datetime import UTC, datetime
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models.dataset import DatasetFile
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.dataset import (
    DatasetFileResponse,
    DatasetPreviewResponse,
    DatasetUploadResponse,
    TrainingDatasetResponse,
    UploadCapacityResponse,
)
from app.services.data_processing_service import (
    compute_file_sha256,
    ensure_directory_headroom,
    estimate_zip_uncompressed_size,
    extract_zip_csvs,
    extract_zip_supported_files,
    get_available_disk_bytes,
    import_rpe_rn,
    inspect_gpkg,
    inspect_csv,
    load_training_metadata,
    prepare_training_csv,
    prepare_training_csv_from_etn_kpp,
    prepare_training_csv_from_etn_kpp_bulk,
    read_csv_flexible,
)
from app.services.regions_service import CANONICAL_REGION_ROWS
from app.utils.cache import invalidate_request_caches
from app.utils.municipality import normalize_municipality_name
from app.utils.slovenian_labels import format_municipality_label, is_unknown_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])

DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_SIZE = get_settings().max_upload_size_mb * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".zip", ".gpkg"}
UPLOAD_DISK_RESERVE_BYTES = 2 * 1024 * 1024 * 1024
UPLOAD_STREAM_CHUNK_SIZE = 8 * 1024 * 1024


def _resolve_data_path(raw_path: str) -> str:
    candidate = raw_path if os.path.isabs(raw_path) else os.path.join(DATA_DIR, raw_path)
    return os.path.realpath(candidate)


def _to_relative_data_path(resolved_path: str) -> str:
    return os.path.relpath(resolved_path, DATA_DIR).replace("\\", "/")


def _serialize_dataset(record: DatasetFile) -> DatasetFileResponse:
    return DatasetFileResponse(
        id=record.id,
        original_name=record.original_name,
        relative_path=_to_relative_data_path(record.stored_path),
        source_type=record.source_type,
        row_count=record.row_count,
        columns_json=record.columns_json,
        file_hash=record.file_hash,
        uploaded_at=record.uploaded_at,
    )


def _get_upload_capacity() -> UploadCapacityResponse:
    free_disk_bytes = get_available_disk_bytes(UPLOAD_DIR)
    return UploadCapacityResponse(
        max_upload_size_mb=get_settings().max_upload_size_mb,
        max_upload_size_bytes=MAX_UPLOAD_SIZE,
        free_disk_bytes=free_disk_bytes,
        reserve_disk_bytes=UPLOAD_DISK_RESERVE_BYTES,
        recommended_max_upload_bytes=max(0, free_disk_bytes - UPLOAD_DISK_RESERVE_BYTES),
    )


def _remove_file_if_exists(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)


async def _stream_upload_to_disk(file: UploadFile, destination_path: str) -> tuple[int, str]:
    file_size = 0
    hasher = hashlib.sha256()

    with open(destination_path, "wb") as output:
        while True:
            chunk = await file.read(UPLOAD_STREAM_CHUNK_SIZE)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"File exceeds {MAX_UPLOAD_SIZE // (1024 * 1024)} MB limit",
                )
            output.write(chunk)
            hasher.update(chunk)

    await file.close()
    return file_size, hasher.hexdigest()


def _get_training_dataset_metadata() -> TrainingDatasetResponse:
    relative_path = _to_relative_data_path(TRAIN_CSV)
    if not os.path.exists(TRAIN_CSV):
        return TrainingDatasetResponse(exists=False, relative_path=relative_path)

    rows = None
    columns: list[str] = []
    preparation_metadata = load_training_metadata(TRAIN_CSV)
    try:
        df = read_csv_flexible(TRAIN_CSV)
        rows = len(df)
        columns = list(df.columns)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError, OSError):
        logger.exception("Failed to inspect prepared training dataset %s", TRAIN_CSV)

    return TrainingDatasetResponse(
        exists=True,
        relative_path=relative_path,
        rows=rows,
        columns=columns,
        updated_at=datetime.fromtimestamp(os.path.getmtime(TRAIN_CSV), UTC),
        size_bytes=os.path.getsize(TRAIN_CSV),
        preparation_metadata=preparation_metadata,
    )


def _validate_path_within_data_dir(raw_path: str) -> str:
    """Resolve a path and ensure it stays within DATA_DIR. Raises 400 on traversal or symlink."""
    resolved = _resolve_data_path(raw_path)
    if not resolved.startswith(DATA_DIR + os.sep) and resolved != DATA_DIR:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Path is outside the allowed data directory")
    raw_candidate = raw_path if os.path.isabs(raw_path) else os.path.join(DATA_DIR, raw_path)
    if os.path.islink(raw_candidate):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Symbolic links are not allowed")
    return resolved


def _build_quality_summary() -> dict:
    reference_total = len(CANONICAL_REGION_ROWS)
    if not os.path.exists(TRAIN_CSV):
        return {
            "training_dataset_exists": False,
            "canonical_reference_total": reference_total,
            "covered_municipalities": 0,
            "unresolved_rows": 0,
            "unresolved_labels": [],
            "alias_collisions": [],
        }

    df = read_csv_flexible(TRAIN_CSV)
    if "municipality" not in df.columns:
        return {
            "training_dataset_exists": True,
            "canonical_reference_total": reference_total,
            "covered_municipalities": 0,
            "unresolved_rows": 0,
            "unresolved_labels": [],
            "alias_collisions": [],
        }

    raw_values = df["municipality"].fillna("").astype(str)
    canonical_labels = raw_values.map(format_municipality_label)
    normalized = canonical_labels.map(normalize_municipality_name)
    known_mask = canonical_labels.map(lambda value: value is not None and not is_unknown_label(value))

    unresolved_labels = Counter(raw_values[~known_mask])
    collision_map: dict[str, set[str]] = {}
    for raw, canonical in zip(raw_values, canonical_labels, strict=False):
        if canonical is None:
            continue
        collision_map.setdefault(str(canonical), set()).add(str(raw).strip())

    alias_collisions = [
        {"canonical": canonical, "variants": sorted(variants), "variant_count": len(variants)}
        for canonical, variants in collision_map.items()
        if len(variants) > 1
    ]
    alias_collisions.sort(key=lambda item: item["variant_count"], reverse=True)

    covered = int(normalized[known_mask].nunique())
    return {
        "training_dataset_exists": True,
        "canonical_reference_total": reference_total,
        "covered_municipalities": covered,
        "coverage_ratio": round(covered / max(reference_total, 1), 4),
        "unresolved_rows": int((~known_mask).sum()),
        "unresolved_labels": [
            {"label": label or "unknown", "count": int(count)} for label, count in unresolved_labels.most_common(12)
        ],
        "alias_collisions": alias_collisions[:12],
    }


@router.get("/upload-capacity", response_model=UploadCapacityResponse)
async def get_upload_capacity(_user: User = Depends(require_admin)):
    return _get_upload_capacity()


@router.post("/upload", response_model=DatasetUploadResponse)
@limiter.limit("60/minute")
async def upload_files(
    request: Request,
    files: list[UploadFile],
    source_type: Literal["csv", "etn", "rpe"] = "csv",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    uploaded = []
    skipped = []

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        try:
            ensure_directory_headroom(UPLOAD_DIR, int(content_length), UPLOAD_DISK_RESERVE_BYTES)
        except OSError as exc:
            raise HTTPException(
                status.HTTP_507_INSUFFICIENT_STORAGE,
                f"Not enough disk space to receive upload safely: {exc}",
            ) from exc

    for file in files:
        # Validate file extension
        ext = os.path.splitext(file.filename or "file.csv")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"File type '{ext}' not allowed. Only .csv, .zip, and .gpkg accepted.",
            )

        # Save to disk — sanitise filename to prevent path injection
        safe_filename = pathlib.Path(file.filename or "upload").name
        safe_filename = re.sub(r"[^\w.\-]", "_", safe_filename)[:200] or "upload"
        stored_name = f"{uuid.uuid4().hex}_{safe_filename}"
        stored_path = os.path.join(UPLOAD_DIR, stored_name)
        try:
            file_size, file_hash = await _stream_upload_to_disk(file, stored_path)
        except Exception:
            _remove_file_if_exists(stored_path)
            raise

        try:
            ensure_directory_headroom(UPLOAD_DIR, 0, UPLOAD_DISK_RESERVE_BYTES)
        except OSError as exc:
            _remove_file_if_exists(stored_path)
            raise HTTPException(
                status.HTTP_507_INSUFFICIENT_STORAGE,
                f"Not enough disk space to continue upload safely: {exc}",
            ) from exc

        # Dedup check
        existing = await db.execute(select(DatasetFile).where(DatasetFile.file_hash == file_hash))
        if existing.scalar_one_or_none():
            _remove_file_if_exists(stored_path)
            skipped.append(file.filename or "unknown")
            continue

        # Handle ZIP files: extract CSVs and GeoPackages
        if ext == ".zip":
            try:
                estimated_uncompressed = estimate_zip_uncompressed_size(stored_path)
                ensure_directory_headroom(UPLOAD_DIR, estimated_uncompressed, UPLOAD_DISK_RESERVE_BYTES)
                csv_paths, gpkg_paths = extract_zip_supported_files(
                    stored_path,
                    UPLOAD_DIR,
                    reserve_bytes=UPLOAD_DISK_RESERVE_BYTES,
                )
                if not csv_paths and not gpkg_paths:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                        "ZIP contains no supported CSV or GeoPackage files to import.",
                    )
            except OSError as exc:
                _remove_file_if_exists(stored_path)
                raise HTTPException(
                    status.HTTP_507_INSUFFICIENT_STORAGE,
                    f"Not enough disk space to extract ZIP safely: {exc}",
                ) from exc
            except HTTPException:
                _remove_file_if_exists(stored_path)
                raise
            except Exception as exc:
                _remove_file_if_exists(stored_path)
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Bad ZIP: {exc}") from exc
            _remove_file_if_exists(stored_path)  # remove original zip

            for csv_path in csv_paths:
                csv_hash = hashlib.sha256()
                with open(csv_path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        csv_hash.update(chunk)
                csv_hash_hex = csv_hash.hexdigest()
                dup = await db.execute(select(DatasetFile).where(DatasetFile.file_hash == csv_hash_hex))
                if dup.scalar_one_or_none():
                    _remove_file_if_exists(csv_path)
                    skipped.append(os.path.basename(csv_path))
                    continue

                row_count = None
                columns_json = None
                try:
                    df = read_csv_flexible(csv_path)
                    columns_json = json.dumps(list(df.columns))
                    row_count = len(df)
                except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError, OSError):
                    logger.exception("Failed to read CSV metadata from extracted file %s", csv_path)

                record = DatasetFile(
                    original_name=os.path.basename(csv_path),
                    stored_path=csv_path,
                    source_type="csv",
                    row_count=row_count,
                    columns_json=columns_json,
                    file_hash=csv_hash_hex,
                    uploaded_by=user.id,
                )
                db.add(record)
                await db.flush()
                await db.refresh(record)
                uploaded.append(record)

            for gpkg_path in gpkg_paths:
                gpkg_hash = compute_file_sha256(gpkg_path)
                dup = await db.execute(select(DatasetFile).where(DatasetFile.file_hash == gpkg_hash))
                if dup.scalar_one_or_none():
                    _remove_file_if_exists(gpkg_path)
                    skipped.append(os.path.basename(gpkg_path))
                    continue

                gpkg_preview = inspect_gpkg(gpkg_path, preview_rows=0)
                record = DatasetFile(
                    original_name=os.path.basename(gpkg_path),
                    stored_path=gpkg_path,
                    source_type="gpkg",
                    row_count=None,
                    columns_json=json.dumps(gpkg_preview.get("layers", [])),
                    file_hash=gpkg_hash,
                    uploaded_by=user.id,
                )
                db.add(record)
                await db.flush()
                await db.refresh(record)
                uploaded.append(record)
            continue

        # Regular CSV / GeoPackage
        row_count = None
        columns_json = None
        if ext == ".csv":
            try:
                df = read_csv_flexible(stored_path)
                columns_json = json.dumps(list(df.columns))
                row_count = len(df)
            except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError, OSError):
                logger.exception("Failed to read CSV metadata from %s", stored_path)
        elif ext == ".gpkg":
            try:
                gpkg_preview = inspect_gpkg(stored_path, preview_rows=0)
                columns_json = json.dumps(gpkg_preview.get("layers", []))
            except (sqlite3.DatabaseError, OSError, ValueError):
                logger.exception("Failed to inspect GeoPackage metadata from %s", stored_path)

        record = DatasetFile(
            original_name=file.filename or "unknown",
            stored_path=stored_path,
            source_type="gpkg" if ext == ".gpkg" else source_type,
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
        uploaded=[_serialize_dataset(r) for r in uploaded],
        skipped=skipped,
        message=msg,
    )


@router.get("/datasets")
async def list_datasets(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    import math

    offset = (page - 1) * per_page
    stmt = (
        select(DatasetFile, func.count(DatasetFile.id).over().label("total_count"))
        .order_by(DatasetFile.uploaded_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    total = rows[0].total_count if rows else 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    items = [_serialize_dataset(r.DatasetFile) for r in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/training-dataset", response_model=TrainingDatasetResponse)
async def training_dataset(_user: User = Depends(get_current_user)):
    """Expose the prepared train.csv artifact so the frontend can guide users into training."""
    return _get_training_dataset_metadata()


@router.get("/quality-summary")
async def quality_summary(_user: User = Depends(require_admin)):
    """Expose training-data quality signals for municipality/reference debugging."""
    return _build_quality_summary()


@router.get("/preview/{dataset_id}", response_model=DatasetPreviewResponse)
async def preview_dataset(
    dataset_id: int,
    limit: int = Query(50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(select(DatasetFile).where(DatasetFile.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not os.path.exists(dataset.stored_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    if dataset.source_type == "gpkg" or dataset.stored_path.lower().endswith(".gpkg"):
        try:
            preview = inspect_gpkg(dataset.stored_path, preview_rows=limit)
            return DatasetPreviewResponse(
                columns=preview.get("columns", []),
                rows=preview.get("rows", []),
                total_rows=int(preview.get("total_rows", 0)),
            )
        except (sqlite3.DatabaseError, OSError, ValueError):
            logger.exception("Cannot read GeoPackage file %s for preview", dataset.stored_path)
            raise HTTPException(status_code=500, detail="Cannot read the GeoPackage file") from None

    try:
        df = pd.read_csv(dataset.stored_path, nrows=limit)
        return DatasetPreviewResponse(
            columns=list(df.columns),
            rows=df.fillna("").to_dict(orient="records"),
            total_rows=dataset.row_count or len(df),
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError, OSError):
        logger.exception("Cannot read dataset file %s for preview", dataset.stored_path)
        raise HTTPException(status_code=500, detail="Cannot read the dataset file") from None


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
    await db.commit()


class BulkDeleteRequest(BaseModel):
    dataset_ids: list[int] = Field(..., max_length=500)


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
    request: Request,
    _user: User = Depends(require_admin),
):
    """Prepare training CSV from a single ETN KPP posli+delistavb pair."""
    posli = _validate_path_within_data_dir(req.posli_csv_path)
    delistavb = _validate_path_within_data_dir(req.delistavb_csv_path)
    try:
        result = prepare_training_csv_from_etn_kpp(posli, delistavb, TRAIN_CSV)
    except ValueError as exc:
        logger.warning("ETN KPP preparation rejected: %s", exc)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:
        logger.error("ETN KPP preparation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Data preparation failed. Check server logs."
        ) from exc
    result["output_csv_path"] = _to_relative_data_path(TRAIN_CSV)
    result["training_dataset"] = _get_training_dataset_metadata().model_dump(mode="json")
    await invalidate_request_caches(request)
    return result


class EtnBulkPair(BaseModel):
    posli_csv_path: str
    delistavb_csv_path: str
    zemljisca_csv_path: str | None = None
    label: str | None = None
    year: str | None = None


class EtnBulkRequest(BaseModel):
    pairs: list[EtnBulkPair] = Field(..., max_length=50)


@router.post("/prepare-etn-kpp-bulk")
async def prepare_etn_kpp_bulk(
    req: EtnBulkRequest,
    request: Request,
    _user: User = Depends(require_admin),
):
    """Prepare training CSV from multiple ETN KPP pairs (multi-year)."""
    pairs_dicts = []
    for pair in req.pairs:
        resolved_pair = pair.model_dump()
        resolved_pair["posli_csv_path"] = _validate_path_within_data_dir(pair.posli_csv_path)
        resolved_pair["delistavb_csv_path"] = _validate_path_within_data_dir(pair.delistavb_csv_path)
        if pair.zemljisca_csv_path:
            resolved_pair["zemljisca_csv_path"] = _validate_path_within_data_dir(pair.zemljisca_csv_path)
        pairs_dicts.append(resolved_pair)
    try:
        result = prepare_training_csv_from_etn_kpp_bulk(pairs_dicts, TRAIN_CSV)
    except ValueError as exc:
        logger.warning("ETN KPP bulk preparation rejected: %s", exc)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:
        logger.error("ETN KPP bulk preparation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Data preparation failed. Check server logs."
        ) from exc
    result["output_csv_path"] = _to_relative_data_path(TRAIN_CSV)
    result["training_dataset"] = _get_training_dataset_metadata().model_dump(mode="json")
    await invalidate_request_caches(request)
    return result


class RpeRnImportRequest(BaseModel):
    rn_csv_path: str
    stat_regije_csv_path: str | None = None


@router.post("/regions/import-rpe-rn")
async def import_rpe_rn_endpoint(
    req: RpeRnImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Import RPE + RN data, store municipality→region mappings in DB."""
    from app.models.region import RegionLookup as RegionLookupModel

    rn_path = _validate_path_within_data_dir(req.rn_csv_path)
    stat_path = _validate_path_within_data_dir(req.stat_regije_csv_path) if req.stat_regije_csv_path else None
    try:
        result = import_rpe_rn(rn_path, stat_path, UPLOAD_DIR)
    except Exception as exc:
        logger.error("RPE/RN import failed: %s", exc, exc_info=True)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Region import failed. Check server logs.") from exc

    for m in result["mappings"]:
        # Skip if a record with same (obcina_naziv, vir) already exists
        vir_value = m.get("vir", "RPE/RN")
        existing = await db.execute(
            select(RegionLookupModel).where(
                RegionLookupModel.obcina_naziv == m["obcina_naziv"],
                RegionLookupModel.vir == vir_value,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        record = RegionLookupModel(
            obcina_sifra=m.get("obcina_sifra"),
            obcina_naziv=m["obcina_naziv"],
            regija_naziv=m["regija_naziv"],
            vir=vir_value,
        )
        db.add(record)
    await db.commit()

    await invalidate_request_caches(request)
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
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError, OSError):
        logger.exception("Cannot inspect dataset file %s", dataset.stored_path)
        raise HTTPException(status_code=500, detail="Cannot inspect the dataset file") from None


class PrepareTrainRequest(BaseModel):
    source_csv_path: str
    column_map: dict[str, str]


@router.post("/prepare-train")
async def prepare_train(
    req: PrepareTrainRequest,
    request: Request,
    _user: User = Depends(require_admin),
):
    """Prepare training CSV from a source CSV with custom column mapping."""
    source = _validate_path_within_data_dir(req.source_csv_path)
    try:
        result = prepare_training_csv(source, req.column_map, TRAIN_CSV)
    except ValueError as exc:
        logger.warning("Training CSV preparation rejected: %s", exc)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:
        logger.error("Training CSV preparation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Data preparation failed. Check server logs."
        ) from exc
    result["output_csv_path"] = _to_relative_data_path(TRAIN_CSV)
    result["training_dataset"] = _get_training_dataset_metadata().model_dump(mode="json")
    await invalidate_request_caches(request)
    return result
