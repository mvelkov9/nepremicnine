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
import threading
import uuid
import zipfile
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal

import pandas as pd
from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import require_admin
from app.models.dataset import DatasetFile
from app.models.prepare_run import PrepareRun
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.dataset import (
    DatasetFileResponse,
    DatasetPreviewResponse,
    DatasetRescanResponse,
    DatasetUploadResponse,
    EtnKppDatasetRefResponse,
    EtnKppPairResponse,
    EtnKppPairsResponse,
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
from app.utils.cache import cache_get, cache_set, invalidate_request_caches
from app.utils.municipality import normalize_municipality_name
from app.utils.slovenian_labels import format_municipality_label, is_unknown_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])

# ETN files follow the pattern ETN_SLO_YYYY_{KPP|NP}_<date>.zip
_ETN_ZIP_PATTERN = re.compile(r"^ETN_SLO_\d{4}_(KPP|NP)_", re.IGNORECASE)
_ETN_KPP_YEAR_PATTERN = re.compile(r"ETN(?:_SLO)?_(20\d{2})_KPP(?:_|\.|$)", re.IGNORECASE)
_ETN_KPP_BUNDLE_PATTERN = re.compile(r"ETN(?:_SLO)?_(20\d{2})_KPP\.ZIP$", re.IGNORECASE)

DATA_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_SIZE = get_settings().max_upload_size_mb * 1024 * 1024
ALLOWED_EXTENSIONS = {".csv", ".zip", ".gpkg"}
UPLOAD_STREAM_CHUNK_SIZE = 8 * 1024 * 1024

_CACHE_LOCK = threading.Lock()
_TRAINING_DATASET_CACHE: dict[str, object | None] = {"signature": None, "value": None}
_QUALITY_SUMMARY_CACHE: dict[str, object | None] = {"signature": None, "value": None}
_CANONICAL_MUNICIPALITY_KEYS = {normalize_municipality_name(str(row["obcina_naziv"])) for row in CANONICAL_REGION_ROWS}
_TRAINING_DATASET_CACHE_VERSION = 1
_QUALITY_SUMMARY_CACHE_VERSION = 3


def _upload_disk_reserve_bytes() -> int:
    settings = get_settings()
    if settings.app_env == "test":
        return 0
    return max(0, int(settings.upload_disk_reserve_mb)) * 1024 * 1024


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


def _parse_etn_kpp_role(item: DatasetFile) -> tuple[str, int | None]:
    candidates = [item.original_name or "", _to_relative_data_path(item.stored_path)]

    for candidate in candidates:
        text = str(candidate).upper()
        year_match = _ETN_KPP_YEAR_PATTERN.search(text)
        if not year_match:
            continue

        year = int(year_match.group(1))
        if re.search(r"_KPP_POSLI(?:_|\.|$)", text):
            return "posli", year

        if re.search(r"_KPP_DELISTAVB(?:_|\.|$)", text):
            return "delistavb", year

        if re.search(r"_KPP_ZEMLJISCA(?:_|\.|$)", text) or re.search(r"_KPP_ZEMLJISC(?:_|\.|$)", text):
            return "zemljisca", year

        # A KPP yearly bundle ZIP can stand in for all role-specific inputs.
        if _ETN_KPP_BUNDLE_PATTERN.search(text):
            return "bundle", year

    return "other", None


def _serialize_etn_kpp_dataset_ref(item: DatasetFile | None) -> EtnKppDatasetRefResponse | None:
    if item is None:
        return None
    return EtnKppDatasetRefResponse(
        original_name=item.original_name,
        relative_path=_to_relative_data_path(item.stored_path),
        uploaded_at=item.uploaded_at,
    )


def _get_upload_capacity() -> UploadCapacityResponse:
    free_disk_bytes = get_available_disk_bytes(UPLOAD_DIR)
    reserve_disk_bytes = _upload_disk_reserve_bytes()
    return UploadCapacityResponse(
        max_upload_size_mb=get_settings().max_upload_size_mb,
        max_upload_size_bytes=MAX_UPLOAD_SIZE,
        free_disk_bytes=free_disk_bytes,
        reserve_disk_bytes=reserve_disk_bytes,
        recommended_max_upload_bytes=max(0, free_disk_bytes - reserve_disk_bytes),
    )


def _remove_file_if_exists(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)


def _training_file_signature(csv_path: str) -> tuple[int, int]:
    stat = os.stat(csv_path)
    return int(stat.st_mtime_ns), int(stat.st_size)


def _read_csv_header_columns(csv_path: str) -> list[str]:
    with contextlib.suppress(Exception):
        return pd.read_csv(csv_path, nrows=0, low_memory=False).columns.tolist()
    with contextlib.suppress(Exception):
        return read_csv_flexible(csv_path, nrows=0).columns.tolist()
    return []


def _count_csv_rows_fast(csv_path: str) -> int | None:
    newline_count = 0
    last_byte = b""
    try:
        with open(csv_path, "rb") as f:
            for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                newline_count += chunk.count(b"\n")
                last_byte = chunk[-1:]
    except OSError:
        return None

    if newline_count == 0:
        return 0
    if last_byte == b"\n":
        return max(newline_count - 1, 0)
    return newline_count


def _quality_summary_cache_path(csv_path: str) -> str:
    return f"{csv_path}.quality-summary.json"


def _load_quality_summary_from_disk(csv_path: str, signature: tuple[object, ...]) -> dict | None:
    cache_path = _quality_summary_cache_path(csv_path)
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("signature") == list(signature) and isinstance(payload.get("summary"), dict):
            return payload["summary"]
    except Exception:
        logger.warning("Ignoring invalid quality summary cache %s", cache_path, exc_info=True)
    return None


def _store_quality_summary_to_disk(csv_path: str, signature: tuple[object, ...], summary: dict) -> None:
    cache_path = _quality_summary_cache_path(csv_path)
    payload = {
        "signature": list(signature),
        "summary": summary,
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)


def _pre_extract_zips_in_dir(upload_dir: str) -> None:
    """Extract each ZIP in upload_dir into a same-named subdirectory (idempotent).

    Skips subdirs that already contain at least one file.  Flattens internal
    directory structure — only the file basenames are used.
    """
    try:
        entries = sorted(os.listdir(upload_dir))
    except OSError:
        return

    for filename in entries:
        if not filename.lower().endswith(".zip"):
            continue
        zip_path = os.path.join(upload_dir, filename)
        if not os.path.isfile(zip_path):
            continue

        subdir_name = os.path.splitext(filename)[0]
        subdir = os.path.join(upload_dir, subdir_name)

        # Idempotency: skip if subdir already has files
        if os.path.isdir(subdir) and any(os.path.isfile(os.path.join(subdir, f)) for f in os.listdir(subdir)):
            continue

        try:
            os.makedirs(subdir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    basename = os.path.basename(member.filename)
                    if not basename or basename.endswith(".preview.json"):
                        continue
                    dest = os.path.join(subdir, basename)
                    if not os.path.exists(dest):
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
            logger.info("Pre-extracted ZIP %s to %s/", filename, subdir_name)
        except Exception:
            logger.warning("Failed to pre-extract %s", filename, exc_info=True)


def _peek_zip_for_csv_preview(zip_path: str, limit: int) -> dict:
    """Open a ZIP and preview the first CSV found inside it."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_members = sorted(m for m in zf.namelist() if m.lower().endswith(".csv") and not m.startswith("__MACOSX"))
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


def _resolve_managed_dataset_path(raw_path: str) -> str:
    resolved = os.path.realpath(raw_path)
    if not _is_path_within(UPLOAD_DIR, resolved):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Dataset file is outside the managed upload directory",
        )
    return resolved


def _remove_managed_dataset_file(raw_path: str) -> None:
    try:
        resolved = _resolve_managed_dataset_path(raw_path)
    except HTTPException:
        logger.warning("Skipping deletion for unmanaged dataset path %s", raw_path)
        return
    _remove_file_if_exists(resolved)


async def _sync_upload_directory_records(db: AsyncSession) -> tuple[int, int]:
    """Index manually added upload files so they appear in the dataset library."""
    # Pre-extract ZIPs so their contents appear as individual files in the listing.
    _pre_extract_zips_in_dir(UPLOAD_DIR)

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
        resolved = os.path.realpath(record.stored_path)
        if not _is_path_within(UPLOAD_DIR, resolved):
            logger.warning("Dropping unmanaged dataset record %s -> %s", record.id, record.stored_path)
        elif os.path.exists(resolved):
            continue

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
    file_exists = os.path.exists(TRAIN_CSV)
    relative_path = _to_relative_data_path(TRAIN_CSV)
    if not file_exists:
        signature = ("missing", _TRAINING_DATASET_CACHE_VERSION)
        with _CACHE_LOCK:
            if _TRAINING_DATASET_CACHE["signature"] == signature and _TRAINING_DATASET_CACHE["value"] is not None:
                return _TRAINING_DATASET_CACHE["value"]
        response = TrainingDatasetResponse(exists=False, relative_path=relative_path)
        with _CACHE_LOCK:
            _TRAINING_DATASET_CACHE["signature"] = signature
            _TRAINING_DATASET_CACHE["value"] = response
        return response

    signature = ("present", _TRAINING_DATASET_CACHE_VERSION) + _training_file_signature(TRAIN_CSV)
    with _CACHE_LOCK:
        if _TRAINING_DATASET_CACHE["signature"] == signature and _TRAINING_DATASET_CACHE["value"] is not None:
            return _TRAINING_DATASET_CACHE["value"]

    preparation_metadata = load_training_metadata(TRAIN_CSV)
    rows = None
    columns: list[str] = []

    if isinstance(preparation_metadata, dict):
        with contextlib.suppress(Exception):
            rows = int(preparation_metadata.get("rows"))
        metadata_columns = preparation_metadata.get("columns")
        if isinstance(metadata_columns, list):
            columns = [str(column) for column in metadata_columns]

    if not columns:
        columns = _read_csv_header_columns(TRAIN_CSV)

    if rows is None:
        rows = _count_csv_rows_fast(TRAIN_CSV)

    response = TrainingDatasetResponse(
        exists=True,
        relative_path=relative_path,
        rows=rows,
        columns=columns,
        updated_at=datetime.fromtimestamp(os.path.getmtime(TRAIN_CSV), UTC),
        size_bytes=os.path.getsize(TRAIN_CSV),
        preparation_metadata=preparation_metadata,
    )
    with _CACHE_LOCK:
        _TRAINING_DATASET_CACHE["signature"] = signature
        _TRAINING_DATASET_CACHE["value"] = response
    return response


def _validate_path_within_data_dir(raw_path: str) -> str:
    """Resolve a path and ensure it stays within DATA_DIR. Raises 400 on traversal or symlink."""
    resolved = _resolve_data_path(raw_path)
    if not resolved.startswith(DATA_DIR + os.sep) and resolved != DATA_DIR:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Path is outside the allowed data directory")
    raw_candidate = raw_path if os.path.isabs(raw_path) else os.path.join(DATA_DIR, raw_path)
    if os.path.islink(raw_candidate):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Symbolic links are not allowed")
    return resolved


def _require_non_blank_path(raw_path: str, field_name: str) -> str:
    cleaned = raw_path.strip()
    if not cleaned:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{field_name} is required")
    return cleaned


def _build_quality_summary() -> dict:
    reference_total = len(CANONICAL_REGION_ROWS)
    if not os.path.exists(TRAIN_CSV):
        signature = ("missing", _QUALITY_SUMMARY_CACHE_VERSION)
        with _CACHE_LOCK:
            if _QUALITY_SUMMARY_CACHE["signature"] == signature and _QUALITY_SUMMARY_CACHE["value"] is not None:
                return _QUALITY_SUMMARY_CACHE["value"]
        response = {
            "training_dataset_exists": False,
            "canonical_reference_total": reference_total,
            "covered_municipalities": 0,
            "unresolved_rows": 0,
            "unresolved_labels": [],
            "noncanonical_rows": 0,
            "noncanonical_labels": [],
            "alias_collisions": [],
        }
        with _CACHE_LOCK:
            _QUALITY_SUMMARY_CACHE["signature"] = signature
            _QUALITY_SUMMARY_CACHE["value"] = response
        return response

    signature = ("present", _QUALITY_SUMMARY_CACHE_VERSION) + _training_file_signature(TRAIN_CSV)
    with _CACHE_LOCK:
        if _QUALITY_SUMMARY_CACHE["signature"] == signature and _QUALITY_SUMMARY_CACHE["value"] is not None:
            return _QUALITY_SUMMARY_CACHE["value"]

    disk_cached_summary = _load_quality_summary_from_disk(TRAIN_CSV, signature)
    if disk_cached_summary is not None:
        with _CACHE_LOCK:
            _QUALITY_SUMMARY_CACHE["signature"] = signature
            _QUALITY_SUMMARY_CACHE["value"] = disk_cached_summary
        return disk_cached_summary

    try:
        municipality_df = pd.read_csv(
            TRAIN_CSV,
            usecols=["municipality"],
            low_memory=False,
            dtype={"municipality": "string"},
        )
    except Exception:
        municipality_df = read_csv_flexible(
            TRAIN_CSV,
            usecols=["municipality"],
            dtype={"municipality": "string"},
        )

    if "municipality" not in municipality_df.columns:
        response = {
            "training_dataset_exists": True,
            "canonical_reference_total": reference_total,
            "covered_municipalities": 0,
            "unresolved_rows": 0,
            "unresolved_labels": [],
            "noncanonical_rows": 0,
            "noncanonical_labels": [],
            "alias_collisions": [],
        }
        with _CACHE_LOCK:
            _QUALITY_SUMMARY_CACHE["signature"] = signature
            _QUALITY_SUMMARY_CACHE["value"] = response
        return response

    raw_values = municipality_df["municipality"].fillna("").astype(str)
    canonical_labels = raw_values.map(format_municipality_label)
    normalized = canonical_labels.map(normalize_municipality_name)
    known_mask = canonical_labels.map(lambda value: value is not None and not is_unknown_label(value))
    canonical_mask = known_mask & normalized.isin(_CANONICAL_MUNICIPALITY_KEYS)
    noncanonical_mask = known_mask & ~normalized.isin(_CANONICAL_MUNICIPALITY_KEYS)

    unresolved_labels = Counter(raw_values[~canonical_mask])
    noncanonical_labels = Counter(str(label) for label in canonical_labels[noncanonical_mask] if label)
    collision_map: dict[str, set[str]] = {}
    for raw, canonical, is_canonical in zip(raw_values, canonical_labels, canonical_mask, strict=False):
        if canonical is None or not is_canonical:
            continue
        collision_map.setdefault(str(canonical), set()).add(str(raw).strip())

    alias_collisions = [
        {"canonical": canonical, "variants": sorted(variants), "variant_count": len(variants)}
        for canonical, variants in collision_map.items()
        if len(variants) > 1
    ]
    alias_collisions.sort(key=lambda item: item["variant_count"], reverse=True)

    covered = int(normalized[canonical_mask].nunique())
    response = {
        "training_dataset_exists": True,
        "canonical_reference_total": reference_total,
        "covered_municipalities": covered,
        "coverage_ratio": round(covered / max(reference_total, 1), 4),
        "unresolved_rows": int((~canonical_mask).sum()),
        "unresolved_labels": [
            {"label": label or "unknown", "count": int(count)} for label, count in unresolved_labels.most_common(12)
        ],
        "noncanonical_rows": int(noncanonical_mask.sum()),
        "noncanonical_labels": [
            {"label": label, "count": int(count)} for label, count in noncanonical_labels.most_common(12)
        ],
        "alias_collisions": alias_collisions[:12],
    }
    with _CACHE_LOCK:
        _QUALITY_SUMMARY_CACHE["signature"] = signature
        _QUALITY_SUMMARY_CACHE["value"] = response
    with contextlib.suppress(Exception):
        _store_quality_summary_to_disk(TRAIN_CSV, signature, response)
    return response


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
    reserve_disk_bytes = _upload_disk_reserve_bytes()

    for file in files:
        ext = os.path.splitext(file.filename or "file.csv")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"File type '{ext}' not allowed. Only .csv, .zip, and .gpkg accepted.",
            )

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        try:
            ensure_directory_headroom(UPLOAD_DIR, int(content_length), reserve_disk_bytes)
        except OSError as exc:
            raise HTTPException(
                status.HTTP_507_INSUFFICIENT_STORAGE,
                f"Not enough disk space to receive upload safely: {exc}",
            ) from exc

    for file in files:
        ext = os.path.splitext(file.filename or "file.csv")[1].lower()

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
            ensure_directory_headroom(UPLOAD_DIR, 0, reserve_disk_bytes)
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
                ensure_directory_headroom(UPLOAD_DIR, estimated_uncompressed, reserve_disk_bytes)
                csv_paths, gpkg_paths = extract_zip_supported_files(
                    stored_path,
                    UPLOAD_DIR,
                    reserve_bytes=reserve_disk_bytes,
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
    result = DatasetUploadResponse(
        uploaded=[_serialize_dataset(r) for r in uploaded],
        skipped=skipped,
        message=msg,
    )
    await invalidate_request_caches(request, prefixes=("cache:data:", "cache:admin:"))
    return result


@router.get("/datasets")
async def list_datasets(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sync: bool = Query(False),
    search: str | None = Query(None),
    sort: str = Query("uploaded_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    import math

    if sync:
        indexed, deleted = await _sync_upload_directory_records(db)
        if indexed or deleted:
            logger.info("Dataset registry sync finished: indexed=%d deleted_stale=%d", indexed, deleted)

    offset = (page - 1) * per_page
    stmt = select(DatasetFile, func.count(DatasetFile.id).over().label("total_count"))

    normalized_search = (search or "").strip()
    if normalized_search:
        pattern = f"%{normalized_search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(func.coalesce(DatasetFile.original_name, "")).like(pattern),
                func.lower(func.coalesce(DatasetFile.source_type, "")).like(pattern),
                func.lower(func.coalesce(DatasetFile.stored_path, "")).like(pattern),
            )
        )

    sort_columns = {
        "id": DatasetFile.id,
        "original_name": DatasetFile.original_name,
        "relative_path": DatasetFile.stored_path,
        "source_type": DatasetFile.source_type,
        "row_count": DatasetFile.row_count,
        "uploaded_at": DatasetFile.uploaded_at,
    }
    sort_column = sort_columns.get(sort, DatasetFile.uploaded_at)
    stmt = stmt.order_by(sort_column.asc() if order == "asc" else sort_column.desc())
    stmt = stmt.offset(offset).limit(per_page)
    rows = (await db.execute(stmt)).all()
    total = rows[0].total_count if rows else 0
    pages = math.ceil(total / per_page) if total > 0 else 0

    items = [_serialize_dataset(r.DatasetFile) for r in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "page_size": per_page,
        "pages": pages,
        "filters": {
            "search": normalized_search or None,
        },
        "sort": sort if sort in sort_columns else "uploaded_at",
        "order": order,
    }


@router.get("/prepare-etn-kpp-pairs", response_model=EtnKppPairsResponse)
async def list_prepare_etn_kpp_pairs(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Return deduplicated ETN KPP year pairs for fast bulk-prepare selection."""
    response.headers["Cache-Control"] = "private, max-age=300"
    cache_key = "cache:data:prepare-etn-kpp-pairs"
    cached = await cache_get(request, cache_key)
    if cached is not None:
        return EtnKppPairsResponse(**cached)

    await _sync_upload_directory_records(db)
    rows = (
        (
            await db.execute(
                select(DatasetFile).where(DatasetFile.original_name.ilike("%ETN%KPP%")).order_by(DatasetFile.id.desc())
            )
        )
        .scalars()
        .all()
    )

    by_year: dict[int, dict[str, DatasetFile | None]] = {}
    for item in rows:
        role, year = _parse_etn_kpp_role(item)
        if year is None:
            continue

        if year not in by_year:
            by_year[year] = {
                "posli": None,
                "delistavb": None,
                "zemljisca": None,
            }

        year_row = by_year[year]
        if role == "bundle":
            if year_row["posli"] is None:
                year_row["posli"] = item
            if year_row["delistavb"] is None:
                year_row["delistavb"] = item
            if year_row["zemljisca"] is None:
                year_row["zemljisca"] = item
            continue

        if role in ("posli", "delistavb", "zemljisca") and year_row[role] is None:
            year_row[role] = item

    pairs = [
        EtnKppPairResponse(
            year=year,
            posli=_serialize_etn_kpp_dataset_ref(values["posli"]),
            delistavb=_serialize_etn_kpp_dataset_ref(values["delistavb"]),
            zemljisca=_serialize_etn_kpp_dataset_ref(values["zemljisca"]),
        )
        for year, values in sorted(by_year.items(), key=lambda item: item[0])
        if values["posli"] is not None and values["delistavb"] is not None
    ]
    result = EtnKppPairsResponse(pairs=pairs)
    await cache_set(request, cache_key, result.model_dump(mode="json"))
    return result


@router.post("/datasets/rescan", response_model=DatasetRescanResponse)
async def rescan_datasets(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    indexed, deleted = await _sync_upload_directory_records(db)
    message = f"Dataset registry sync finished: indexed={indexed}, deleted_stale={deleted}"
    await invalidate_request_caches(request, prefixes=("cache:data:", "cache:admin:"))
    return DatasetRescanResponse(indexed=indexed, deleted_stale=deleted, message=message)


@router.get("/training-dataset", response_model=TrainingDatasetResponse)
async def training_dataset(_user: User = Depends(require_admin)):
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
    _user: User = Depends(require_admin),
):
    result = await db.execute(select(DatasetFile).where(DatasetFile.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    stored_path = _resolve_managed_dataset_path(dataset.stored_path)

    if not os.path.exists(stored_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    if dataset.source_type == "gpkg" or stored_path.lower().endswith(".gpkg"):
        try:
            preview = inspect_gpkg(stored_path, preview_rows=limit)
            return DatasetPreviewResponse(
                columns=preview.get("columns", []),
                rows=preview.get("rows", []),
                total_rows=int(preview.get("total_rows", 0)),
            )
        except (sqlite3.DatabaseError, OSError, ValueError):
            logger.exception("Cannot read GeoPackage file %s for preview", stored_path)
            raise HTTPException(status_code=500, detail="Cannot read the GeoPackage file") from None

    if dataset.source_type == "shape-zip":
        try:
            preview = inspect_shapefile_zip_with_cache(stored_path, UPLOAD_DIR, preview_rows=limit)
            return DatasetPreviewResponse(
                columns=preview.get("columns", []),
                rows=preview.get("rows", []),
                total_rows=int(preview.get("total_rows", 0)),
            )
        except ValueError:
            logger.exception("Cannot preview shapefile ZIP %s", stored_path)
            raise HTTPException(
                status_code=422, detail="ZIP does not contain any previewable shapefile attribute tables"
            ) from None
        except OSError:
            logger.exception("Cannot read shapefile ZIP %s for preview", stored_path)
            raise HTTPException(status_code=500, detail="Cannot read the shapefile ZIP") from None

    if dataset.source_type in ("zip", "etn") or stored_path.lower().endswith(".zip"):
        try:
            preview = _peek_zip_for_csv_preview(stored_path, limit)
            return DatasetPreviewResponse(
                columns=preview["columns"],
                rows=preview["rows"],
                total_rows=dataset.row_count or preview["total_rows"],
            )
        except (OSError, zipfile.BadZipFile, ValueError):
            logger.exception("Cannot peek ZIP %s for preview", stored_path)
            raise HTTPException(status_code=500, detail="Cannot read the dataset file") from None

    try:
        df = read_csv_flexible(stored_path, nrows=limit)
        return DatasetPreviewResponse(
            columns=list(df.columns),
            rows=df.fillna("").to_dict(orient="records"),
            total_rows=dataset.row_count or len(df),
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError, OSError):
        logger.exception("Cannot read dataset file %s for preview", stored_path)
        raise HTTPException(status_code=500, detail="Cannot read the dataset file") from None


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    request: Request,
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    result = await db.execute(select(DatasetFile).where(DatasetFile.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    _remove_managed_dataset_file(dataset.stored_path)

    await db.delete(dataset)
    await db.commit()
    await invalidate_request_caches(request, prefixes=("cache:data:", "cache:admin:"))


class BulkDeleteRequest(BaseModel):
    dataset_ids: list[int] = Field(..., max_length=500)


@router.post("/datasets/delete-bulk", status_code=status.HTTP_200_OK)
async def delete_datasets_bulk(
    request: Request,
    req: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Delete multiple datasets at once."""
    rows = (await db.execute(select(DatasetFile).where(DatasetFile.id.in_(req.dataset_ids)))).scalars().all()

    deleted = 0
    for dataset in rows:
        _remove_managed_dataset_file(dataset.stored_path)
        await db.delete(dataset)
        deleted += 1
    await db.commit()
    await invalidate_request_caches(request, prefixes=("cache:data:", "cache:admin:"))
    return {"deleted": deleted}


TRAIN_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw", "train.csv")


def _coerce_progress(value: object, fallback: int = 0) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return fallback


def _state_value(payload: dict | None, key: str, fallback: Any) -> Any:
    if not payload:
        return fallback
    value = payload.get(key)
    return fallback if value is None else value


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
        spatial_phase=data.get("spatial_phase"),
        result=result,
        error=data.get("error"),
    )


async def _sync_prepare_run(
    db: AsyncSession,
    *,
    job_id: str,
    payload: dict | None,
    created_by: int | None = None,
    source_pairs: list[dict] | None = None,
    enrichment_options: dict | None = None,
) -> PrepareRun:
    result = await db.execute(select(PrepareRun).where(PrepareRun.job_id == job_id))
    row = result.scalar_one_or_none()
    if row is None:
        row = PrepareRun(
            job_id=job_id,
            created_by=created_by,
            source_pairs_json=json.dumps(source_pairs or [], ensure_ascii=True) if source_pairs is not None else None,
            enrichment_options_json=json.dumps(enrichment_options or {}, ensure_ascii=True)
            if enrichment_options is not None
            else None,
        )
        db.add(row)

    data = payload or {}
    row.status = str(data.get("status") or row.status or "unknown")
    row.stage = _state_value(data, "stage", row.stage)
    row.progress = _coerce_progress(data.get("progress"), fallback=row.progress or 0)
    row.total_pairs = _state_value(data, "total_pairs", row.total_pairs)
    row.current_pair_index = _state_value(data, "current_pair_index", row.current_pair_index)
    row.current_label = _state_value(data, "current_label", row.current_label)
    row.pairs_completed = _state_value(data, "pairs_completed", row.pairs_completed)
    row.rows = _state_value(data, "rows", row.rows)
    row.spatial_phase = _state_value(data, "spatial_phase", row.spatial_phase)
    row.error = _state_value(data, "error", row.error)
    if data.get("result") is not None:
        row.result_json = json.dumps(data.get("result") or {}, ensure_ascii=True)
    await db.flush()
    return row


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
    shared_redis = getattr(request.app.state, "redis", None)
    if shared_redis is not None and hasattr(shared_redis, "enqueue_job"):
        return shared_redis, False

    redis = await create_pool(_parse_redis_url(get_settings().redis_url))
    return redis, True


class EtnPrepareRequest(BaseModel):
    posli_csv_path: str = Field(min_length=1, max_length=1000)
    delistavb_csv_path: str = Field(min_length=1, max_length=1000)
    enrichment_options: dict | None = None


@router.post("/prepare-etn-kpp")
async def prepare_etn_kpp(
    req: EtnPrepareRequest,
    request: Request,
    _user: User = Depends(require_admin),
):
    """Prepare training CSV from a single ETN KPP posli+delistavb pair."""
    posli = _validate_path_within_data_dir(_require_non_blank_path(req.posli_csv_path, "posli_csv_path"))
    delistavb = _validate_path_within_data_dir(_require_non_blank_path(req.delistavb_csv_path, "delistavb_csv_path"))
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
    posli_csv_path: str = Field(min_length=1, max_length=1000)
    delistavb_csv_path: str = Field(min_length=1, max_length=1000)
    zemljisca_csv_path: str | None = None
    label: str | None = None
    year: str | None = None


class EtnBulkRequest(BaseModel):
    pairs: list[EtnBulkPair] = Field(..., min_length=1, max_length=50)
    enrichment_options: dict | None = None


@router.post("/prepare-etn-kpp-bulk/start", response_model=PrepareJobStatusResponse)
async def start_prepare_etn_kpp_bulk(
    req: EtnBulkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Start an async ETN bulk preparation job."""
    pairs_dicts = []
    for pair in req.pairs:
        resolved_pair = pair.model_dump()
        resolved_pair["posli_csv_path"] = _validate_path_within_data_dir(
            _require_non_blank_path(pair.posli_csv_path, "posli_csv_path")
        )
        resolved_pair["delistavb_csv_path"] = _validate_path_within_data_dir(
            _require_non_blank_path(pair.delistavb_csv_path, "delistavb_csv_path")
        )
        if pair.zemljisca_csv_path:
            resolved_pair["zemljisca_csv_path"] = _validate_path_within_data_dir(
                _require_non_blank_path(pair.zemljisca_csv_path, "zemljisca_csv_path")
            )
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
        await _sync_prepare_run(
            db,
            job_id=job_id,
            payload=initial_payload,
            created_by=user.id,
            source_pairs=pairs_dicts,
            enrichment_options=req.enrichment_options,
        )
        await redis.set(f"{PREPARE_JOB_PREFIX}{job_id}", json.dumps(initial_payload), ex=86400)
        await redis.set(PREPARE_ACTIVE_KEY, job_id, ex=86400)
        queue_error = "Preparation worker queue is unavailable"
        try:
            enqueued_job = await redis.enqueue_job(
                "run_prepare_etn_bulk", job_id, pairs_dicts, TRAIN_CSV, req.enrichment_options
            )
        except Exception:
            logger.exception("Failed to enqueue prepare job %s", job_id)
            await redis.delete(PREPARE_ACTIVE_KEY)
            await redis.delete(f"{PREPARE_JOB_PREFIX}{job_id}")
            await _sync_prepare_run(
                db,
                job_id=job_id,
                payload={
                    **initial_payload,
                    "status": "failed",
                    "stage": "error",
                    "error": queue_error,
                },
            )
            await db.commit()
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, queue_error) from None
        if enqueued_job is None:
            logger.error("Prepare queue returned no job handle for %s", job_id)
            await redis.delete(PREPARE_ACTIVE_KEY)
            await redis.delete(f"{PREPARE_JOB_PREFIX}{job_id}")
            await _sync_prepare_run(
                db,
                job_id=job_id,
                payload={
                    **initial_payload,
                    "status": "failed",
                    "stage": "error",
                    "error": queue_error,
                },
            )
            await db.commit()
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, queue_error)
        logger.info("Queued prepare job %s for %d pairs", job_id, len(pairs_dicts))
        await db.commit()
        return _serialize_prepare_job(job_id, initial_payload)
    finally:
        if should_close:
            await redis.close()


@router.get("/prepare-etn-kpp-bulk/active", response_model=PrepareJobStatusResponse)
async def get_active_prepare_etn_kpp_bulk(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Return the currently active ETN bulk preparation job, if any."""
    job_id, state = await _get_active_prepare_job(request.app.state.redis)
    if not job_id or not state:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active preparation job")
    await _sync_prepare_run(db, job_id=job_id, payload=state)
    await db.commit()
    return _serialize_prepare_job(job_id, state)


@router.get("/prepare-etn-kpp-bulk/status/{job_id}", response_model=PrepareJobStatusResponse)
async def get_prepare_etn_kpp_bulk_status(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """Return ETN bulk preparation status from Redis."""
    state = await _read_prepare_job_state(request.app.state.redis, job_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preparation job not found")

    await _sync_prepare_run(db, job_id=job_id, payload=state)
    await db.commit()

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
        resolved_pair["posli_csv_path"] = _validate_path_within_data_dir(
            _require_non_blank_path(pair.posli_csv_path, "posli_csv_path")
        )
        resolved_pair["delistavb_csv_path"] = _validate_path_within_data_dir(
            _require_non_blank_path(pair.delistavb_csv_path, "delistavb_csv_path")
        )
        if pair.zemljisca_csv_path:
            resolved_pair["zemljisca_csv_path"] = _validate_path_within_data_dir(
                _require_non_blank_path(pair.zemljisca_csv_path, "zemljisca_csv_path")
            )
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
    rn_csv_path: str = Field(min_length=1, max_length=1000)
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

    rn_path = _validate_path_within_data_dir(_require_non_blank_path(req.rn_csv_path, "rn_csv_path"))
    stat_path = (
        _validate_path_within_data_dir(_require_non_blank_path(req.stat_regije_csv_path, "stat_regije_csv_path"))
        if req.stat_regije_csv_path
        else None
    )
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
    _user: User = Depends(require_admin),
):
    """Inspect a dataset: columns, row count, preview rows."""
    result = await db.execute(select(DatasetFile).where(DatasetFile.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    stored_path = _resolve_managed_dataset_path(dataset.stored_path)
    if not os.path.exists(stored_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    try:
        return inspect_csv(stored_path)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError, UnicodeDecodeError, OSError):
        logger.exception("Cannot inspect dataset file %s", stored_path)
        raise HTTPException(status_code=500, detail="Cannot inspect the dataset file") from None


class PrepareTrainRequest(BaseModel):
    source_csv_path: str = Field(min_length=1, max_length=1000)
    column_map: dict[str, str]


@router.post("/prepare-train")
async def prepare_train(
    req: PrepareTrainRequest,
    request: Request,
    _user: User = Depends(require_admin),
):
    """Prepare training CSV from a source CSV with custom column mapping."""
    source = _validate_path_within_data_dir(_require_non_blank_path(req.source_csv_path, "source_csv_path"))
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
