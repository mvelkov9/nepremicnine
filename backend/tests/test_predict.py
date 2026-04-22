"""Prediction endpoint tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

# ── POST /api/predict ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_predict_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/predict", json={"size_m2": 70})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_predict_missing_required_field(client: AsyncClient, admin_headers: dict):
    """size_m2 is required; omitting it must produce 422."""
    resp = await client.post("/api/predict", json={}, headers=admin_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_predict_accepts_d96_tm_coordinates(client: AsyncClient, admin_headers: dict):
    """The API must accept Slovenia D96/TM metric coordinates used by prepared data."""
    fake_result = {
        "predicted_price_eur": 185_000.0,
        "model_used": "global",
        "features_used": {"size_m2": "70.0"},
    }
    with patch("app.api.predict.predict_one", return_value=fake_result):
        resp = await client.post(
            "/api/predict",
            json={"size_m2": 70, "latitude": 100_800.0, "longitude": 460_900.0},
            headers=admin_headers,
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_predict_invalid_size_zero(client: AsyncClient, admin_headers: dict):
    """size_m2 < 1 violates ge=1 → 422."""
    resp = await client.post(
        "/api/predict",
        json={"size_m2": 0},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_predict_success_with_mock_model(client: AsyncClient, admin_headers: dict):
    """Valid prediction with a mocked model service."""
    fake_result = {
        "predicted_price_eur": 185_000.0,
        "model_used": "global",
        "features_used": {"size_m2": "70.0"},
    }
    with patch("app.api.predict.predict_one", return_value=fake_result):
        resp = await client.post(
            "/api/predict",
            json={"size_m2": 70, "rooms": 3, "property_type": "stanovanje"},
            headers=admin_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["predicted_price_eur"] == 185_000.0
    assert data["model_used"] == "global"


@pytest.mark.asyncio
async def test_predict_model_not_loaded(client: AsyncClient, admin_headers: dict):
    """When no model is loaded predict_one raises RuntimeError → 422."""
    with patch("app.api.predict.predict_one", side_effect=RuntimeError("No trained model")):
        resp = await client.post(
            "/api/predict",
            json={"size_m2": 70},
            headers=admin_headers,
        )
    assert resp.status_code == 422


# ── GET /api/predict/history ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_predict_history_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/predict/history")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_predict_history_empty(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/predict/history", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_predict_history_returns_entries(client: AsyncClient, admin_headers: dict):
    """After a successful prediction the history must contain one entry."""
    fake_result = {
        "predicted_price_eur": 200_000.0,
        "model_used": "global",
        "features_used": {"size_m2": "80.0"},
    }
    with patch("app.api.predict.predict_one", return_value=fake_result):
        await client.post("/api/predict", json={"size_m2": 80}, headers=admin_headers)

    resp = await client.get("/api/predict/history", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    entries = data["items"]
    assert len(entries) == 1
    assert entries[0]["predicted_price_eur"] == 200_000.0


# ── DELETE /api/predict/history/clear ────────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_history_unauthenticated(client: AsyncClient):
    resp = await client.delete("/api/predict/history/clear")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_clear_history_viewer_success(client: AsyncClient, viewer_headers: dict):
    resp = await client.delete("/api/predict/history/clear", headers=viewer_headers)
    assert resp.status_code == 200
    assert "deleted" in resp.json()


@pytest.mark.asyncio
async def test_clear_history_admin_success(client: AsyncClient, admin_headers: dict):
    resp = await client.delete("/api/predict/history/clear", headers=admin_headers)
    assert resp.status_code == 200
    assert "deleted" in resp.json()


@pytest.mark.asyncio
async def test_clear_history_only_deletes_current_users_entries(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,
):
    fake_result = {
        "predicted_price_eur": 200_000.0,
        "model_used": "global",
        "features_used": {"size_m2": "80.0"},
    }
    with patch("app.api.predict.predict_one", return_value=fake_result):
        await client.post("/api/predict", json={"size_m2": 80}, headers=admin_headers)
        await client.post("/api/predict", json={"size_m2": 90}, headers=viewer_headers)

    clear_resp = await client.delete("/api/predict/history/clear", headers=viewer_headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["deleted"] == 1

    admin_history = await client.get("/api/predict/history", headers=admin_headers)
    viewer_history = await client.get("/api/predict/history", headers=viewer_headers)

    assert admin_history.status_code == 200
    assert viewer_history.status_code == 200
    assert admin_history.json()["total"] == 1
    assert viewer_history.json()["total"] == 0
