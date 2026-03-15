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
async def test_score_empty_listings(client: AsyncClient, admin_headers: dict):
    """Empty listings list should return totals of zero."""
    fake_artifact = {"some": "model"}
    with patch("app.api.analysis.load_model", return_value=fake_artifact):
        resp = await client.post(
            "/api/analysis/score",
            json={"listings": []},
            headers=admin_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["overpriced"] == 0
    assert data["underpriced"] == 0
    assert data["market_aligned"] == 0


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
