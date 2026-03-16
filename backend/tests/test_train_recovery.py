"""Unit tests for training recovery helpers without the HTTP client harness."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.train import _reconcile_active_job
from app.models.training_job import JobStatus, TrainingJob


class _FakeRedis:
    def __init__(self, payloads: dict[str, str] | None = None):
        self.payloads = payloads or {}

    async def get(self, key: str) -> str | None:
        return self.payloads.get(key)


@pytest.mark.asyncio
async def test_reconcile_active_job_returns_live_job_with_redis_state(db_session):
    job = TrainingJob(job_id="live-job", status=JobStatus.running, csv_path="/tmp/train.csv", progress=10)
    db_session.add(job)
    await db_session.commit()

    active_job, active_state = await _reconcile_active_job(
        db_session,
        _FakeRedis(
            {
                "training_job:live-job": json.dumps(
                    {"status": "running", "stage": "fitting", "progress": 62, "updated_at": 1}
                )
            }
        ),
    )

    assert active_job is not None
    assert active_job.job_id == "live-job"
    assert active_state is not None
    assert active_state["progress"] == 62


@pytest.mark.asyncio
async def test_reconcile_active_job_marks_missing_stale_jobs_failed(db_session):
    stale_job = TrainingJob(
        job_id="stale-job",
        status=JobStatus.queued,
        csv_path="/tmp/train.csv",
        progress=0,
        updated_at=datetime.now(UTC) - timedelta(hours=3),
    )
    db_session.add(stale_job)
    await db_session.commit()

    active_job, active_state = await _reconcile_active_job(db_session, _FakeRedis())

    assert active_job is None
    assert active_state is None

    result = await db_session.execute(select(TrainingJob).where(TrainingJob.job_id == "stale-job"))
    refreshed = result.scalar_one()
    assert refreshed.status == JobStatus.failed
    assert refreshed.stage == "stale"
