"""Data management routes: upload, list, delete, preview, ETN prepare."""

import contextlib
import hashlib
import io
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
from arq import create_pool
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
    DatasetRescanResponse,
    DatasetUploadResponse,
    PrepareJobStatusResponse,
    TrainingDatasetResponse,
    UploadCapacityResponse,
)
from app.services.data_processing_service import (
    compute_file_sha256,
    ensure_directory_headroom,
    estimate_zip_uncompressed_size,
    extract_zip_supported_files,
    get_available_disk_bytes,
    import_rpe_rn,
    inspect_csv,
    inspect_gpkg,
    inspect_shapefile_zip_with_cache,
    load_training_metadata,
    prepare_training_csv,
    prepare_training_csv_from_etn_kpp,
    prepare_training_csv_from_etn_kpp_bulk,
    read_csv_flexible,
)
from app.services.regions_service import CANONICAL_REGION_ROWS
from app.tasks.training_worker import PREPARE_ACTIVE_KEY, PREPARE_JOB_PREFIX, _parse_redis_url
from app.utils.cache import invalidate_request_caches
from app.utils.municipality import normalize_municipality_name
from app.utils.slovenian_labels import format_municipality_label, is_unknown_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])

# ETN files follow the pattern ETN_SLO_YYYY_{KPP|NP}_<date>.zip
_ETN_ZIP_PATTERN = re.compile(r"^ETN_SLO_\d{4}_(KPP|NP)_", re.IGNORECASE)

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


def _peek_zip_for_csv_preview(zip_path: str, limit: int) -> dict:
    """Open a ZIP and preview the first CSV found inside it."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_members = sorted(
            m for m in zf.namelist()
            if m.lower().endswith(".csv") and not m.startswith("__MACOSX")
        )
        if not csv_members:
            raise ValueError("No CSV found inside ZIP")
        csv_data = zf.read(csv_members[0])

    df = None
    last_exc: Exception | None = None
    for encoding in ("utf-8", "cp1250", "latin1"):
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(io.BytesIO(csv_data), encoding=encoding, sep=sep, nrows=limit, low_memory=False)
                break
            except Exception as e:
                last_exc = e
        if df is not None:
            break
    if df is None:
        raise ValueError(f"Cannot parse CSV inside ZIP: {last_exc}")

    return {
        "columns": list(df.columns),
        "rows": df.fillna("").to_dict(orient="records"),
        "total_rows": len(df),
    }


def _is_path_within(base_dir: str, candidate_path: str) -> bool:
    base_real = os.path.realpath(base_dir)
    cand_real = os.path.realpath(candidate_path)
    return cand_real == base_real or cand_real.startswith(base_real + os.sep)


async def _sync_upload_directory_records(db: AsyncSession) -> tuple[int, int]:
    """Index manually added upload files so they appear in the dataset library."""
    indexed_count = 0
    deleted_count = 0

    existing_records = (await db.execute(select(DatasetFile))).scalars().all()
    existing_by_path: dict[str, DatasetFile] = {}
    existing_hash_counts: dict[str, int] = {}

    for record in existing_records:
        resolved = os.path.realpath(record.stored_path)
        existing_by_path[resolved] = record
        existing_hash_counts[record.file_hash] = existing_hash_counts.get(record.file_hash, 0) + 1

    for record in existing_records:
        if os.path.exists(record.stored_path):
            continue

        resolved = os.path.realpath(record.stored_path)
        existing_by_path.pop(resolved, None)

        remaining_hash_refs = existing_hash_counts.get(record.file_hash, 0) - 1
        if remaining_hash_refs <= 0:
            existing_hash_counts.pop(record.file_hash, None)
        else:
            existing_hash_counts[record.file_hash] = remaining_hash_refs

        await db.delete(record)
        deleted_count += 1

    for root, _, files in os.walk(UPLOAD_DIR):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue

            stored_path = os.path.realpath(os.path.join(root, filename))
            if not _is_path_within(UPLOAD_DIR, stored_path):
                continue
            if stored_path in existing_by_path:
                continue

            # Keep manual rescan fast: avoid reading large files just to register them.
            # We derive a stable signature from relative path + file stat metadata.
            try:
                stat = os.stat(stored_path)
                relative_path = _to_relative_data_path(stored_path)
                signature = f"{relative_path}|{int(stat.st_size)}|{int(stat.st_mtime_ns)}"
                file_hash = hashlib.sha256(signature.encode("utf-8", errors="ignore")).hexdigest()
            except OSError:
                logger.exception("Failed to stat upload candidate %s", stored_path)
                continue

            if file_hash in existing_hash_counts:
                continue

            if ext == ".zip" and _ETN_ZIP_PATTERN.match(filename):
                source_type = "etn"
            elif ext == ".zip":
                source_type = "zip"
            elif ext == ".gpkg":
                source_type = "gpkg"
            else:
                source_type = "csv"
            row_count = None
            columns_json = None

            record = DatasetFile(
                original_name=filename,
                stored_path=stored_path,
                source_type=source_type,
                row_count=row_count,
                columns_json=columns_json,
                file_hash=file_hash,
                uploaded_by=None,
            )
            db.add(record)
            existing_hash_counts[file_hash] = 1
            existing_by_path[stored_path] = record
            indexed_count += 1

    if indexed_count > 0 or deleted_count > 0:
        await db.commit()

    return indexed_count, deleted_count


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
                    shape_preview = inspect_shapefile_zip_with_cache(stored_path, UPLOAD_DIR, preview_rows=20)
                    record = DatasetFile(
                        original_name=file.filename or "unknown",
                        stored_path=stored_path,
                        source_type="shape-zip",
                        row_count=None,
                        columns_json=json.dumps(shape_preview.get("layers", [])),
                        file_hash=file_hash,
                        uploaded_by=user.id,
                    )
                    db.add(record)
                    await db.flush()
                    await db.refresh(record)
                    uploaded.append(record)
                    continue
            except OSError as exc:
                _remove_file_if_exists(stored_path)
                raise HTTPException(
                    status.HTTP_507_INSUFFICIENT_STORAGE,
                    f"Not enough disk space to extract ZIP safely: {exc}",
                ) from exc
            except ValueError:
                _remove_file_if_exists(stored_path)
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "ZIP contains no supported CSV, GeoPackage, or shapefile attribute data to preview.",
                ) from None
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
    sync: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    import math

    if sync:
        indexed, deleted = await _sync_upload_directory_records(db)
        if indexed or deleted:
            logger.info("Dataset registry sync finished: indexed=%d deleted_stale=%d", indexed, deleted)

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


@router.post("/datasets/rescan", response_model=DatasetRescanResponse)
async def rescan_datasets(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    indexed, deleted = await _sync_upload_directory_records(db)
    message = f"Dataset registry sync finished: indexed={indexed}, deleted_stale={deleted}"
    return DatasetRescanResponse(indexed=indexed, deleted_stale=deleted, message=message)


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

    if dataset.source_type == "shape-zip":
        try:
            preview = inspect_shapefile_zip_with_cache(dataset.stored_path, UPLOAD_DIR, preview_rows=limit)
            return DatasetPreviewResponse(
                columns=preview.get("columns", []),
                rows=preview.get("rows", []),
                total_rows=int(preview.get("total_rows", 0)),
            )
        except ValueError:
            logger.exception("Cannot preview shapefile ZIP %s", dataset.stored_path)
            raise HTTPException(
                status_code=422, detail="ZIP does not contain any previewable shapefile attribute tables"
            ) from None
        except OSError:
            logger.exception("Cannot read shapefile ZIP %s for preview", dataset.stored_path)
            raise HTTPException(status_code=500, detail="Cannot read the shapefile ZIP") from None

    if dataset.source_type in ("zip", "etn") or dataset.stored_path.lower().endswith(".zip"):
        try:
            preview = _peek_zip_for_csv_preview(dataset.stored_path, limit)
            return DatasetPreviewResponse(
                columns=preview["columns"],
                rows=preview["rows"],
                total_rows=dataset.row_count or preview["total_rows"],
            )
        except (OSError, zipfile.BadZipFile, ValueError):
            logger.exception("Cannot peek ZIP %s for preview", dataset.stored_path)
            raise HTTPException(status_code=500, detail="Cannot read the dataset file") from None

    try:
        df = read_csv_flexible(dataset.stored_path, nrows=limit)
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


def _coerce_progress(value: object, fallback: int = 0) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return fallback


async def _read_prepare_job_state(redis, job_id: str) -> dict | None:
    raw = await redis.get(f"{PREPARE_JOB_PREFIX}{job_id}")
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid Redis prepare payload for job %s", job_id)
        return None


def _serialize_prepare_job(job_id: str, payload: dict | None) -> PrepareJobStatusResponse:
    data = payload or {}
    result = data.get("result")
    if isinstance(result, dict) and result.get("output_csv_path"):
        result = {
            **result,
            "output_csv_path": _to_relative_data_path(str(result["output_csv_path"])),
        }
        if result.get("status") == "completed" or data.get("status") == "completed":
            result["training_dataset"] = _get_training_dataset_metadata().model_dump(mode="json")
    return PrepareJobStatusResponse(
        job_id=job_id,
        status=str(data.get("status") or "unknown"),
        stage=data.get("stage"),
        progress=_coerce_progress(data.get("progress")),
        total_pairs=data.get("total_pairs"),
        current_pair_index=data.get("current_pair_index"),
        current_label=data.get("current_label"),
        pairs_completed=data.get("pairs_completed"),
        rows=data.get("rows"),
        result=result,
        error=data.get("error"),
    )


async def _get_active_prepare_job(redis) -> tuple[str | None, dict | None]:
    active_job_id = await redis.get(PREPARE_ACTIVE_KEY)
    if isinstance(active_job_id, bytes):
        active_job_id = active_job_id.decode("utf-8", errors="ignore")
    if not active_job_id:
        return None, None

    state = await _read_prepare_job_state(redis, str(active_job_id))
    if state is None:
        await redis.delete(PREPARE_ACTIVE_KEY)
        return None, None

    status_value = str(state.get("status") or "unknown")
    if status_value in {"completed", "failed"}:
        await redis.delete(PREPARE_ACTIVE_KEY)
        return None, None

    return str(active_job_id), state


async def _get_prepare_enqueue_redis(request: Request):
    shared_redis = request.app.state.redis
    if hasattr(shared_redis, "enqueued_jobs"):
        return shared_redis, False

    redis = await create_pool(_parse_redis_url(get_settings().redis_url))
    return redis, True


class EtnPrepareRequest(BaseModel):
    posli_csv_path: str
    delistavb_csv_path: str
    enrichment_options: dict | None = None


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
        result = prepare_training_csv_from_etn_kpp(posli, delistavb, TRAIN_CSV, req.enrichment_options)
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
    enrichment_options: dict | None = None


@router.post("/prepare-etn-kpp-bulk/start", response_model=PrepareJobStatusResponse)
async def start_prepare_etn_kpp_bulk(
    req: EtnBulkRequest,
    request: Request,
    _user: User = Depends(require_admin),
):
    """Start an async ETN bulk preparation job."""
    pairs_dicts = []
    for pair in req.pairs:
        resolved_pair = pair.model_dump()
        resolved_pair["posli_csv_path"] = _validate_path_within_data_dir(pair.posli_csv_path)
        resolved_pair["delistavb_csv_path"] = _validate_path_within_data_dir(pair.delistavb_csv_path)
        if pair.zemljisca_csv_path:
            resolved_pair["zemljisca_csv_path"] = _validate_path_within_data_dir(pair.zemljisca_csv_path)
        pairs_dicts.append(resolved_pair)

    redis, should_close = await _get_prepare_enqueue_redis(request)
    try:
        active_job_id, active_state = await _get_active_prepare_job(redis)
        if active_job_id and active_state:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "message": "A preparation job is already queued or running",
                    **_serialize_prepare_job(active_job_id, active_state).model_dump(),
                },
            )

        job_id = uuid.uuid4().hex[:16]
        initial_payload = {
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "total_pairs": len(pairs_dicts),
            "pairs_completed": 0,
        }
        await redis.set(f"{PREPARE_JOB_PREFIX}{job_id}", json.dumps(initial_payload), ex=86400)
        await redis.set(PREPARE_ACTIVE_KEY, job_id, ex=86400)
        enqueued_job = await redis.enqueue_job(
            "run_prepare_etn_bulk", job_id, pairs_dicts, TRAIN_CSV, req.enrichment_options
        )
        if should_close and enqueued_job is None:
            logger.error("Failed to enqueue prepare job %s", job_id)
            await redis.delete(PREPARE_ACTIVE_KEY)
            await redis.delete(f"{PREPARE_JOB_PREFIX}{job_id}")
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Preparation worker queue is unavailable")
        logger.info("Queued prepare job %s for %d pairs", job_id, len(pairs_dicts))
        return _serialize_prepare_job(job_id, initial_payload)
    finally:
        if should_close:
            await redis.close()


@router.get("/prepare-etn-kpp-bulk/active", response_model=PrepareJobStatusResponse)
async def get_active_prepare_etn_kpp_bulk(
    request: Request,
    _user: User = Depends(get_current_user),
):
    """Return the currently active ETN bulk preparation job, if any."""
    job_id, state = await _get_active_prepare_job(request.app.state.redis)
    if not job_id or not state:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active preparation job")
    return _serialize_prepare_job(job_id, state)


@router.get("/prepare-etn-kpp-bulk/status/{job_id}", response_model=PrepareJobStatusResponse)
async def get_prepare_etn_kpp_bulk_status(
    job_id: str,
    request: Request,
    _user: User = Depends(get_current_user),
):
    """Return ETN bulk preparation status from Redis."""
    state = await _read_prepare_job_state(request.app.state.redis, job_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preparation job not found")

    if str(state.get("status") or "") == "completed":
        await invalidate_request_caches(request)

    return _serialize_prepare_job(job_id, state)


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
        result = prepare_training_csv_from_etn_kpp_bulk(
            pairs_dicts, TRAIN_CSV, enrichment_options=req.enrichment_options
        )
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
