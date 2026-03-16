"""Phase 11 security tests: health response, generic errors, path traversal."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_keeps_version_but_redacts_environment_in_production(client: AsyncClient):
    """In production mode, /api/health should expose the app version but not the environment."""
    with patch("app.api.health.get_settings") as mock_settings:
        s = mock_settings.return_value
        s.app_env = "production"
        s.app_version = "0.8.9"
        s.database_url = "sqlite+aiosqlite:///:memory:"
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("version") == "0.8.9"
    assert data.get("environment") is None


@pytest.mark.asyncio
async def test_admin_role_error_is_generic(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001
):
    """PATCH user with invalid role should return 'Invalid role', not leak the actual role value."""
    resp = await client.get("/api/admin/users", headers=admin_headers)
    viewer = next(u for u in resp.json()["items"] if u["role"] == "viewer")

    resp = await client.patch(
        f"/api/admin/users/{viewer['id']}",
        json={"role": "superadmin"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail == "Invalid role"
    assert "superadmin" not in detail


@pytest.mark.asyncio
async def test_path_traversal_blocked(client: AsyncClient, admin_headers: dict):
    """Path traversal attempts via prepare-etn-kpp should be rejected."""
    resp = await client.post(
        "/api/data/prepare-etn-kpp",
        json={
            "posli_csv_path": "../../../etc/passwd",
            "delistavb_csv_path": "/data/uploads/d.csv",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 400
