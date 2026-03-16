"""Analysis (listing scoring) endpoint tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

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
