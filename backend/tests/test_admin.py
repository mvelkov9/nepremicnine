"""Admin endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ── GET /api/admin/users ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_users_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/admin/users", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users_admin_success(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 1  # at least the admin


@pytest.mark.asyncio
async def test_list_users_contains_both_users(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001 — ensures viewer user is registered
):
    resp = await client.get("/api/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert "admin@test.com" in emails
    assert "viewer@test.com" in emails


# ── PATCH /api/admin/users/{id} ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_user_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.patch("/api/admin/users/1", json={"role": "admin"}, headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_change_role(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001
):
    """Admin can promote a viewer to admin."""
    # Find the viewer user id
    resp = await client.get("/api/admin/users", headers=admin_headers)
    users = resp.json()
    viewer = next(u for u in users if u["role"] == "viewer")

    resp = await client.patch(
        f"/api/admin/users/{viewer['id']}",
        json={"role": "admin"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_update_user_invalid_role(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001
):
    resp = await client.get("/api/admin/users", headers=admin_headers)
    viewer = next(u for u in resp.json() if u["role"] == "viewer")

    resp = await client.patch(
        f"/api/admin/users/{viewer['id']}",
        json={"role": "superadmin"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_self_forbidden(client: AsyncClient, admin_headers: dict):
    """Admin cannot modify their own account."""
    resp = await client.get("/api/admin/users", headers=admin_headers)
    admin = next(u for u in resp.json() if u["role"] == "admin")

    resp = await client.patch(
        f"/api/admin/users/{admin['id']}",
        json={"role": "viewer"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_nonexistent_user(client: AsyncClient, admin_headers: dict):
    resp = await client.patch("/api/admin/users/9999", json={"role": "viewer"}, headers=admin_headers)
    assert resp.status_code == 404


# ── DELETE /api/admin/users/{id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_user_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.delete("/api/admin/users/1", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_self_forbidden(client: AsyncClient, admin_headers: dict):
    """Admin cannot delete their own account."""
    resp = await client.get("/api/admin/users", headers=admin_headers)
    admin = next(u for u in resp.json() if u["role"] == "admin")

    resp = await client.delete(f"/api/admin/users/{admin['id']}", headers=admin_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_nonexistent_user(client: AsyncClient, admin_headers: dict):
    resp = await client.delete("/api/admin/users/9999", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_success(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001
):
    """Admin can delete another user."""
    resp = await client.get("/api/admin/users", headers=admin_headers)
    viewer = next(u for u in resp.json() if u["role"] == "viewer")

    resp = await client.delete(f"/api/admin/users/{viewer['id']}", headers=admin_headers)
    assert resp.status_code == 204

    # User should no longer appear in the list
    resp = await client.get("/api/admin/users", headers=admin_headers)
    ids = {u["id"] for u in resp.json()}
    assert viewer["id"] not in ids
