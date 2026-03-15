# Phase 1: Backend Core

**Status:** 🔲 Not started

## Checklist

- [ ] SQLAlchemy ORM models (DatasetFile, ModelRun, PredictionLog, TrainingJob, RegionLookup, ListingsRun)
- [ ] Pydantic v2 schemas for all request/response
- [ ] Initial Alembic migration
- [ ] Auth system: register, login, refresh, me
- [ ] Auth dependency: get_current_user, require_admin
- [ ] Data endpoints: upload, list, delete, preview
- [ ] Reference endpoints: municipalities, regions, regions/stats
- [ ] Stats endpoints: overview, regions, price-distribution, trend
- [ ] pytest fixtures + tests for auth + data endpoints
- [ ] Swagger docs verification at /docs
