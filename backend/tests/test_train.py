"""Training endpoint tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.training_job import JobStatus, TrainingJob


class _FakeRedisPool:
    def __init__(
        self,
        payloads: dict[str, str] | None = None,
        *,
        enqueue_result=object(),
        enqueue_error: Exception | None = None,
    ):
        self.payloads = payloads or {}
        self.enqueued: list[tuple[str, str, str]] = []
        self.enqueue_result = enqueue_result
        self.enqueue_error = enqueue_error

    async def get(self, key: str) -> str | None:
        return self.payloads.get(key)

    async def enqueue_job(self, func_name: str, job_id: str, csv_path: str):
        if self.enqueue_error is not None:
            raise self.enqueue_error
        self.enqueued.append((func_name, job_id, csv_path))
        return self.enqueue_result

    async def close(self) -> None:
        pass


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
    resp = await client.post(
        "/api/train/start",
        json={"csv_path": "nonexistent.csv"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_train_start_blank_csv_path_rejected(client: AsyncClient, admin_headers: dict):
    resp = await client.post(
        "/api/train/start",
        json={"csv_path": "   "},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_train_start_path_traversal_rejected(client: AsyncClient, admin_headers: dict):
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
):
    job = TrainingJob(job_id="active-job", status=JobStatus.running, csv_path="/tmp/train.csv", progress=12)
    db_session.add(job)
    await db_session.commit()

    client._transport.app.state.redis = _FakeRedisPool(
        {
            "training_job:active-job": json.dumps(
                {"status": "running", "stage": "fitting", "progress": 48, "updated_at": 1}
            )
        }
    )

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
):
    job = TrainingJob(job_id="status-job", status=JobStatus.running, csv_path="/tmp/train.csv", progress=12)
    db_session.add(job)
    await db_session.commit()

    client._transport.app.state.redis = _FakeRedisPool(
        {
            "training_job:status-job": json.dumps(
                {"status": "running", "stage": "fitting", "progress": 64, "updated_at": 1}
            )
        }
    )

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
    tmp_path: Path,
):
    fake_data_dir = tmp_path / "data"
    train_csv = fake_data_dir / "raw" / "train.csv"
    train_csv.parent.mkdir(parents=True, exist_ok=True)
    train_csv.write_text("price_eur,size_m2\n100000,55\n", encoding="utf-8")
    monkeypatch.setattr("app.api.train.DATA_DIR", str(fake_data_dir))

    job = TrainingJob(job_id="active-job", status=JobStatus.running, csv_path=str(train_csv), progress=12)
    db_session.add(job)
    await db_session.commit()

    client._transport.app.state.redis = _FakeRedisPool(
        {
            "training_job:active-job": json.dumps(
                {"status": "running", "stage": "fitting", "progress": 48, "updated_at": 1}
            )
        }
    )

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
    tmp_path: Path,
):
    fake_data_dir = tmp_path / "data"
    train_csv = fake_data_dir / "raw" / "train.csv"
    train_csv.parent.mkdir(parents=True, exist_ok=True)
    train_csv.write_text("price_eur,size_m2\n100000,55\n", encoding="utf-8")
    monkeypatch.setattr("app.api.train.DATA_DIR", str(fake_data_dir))

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
    client._transport.app.state.redis = fake_redis

    resp = await client.post("/api/train/start", json={"csv_path": "raw/train.csv"}, headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert fake_redis.enqueued and fake_redis.enqueued[0][0] == "run_training"

    result = await db_session.execute(select(TrainingJob).where(TrainingJob.job_id == "stale-job"))
    refreshed_stale_job = result.scalar_one()
    assert refreshed_stale_job.status == JobStatus.failed
    assert refreshed_stale_job.stage == "stale"


@pytest.mark.asyncio
async def test_train_start_marks_job_failed_when_queue_enqueue_fails(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    fake_data_dir = tmp_path / "data"
    train_csv = fake_data_dir / "raw" / "train.csv"
    train_csv.parent.mkdir(parents=True, exist_ok=True)
    train_csv.write_text("price_eur,size_m2\n100000,55\n", encoding="utf-8")
    monkeypatch.setattr("app.api.train.DATA_DIR", str(fake_data_dir))

    client._transport.app.state.redis = _FakeRedisPool(enqueue_error=RuntimeError("redis down"))

    resp = await client.post("/api/train/start", json={"csv_path": "raw/train.csv"}, headers=admin_headers)

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Training worker queue is unavailable"

    rows = (await db_session.execute(select(TrainingJob).order_by(TrainingJob.created_at.desc()))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == JobStatus.failed
    assert rows[0].stage == "error"
    assert rows[0].error == "Training worker queue is unavailable"


@pytest.mark.asyncio
async def test_train_jobs_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/train/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_train_jobs_empty_list(client: AsyncClient, admin_headers: dict):
    client._transport.app.state.redis = _FakeRedisPool()

    resp = await client.get("/api/train/jobs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_train_jobs_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/train/jobs", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_train_active_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/train/active", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_train_status_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/train/status/any-job", headers=viewer_headers)
    assert resp.status_code == 403


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
    client._transport.app.state.redis = _FakeRedisPool()

    resp = await client.delete("/api/train/jobs/clear", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 0


@pytest.mark.asyncio
async def test_clear_jobs_admin_conflict_while_active_job_exists(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
):
    job = TrainingJob(job_id="active-job", status=JobStatus.running, csv_path="/tmp/train.csv", progress=12)
    db_session.add(job)
    await db_session.commit()

    client._transport.app.state.redis = _FakeRedisPool(
        {
            "training_job:active-job": json.dumps(
                {"status": "running", "stage": "fitting", "progress": 48, "updated_at": 1}
            )
        }
    )

    resp = await client.delete("/api/train/jobs/clear", headers=admin_headers)

    assert resp.status_code == 409
    payload = resp.json()
    assert payload["detail"] == "Cannot clear training jobs while a job is queued or running"
    assert payload["job_id"] == "active-job"

    remaining = await db_session.execute(select(func.count(TrainingJob.id)))
    assert remaining.scalar_one() == 1
