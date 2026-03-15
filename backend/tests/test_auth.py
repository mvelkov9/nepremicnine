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
