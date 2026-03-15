# Phase 1: Backend Core

**Status:** ✅ Complete  
**Commit:** `7b0a80c`

## Checklist

- [x] SQLAlchemy ORM models (User, DatasetFile, ModelRun, PredictionLog, TrainingJob, RegionLookup, ListingsRun)
- [x] Pydantic v2 schemas for all request/response payloads
- [x] Initial Alembic migration (`7948cdf948fa`) — 7 tables
- [x] Auth system: register, login, refresh, me (JWT access + refresh)
- [x] Auth dependencies: `get_current_user`, `require_admin`
- [x] First registered user auto-promoted to admin
- [x] Data endpoints: upload CSV, list datasets, delete, preview
- [x] Reference endpoints: municipalities, regions, regions/stats
- [x] Stats endpoints: overview, regions, price-distribution, trend
- [x] pytest fixtures + 14 tests (auth + data + regions)
- [x] Swagger/OpenAPI docs at `/docs`

## Key Files

| File | Purpose |
|------|---------|
| `app/models/user.py` | User model (UserRole StrEnum: admin/viewer) |
| `app/models/dataset.py` | DatasetFile (ETN CSV uploads, SHA-256 dedup) |
| `app/models/training_job.py` | TrainingJob (JobStatus StrEnum) |
| `app/models/model_run.py` | ModelRun (training metrics snapshot) |
| `app/models/prediction.py` | PredictionLog |
| `app/models/region.py` | RegionLookup (municipality + region mapping) |
| `app/models/listings_run.py` | ListingsRun |
| `app/schemas/auth.py` | Login/Register/Token/User schemas |
| `app/schemas/dataset.py` | Dataset request/response schemas |
| `app/schemas/stats.py` | Stats response schemas |
| `app/api/auth.py` | Auth routes (register, login, refresh, me) |
| `app/api/data.py` | Data routes (upload, list, delete, preview) |
| `app/api/regions.py` | Region/municipality routes |
| `app/api/stats.py` | Dashboard statistics routes |
| `app/dependencies/auth.py` | JWT verification + role enforcement |
| `app/services/auth_service.py` | Password hashing, JWT creation |
| `app/services/regions_service.py` | Municipality/region lookups (šumniki-safe) |
| `tests/test_auth.py` | Auth endpoint tests |
| `tests/test_data.py` | Data endpoint tests |

## Database Schema (7 tables)

```
users            dataset_files     training_jobs     model_runs
────────────     ────────────      ─────────────     ──────────
id (PK)          id (PK)           id (PK)           id (PK)
email            filename          status            property_type
hashed_password  file_hash         progress          r2_score
role             uploaded_by       total_records     mae
is_active        row_count         error_message     feature_importance
created_at       uploaded_at       started_at        trained_at
                 source_label      completed_at
                                   triggered_by

prediction_logs  region_lookups    listings_runs
──────────────   ──────────────    ─────────────
id (PK)          id (PK)           id (PK)
input_data       municipality      source
predicted_price  region            year
property_type    statistical_region records_count
model_version    postal_code       processed_at
predicted_at     display_name
user_id (FK)
```
