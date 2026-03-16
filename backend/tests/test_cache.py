"""Cache helper and worker invalidation tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.data import PrepareTrainRequest, RpeRnImportRequest, import_rpe_rn_endpoint, prepare_train
from app.tasks.training_worker import run_training
from app.utils.cache import invalidate_cache_prefixes


class _FakeRedis:
    def __init__(self, payloads: dict[str, str] | None = None):
        self.payloads = payloads or {}

    async def get(self, key: str) -> str | None:
        return self.payloads.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.payloads[key] = value

    async def scan(self, cursor=0, match: str | None = None, count: int | None = None):
        prefix = (match or "").rstrip("*")
        keys = [key for key in self.payloads if key.startswith(prefix)] if prefix else list(self.payloads)
        return 0, keys

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.payloads:
                deleted += 1
                self.payloads.pop(key, None)
        return deleted


@pytest.mark.asyncio
async def test_invalidate_cache_prefixes_removes_stats_and_model_entries():
    redis = _FakeRedis(
        {
            "cache:stats:overview": "1",
            "cache:model:info": "2",
            "training_job:abc": "3",
        }
    )

    deleted = await invalidate_cache_prefixes(redis)

    assert deleted == 2
    assert "cache:stats:overview" not in redis.payloads
    assert "cache:model:info" not in redis.payloads
    assert "training_job:abc" in redis.payloads


@pytest.mark.asyncio
async def test_run_training_invalidates_http_caches_after_success(monkeypatch: pytest.MonkeyPatch):
    redis = _FakeRedis({"cache:stats:overview": "1", "cache:model:info": "2"})
    invalidate = AsyncMock()
    result = {
        "rows": 12,
        "duration_sec": 3.5,
        "global_metrics": {"mae": 1.0, "rmse": 2.0, "r2": 0.9},
        "used_features": ["size_m2"],
        "global_importance": {"size_m2": 0.8},
    }

    monkeypatch.setattr("app.tasks.training_worker.train_from_csv", lambda *_args, **_kwargs: result)
    monkeypatch.setattr("app.tasks.training_worker.invalidate_model_cache", lambda: None)
    monkeypatch.setattr("app.tasks.training_worker._record_model_run", AsyncMock())
    monkeypatch.setattr("app.tasks.training_worker._update_job_record", AsyncMock())
    monkeypatch.setattr("app.tasks.training_worker.invalidate_cache_prefixes", invalidate)

    returned = await run_training({"redis": redis}, "job-1", "/tmp/train.csv")

    assert returned == result
    invalidate.assert_awaited_once_with(redis)


def _fake_request(redis: _FakeRedis):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=redis)))


@pytest.mark.asyncio
async def test_prepare_train_invalidates_request_caches(monkeypatch: pytest.MonkeyPatch):
    invalidate = AsyncMock()
    fake_meta = SimpleNamespace(
        model_dump=lambda mode="json": {"exists": True, "relative_path": "raw/train.csv", "rows": 1}
    )

    monkeypatch.setattr("app.api.data._validate_path_within_data_dir", lambda raw_path: f"/tmp/{raw_path}")
    monkeypatch.setattr(
        "app.api.data.prepare_training_csv",
        lambda *_args, **_kwargs: {"rows": 1, "columns": ["price_eur", "size_m2"], "source": "manual"},
    )
    monkeypatch.setattr("app.api.data._get_training_dataset_metadata", lambda: fake_meta)
    monkeypatch.setattr("app.api.data.invalidate_request_caches", invalidate)

    result = await prepare_train(
        PrepareTrainRequest(source_csv_path="uploads/source.csv", column_map={"price_eur": "price_eur"}),
        request=_fake_request(_FakeRedis()),
        _user=object(),
    )

    assert result["output_csv_path"] == "raw/train.csv"
    invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_region_import_invalidates_request_caches(monkeypatch: pytest.MonkeyPatch):
    class _FakeResult:
        @staticmethod
        def scalar_one_or_none():
            return None

    class _FakeDb:
        def __init__(self):
            self.added = []
            self.committed = False

        async def execute(self, *_args, **_kwargs):
            return _FakeResult()

        def add(self, item):
            self.added.append(item)

        async def commit(self):
            self.committed = True

    invalidate = AsyncMock()
    monkeypatch.setattr("app.api.data._validate_path_within_data_dir", lambda raw_path: f"/tmp/{raw_path}")
    monkeypatch.setattr(
        "app.api.data.import_rpe_rn",
        lambda *_args, **_kwargs: {
            "count": 1,
            "regije": ["osrednjeslovenska"],
            "mappings": [
                {
                    "obcina_sifra": "061",
                    "obcina_naziv": "Ljubljana",
                    "regija_naziv": "Osrednjeslovenska",
                    "vir": "RPE/RN",
                }
            ],
        },
    )
    monkeypatch.setattr("app.api.data.invalidate_request_caches", invalidate)
    fake_db = _FakeDb()

    result = await import_rpe_rn_endpoint(
        RpeRnImportRequest(rn_csv_path="uploads/rn.csv"),
        request=_fake_request(_FakeRedis()),
        db=fake_db,
        _user=object(),
    )

    assert result["imported"] == 1
    assert fake_db.committed is True
    assert len(fake_db.added) == 1
    invalidate.assert_awaited_once()
