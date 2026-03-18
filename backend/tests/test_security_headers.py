"""Tests for security headers and CORS configuration."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    """All security response headers should be present."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("permissions-policy") is not None
    assert "geolocation=()" in resp.headers["permissions-policy"]


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient):
    """Every response should include an X-Request-ID header."""
    resp = await client.get("/api/health")
    assert resp.headers.get("x-request-id") is not None
    # UUID format: 8-4-4-4-12 hex characters
    request_id = resp.headers["x-request-id"]
    assert len(request_id) == 36
    assert request_id.count("-") == 4


@pytest.mark.asyncio
async def test_unauthorized_returns_401_not_500(client: AsyncClient):
    """Missing auth should return 401, not leak a 500."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_invalid_jwt_returns_401(client: AsyncClient):
    """A malformed JWT should return 401."""
    resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_jwt_returns_401(client: AsyncClient):
    """An expired JWT (crafted with past exp) should return 401."""
    import time

    from jose import jwt

    from app.config import get_settings

    settings = get_settings()
    expired_payload = {
        "sub": "999",
        "type": "access",
        "exp": int(time.time()) - 3600,  # 1 hour ago
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_access_token_cannot_be_used_as_refresh(client: AsyncClient, admin_token: str):
    """An access token used as a refresh token should be rejected."""
    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": admin_token},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_access_admin_endpoints(client: AsyncClient, viewer_headers: dict):
    """A viewer role should get 403 on admin-only endpoints."""
    resp = await client.get("/api/admin/users", headers=viewer_headers)
    assert resp.status_code == 403

    resp = await client.get("/api/admin/stats", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cache_control_on_regions(client: AsyncClient, admin_headers: dict):
    """GET /api/regions should have Cache-Control header."""
    resp = await client.get("/api/regions", headers=admin_headers)
    assert resp.status_code == 200
    assert "max-age" in resp.headers.get("cache-control", "")
