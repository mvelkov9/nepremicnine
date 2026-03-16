"""Training endpoint tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.train import DATA_DIR
from app.models.training_job import JobStatus, TrainingJob


class _FakeRedisPool:
    def __init__(self, payloads: dict[str, str] | None = None):
        self.payloads = payloads or {}
        self.enqueued: list[tuple[str, str, str]] = []

    async def get(self, key: str) -> str | None:
        return self.payloads.get(key)

    async def enqueue_job(self, func_name: str, job_id: str, csv_path: str) -> None:
        self.enqueued.append((func_name, job_id, csv_path))

    async def close(self) -> None:
        pass


# ── POST /api/train/start ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_train_start_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/train/start", json={"csv_path": "train.csv"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_train_start_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.post("/api/train/start", json={"csv_path": "train.csv"}, headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_train_start_csv_not_found(client: AsyncClient, admin_headers: dict):
    """Requesting a non-existent CSV returns 404."""
    resp = await client.post(
        "/api/train/start",
        json={"csv_path": "nonexistent.csv"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_train_start_path_traversal_rejected(client: AsyncClient, admin_headers: dict):
    """Absolute paths outside the data directory must be rejected."""
    resp = await client.post(
        "/api/train/start",
        json={"csv_path": "/etc/passwd"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_train_active_returns_current_job_status(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    job = TrainingJob(job_id="active-job", status=JobStatus.running, csv_path="/tmp/train.csv", progress=12)
    db_session.add(job)
    await db_session.commit()

    fake_redis = _FakeRedisPool(
        {
            "training_job:active-job": json.dumps(
                {"status": "running", "stage": "fitting", "progress": 48, "updated_at": 1}
            )
        }
    )

    async def fake_create_pool(*_args, **_kwargs):
        return fake_redis

    monkeypatch.setattr("app.api.train.create_pool", fake_create_pool)

    resp = await client.get("/api/train/active", headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["job_id"] == "active-job"
    assert resp.json()["stage"] == "fitting"
    assert resp.json()["progress"] == 48


@pytest.mark.asyncio
async def test_train_status_returns_redis_progress_without_crashing(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    job = TrainingJob(job_id="status-job", status=JobStatus.running, csv_path="/tmp/train.csv", progress=12)
    db_session.add(job)
    await db_session.commit()

    fake_redis = _FakeRedisPool(
        {
            "training_job:status-job": json.dumps(
                {"status": "running", "stage": "fitting", "progress": 64, "updated_at": 1}
            )
        }
    )

    async def fake_create_pool(*_args, **_kwargs):
        return fake_redis

    monkeypatch.setattr("app.api.train.create_pool", fake_create_pool)

    resp = await client.get("/api/train/status/status-job", headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert resp.json()["stage"] == "fitting"
    assert resp.json()["progress"] == 64


@pytest.mark.asyncio
async def test_train_start_conflict_returns_existing_job_context(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    train_csv = Path(DATA_DIR) / "raw" / "train.csv"
    train_csv.parent.mkdir(parents=True, exist_ok=True)
    train_csv.write_text("price_eur,size_m2\n100000,55\n", encoding="utf-8")

    job = TrainingJob(job_id="active-job", status=JobStatus.running, csv_path=str(train_csv), progress=12)
    db_session.add(job)
    await db_session.commit()

    fake_redis = _FakeRedisPool(
        {
            "training_job:active-job": json.dumps(
                {"status": "running", "stage": "fitting", "progress": 48, "updated_at": 1}
            )
        }
    )

    async def fake_create_pool(*_args, **_kwargs):
        return fake_redis

    monkeypatch.setattr("app.api.train.create_pool", fake_create_pool)

    resp = await client.post("/api/train/start", json={"csv_path": "raw/train.csv"}, headers=admin_headers)

    assert resp.status_code == 409
    data = resp.json()
    assert data["detail"] == "A training job is already queued or running"
    assert data["job_id"] == "active-job"
    assert data["progress"] == 48


@pytest.mark.asyncio
async def test_train_start_marks_stale_job_failed_and_enqueues_new_job(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    train_csv = Path(DATA_DIR) / "raw" / "train.csv"
    train_csv.parent.mkdir(parents=True, exist_ok=True)
    train_csv.write_text("price_eur,size_m2\n100000,55\n", encoding="utf-8")

    stale_job = TrainingJob(
        job_id="stale-job",
        status=JobStatus.queued,
        csv_path=str(train_csv),
        progress=0,
        updated_at=datetime.now(UTC) - timedelta(hours=3),
    )
    db_session.add(stale_job)
    await db_session.commit()

    fake_redis = _FakeRedisPool()

    async def fake_create_pool(*_args, **_kwargs):
        return fake_redis

    monkeypatch.setattr("app.api.train.create_pool", fake_create_pool)

    resp = await client.post("/api/train/start", json={"csv_path": "raw/train.csv"}, headers=admin_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert fake_redis.enqueued and fake_redis.enqueued[0][0] == "run_training"

    result = await db_session.execute(select(TrainingJob).where(TrainingJob.job_id == "stale-job"))
    refreshed_stale_job = result.scalar_one()
    assert refreshed_stale_job.status == JobStatus.failed
    assert refreshed_stale_job.stage == "stale"


# ── GET /api/train/jobs ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_train_jobs_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/train/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_train_jobs_empty_list(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/train/jobs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_train_jobs_viewer_can_list(client: AsyncClient, viewer_headers: dict):
    """Viewer role can list jobs (read access is for any authenticated user)."""
    resp = await client.get("/api/train/jobs", headers=viewer_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["items"], list)


# ── DELETE /api/train/jobs/clear ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_jobs_unauthenticated(client: AsyncClient):
    resp = await client.delete("/api/train/jobs/clear")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_clear_jobs_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.delete("/api/train/jobs/clear", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_clear_jobs_admin_success(client: AsyncClient, admin_headers: dict):
    resp = await client.delete("/api/train/jobs/clear", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0
