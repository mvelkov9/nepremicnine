"""Training endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

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
