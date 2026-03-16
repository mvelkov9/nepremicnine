"""Auth endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_first_user_is_admin(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "admin@test.com",
            "password": "testpass123",
            "full_name": "Test Admin",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "admin@test.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_register_second_user_is_viewer(client: AsyncClient):
    # First user → admin
    await client.post(
        "/api/auth/register",
        json={
            "email": "admin@test.com",
            "password": "testpass123",
            "full_name": "Admin",
        },
    )
    # Second user → viewer
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "viewer@test.com",
            "password": "testpass123",
            "full_name": "Viewer",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "viewer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "dup@test.com",
            "password": "testpass123",
            "full_name": "User",
        },
    )
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "dup@test.com",
            "password": "testpass123",
            "full_name": "User 2",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "login@test.com",
            "password": "testpass123",
            "full_name": "User",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "login@test.com",
            "password": "testpass123",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "wrong@test.com",
            "password": "testpass123",
            "full_name": "User",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "wrong@test.com",
            "password": "wrongpassword",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "me@test.com",
            "password": "testpass123",
            "full_name": "Me User",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "email": "me@test.com",
            "password": "testpass123",
        },
    )
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401  # No bearer token


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "refresh@test.com",
            "password": "testpass123",
            "full_name": "Refresh User",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={
            "email": "refresh@test.com",
            "password": "testpass123",
        },
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_token_rotation_blacklists_old_token(client: AsyncClient):
    """After a refresh, re-using the same refresh token must return 401 (token rotation)."""
    await client.post(
        "/api/auth/register",
        json={"email": "rotation@test.com", "password": "testpass123", "full_name": "Rotation"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "rotation@test.com", "password": "testpass123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # First refresh succeeds and blacklists the token
    first = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200

    # Second use of the same refresh token must be rejected
    second = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_refresh_invalid_token_rejected(client: AsyncClient):
    """A garbage refresh token string must return 401."""
    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": "not.a.valid.jwt"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_blacklists_access_token(client: AsyncClient):
    """After logout, the access token should be rejected on subsequent requests."""
    await client.post(
        "/api/auth/register",
        json={"email": "logout@test.com", "password": "testpass123", "full_name": "Logout User"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "logout@test.com", "password": "testpass123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Logout
    resp = await client.post("/api/auth/logout", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Logged out"

    # Access token should now be blacklisted
    me_resp = await client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_blacklists_refresh_token(client: AsyncClient):
    """Logout with refresh_token body → refresh token is also blacklisted."""
    await client.post(
        "/api/auth/register",
        json={"email": "logout2@test.com", "password": "testpass123", "full_name": "Logout2"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "logout2@test.com", "password": "testpass123"},
    )
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Logout including the refresh token
    await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    # The refresh token must now be blacklisted
    refresh_resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/auth/logout", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_generic_error(client: AsyncClient):
    """Duplicate registration should say 'Registration failed', not leak 'Email already registered'."""
    await client.post(
        "/api/auth/register",
        json={"email": "generic@test.com", "password": "testpass123", "full_name": "User"},
    )
    resp = await client.post(
        "/api/auth/register",
        json={"email": "generic@test.com", "password": "testpass123", "full_name": "User 2"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Registration failed"
    assert "already registered" not in resp.json()["detail"].lower()
