"""Shared test fixtures."""

from __future__ import annotations

import os

# ── env vars must be set BEFORE any app imports ──────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("APP_ENV", "test")

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base, get_db
from app.main import create_app
from app.rate_limit import limiter

# Disable rate limiter globally for tests
limiter.enabled = False

# Clear cached settings so env vars take effect
get_settings.cache_clear()


# ── Fake Redis (replaces arq RedisPool) ──────────────────────────────────────
class _FakeRedis:
    """In-memory Redis substitute used in tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def close(self) -> None:
        pass


# ── DB session fixture ───────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ── HTTP client fixture ──────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    app = create_app()

    # Inject fake Redis so token-blacklist logic works without a real server
    app.state.redis = _FakeRedis()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Auth helper ──────────────────────────────────────────────────────────────
async def _register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
    full_name: str = "Test User",
) -> str:
    """Register a user and return the access token."""
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    return resp.json()["access_token"]


# ── Token fixtures ───────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    """Register the first user (auto-admin) and return the access token."""
    return await _register_and_login(client, "admin@test.com", full_name="Admin")


@pytest_asyncio.fixture
async def viewer_token(client: AsyncClient, admin_token: str) -> str:  # noqa: ARG001
    """Register a second user (auto-viewer) and return the access token."""
    return await _register_and_login(client, "viewer@test.com", full_name="Viewer")


# ── Header fixtures ──────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def viewer_headers(viewer_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {viewer_token}"}
