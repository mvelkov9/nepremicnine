"""Analysis (listing scoring) endpoint tests."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.prediction import PredictionLog

_LISTING = {
    "size_m2": 65,
    "rooms": 2,
    "municipality": "Ljubljana",
    "property_type": "stanovanje",
    "asking_price": 200_000,
}


# ── POST /api/analysis/score ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/analysis/score", json={"listings": [_LISTING]})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_score_no_model(client: AsyncClient, admin_headers: dict):
    """When no model is loaded the endpoint returns 422."""
    with patch("app.api.analysis.load_model", return_value=None):
        resp = await client.post(
            "/api/analysis/score",
            json={"listings": [_LISTING]},
            headers=admin_headers,
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_score_empty_listings_invalid(client: AsyncClient, admin_headers: dict):
    """Empty listings list violates min_length=1 → 422 validation error."""
    resp = await client.post(
        "/api/analysis/score",
        json={"listings": []},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_score_with_mocked_prediction(client: AsyncClient, admin_headers: dict):
    """Score a listing against a mocked prediction."""
    fake_artifact = {"version": "test"}
    fake_predict = {
        "predicted_price_eur": 190_000.0,
        "model_used": "global",
        "features_used": {},
    }
    with (
        patch("app.api.analysis.load_model", return_value=fake_artifact),
        patch("app.api.analysis.predict_one", return_value=fake_predict),
    ):
        resp = await client.post(
            "/api/analysis/score",
            json={"listings": [_LISTING], "threshold": 15.0},
            headers=admin_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["listings"]) == 1
    assert "deviation_pct" in data["listings"][0]


@pytest.mark.asyncio
async def test_score_viewer_can_access(client: AsyncClient, viewer_headers: dict):
    """Scoring is available to any authenticated user, not just admin."""
    with patch("app.api.analysis.load_model", return_value=None):
        resp = await client.post(
            "/api/analysis/score",
            json={"listings": [_LISTING]},
            headers=viewer_headers,
        )
    # 422 because no model, but NOT 403 — access is allowed
    assert resp.status_code == 422


# ── Input validation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_invalid_asking_price_negative(client: AsyncClient, admin_headers: dict):
    """asking_price must be >= 0; negative value → 422."""
    invalid_listing = {**_LISTING, "asking_price": -1}
    resp = await client.post(
        "/api/analysis/score",
        json={"listings": [invalid_listing]},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_score_too_many_listings(client: AsyncClient, admin_headers: dict):
    """max_length=500 on listings; 501 items → 422."""
    listings = [{**_LISTING} for _ in range(501)]
    resp = await client.post(
        "/api/analysis/score",
        json={"listings": listings},
        headers=admin_headers,
    )
    assert resp.status_code == 422


# ── GET /api/analysis/runs ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_runs_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/analysis/runs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_runs_empty(client: AsyncClient, admin_headers: dict):
    """No runs yet → paginated empty response."""
    resp = await client.get("/api/analysis/runs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_runs_after_score(client: AsyncClient, admin_headers: dict):
    """A completed score creates a run record returned by GET /runs."""
    fake_artifact = {"version": "test"}
    fake_predict = {
        "predicted_price_eur": 180_000.0,
        "model_used": "global",
        "features_used": {},
    }
    with (
        patch("app.api.analysis.load_model", return_value=fake_artifact),
        patch("app.api.analysis.predict_one", return_value=fake_predict),
    ):
        score_resp = await client.post(
            "/api/analysis/score",
            json={"listings": [_LISTING]},
            headers=admin_headers,
        )
    assert score_resp.status_code == 200

    runs_resp = await client.get("/api/analysis/runs", headers=admin_headers)
    assert runs_resp.status_code == 200
    data = runs_resp.json()
    assert data["total"] == 1
    run = data["items"][0]
    assert run["total_count"] == 1
    assert "created_at" in run


# ── Enriched score response ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_response_includes_listing_fields(client: AsyncClient, admin_headers: dict):
    """Score response should include original listing fields like size_m2, municipality, property_type."""
    fake_artifact = {"version": "test"}
    fake_predict = {
        "predicted_price_eur": 195_000.0,
        "model_used": "global",
        "features_used": {},
    }
    with (
        patch("app.api.analysis.load_model", return_value=fake_artifact),
        patch("app.api.analysis.predict_one", return_value=fake_predict),
    ):
        resp = await client.post(
            "/api/analysis/score",
            json={"listings": [_LISTING]},
            headers=admin_headers,
        )
    assert resp.status_code == 200
    item = resp.json()["listings"][0]
    assert item["size_m2"] == _LISTING["size_m2"]
    assert item["municipality"] == _LISTING["municipality"]
    assert item["property_type"] == _LISTING["property_type"]
    assert item["rooms"] == _LISTING["rooms"]


@pytest.mark.asyncio
async def test_list_runs_only_returns_current_users_history(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,
):
    fake_artifact = {"version": "test"}
    fake_predict = {
        "predicted_price_eur": 180_000.0,
        "model_used": "global",
        "features_used": {},
    }
    with (
        patch("app.api.analysis.load_model", return_value=fake_artifact),
        patch("app.api.analysis.predict_one", return_value=fake_predict),
    ):
        score_resp = await client.post(
            "/api/analysis/score",
            json={"listings": [_LISTING]},
            headers=admin_headers,
        )
    assert score_resp.status_code == 200

    admin_runs = await client.get("/api/analysis/runs", headers=admin_headers)
    viewer_runs = await client.get("/api/analysis/runs", headers=viewer_headers)

    assert admin_runs.status_code == 200
    assert viewer_runs.status_code == 200
    assert admin_runs.json()["total"] == 1
    assert viewer_runs.json()["total"] == 0
    assert viewer_runs.json()["items"] == []


@pytest.mark.asyncio
async def test_activity_feed_only_includes_current_users_analysis_runs(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,
):
    fake_artifact = {"version": "test"}
    fake_predict = {
        "predicted_price_eur": 180_000.0,
        "model_used": "global",
        "features_used": {},
    }
    with (
        patch("app.api.analysis.load_model", return_value=fake_artifact),
        patch("app.api.analysis.predict_one", return_value=fake_predict),
    ):
        score_resp = await client.post(
            "/api/analysis/score",
            json={"listings": [_LISTING]},
            headers=admin_headers,
        )
    assert score_resp.status_code == 200

    admin_feed = await client.get("/api/activity/feed", headers=admin_headers)
    viewer_feed = await client.get("/api/activity/feed", headers=viewer_headers)

    assert admin_feed.status_code == 200
    assert viewer_feed.status_code == 200
    assert any(item["id"].startswith("analysis:") for item in admin_feed.json())
    assert not any(item["id"].startswith("analysis:") for item in viewer_feed.json())


@pytest.mark.asyncio
async def test_activity_feed_does_not_truncate_busy_single_category(
    client: AsyncClient,
    viewer_headers: dict,
    db_session,
):
    me = await client.get("/api/auth/me", headers=viewer_headers)
    assert me.status_code == 200
    user_id = me.json()["id"]

    db_session.add_all(
        [
            PredictionLog(
                user_id=user_id,
                payload_json=json.dumps({"municipality": f"Ljubljana {index}"}, ensure_ascii=True),
                predicted_price_eur=200_000 + index,
                used_features_json="{}",
            )
            for index in range(5)
        ]
    )
    await db_session.commit()

    feed = await client.get("/api/activity/feed?limit=5", headers=viewer_headers)

    assert feed.status_code == 200
    items = feed.json()
    assert len(items) == 5
    assert all(item["id"].startswith("prediction:") for item in items)
