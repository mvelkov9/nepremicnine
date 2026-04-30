"""Admin endpoint tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.prepare_run import PrepareRun
from app.models.training_job import JobStatus, TrainingJob

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
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 1  # at least the admin


@pytest.mark.asyncio
async def test_list_users_contains_both_users(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001 — ensures viewer user is registered
):
    resp = await client.get("/api/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()["items"]}
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
    users = resp.json()["items"]
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
    viewer = next(u for u in resp.json()["items"] if u["role"] == "viewer")

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
    admin = next(u for u in resp.json()["items"] if u["role"] == "admin")

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
    admin = next(u for u in resp.json()["items"] if u["role"] == "admin")

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
    viewer = next(u for u in resp.json()["items"] if u["role"] == "viewer")

    resp = await client.delete(f"/api/admin/users/{viewer['id']}", headers=admin_headers)
    assert resp.status_code == 204

    # User should no longer appear in the list
    resp = await client.get("/api/admin/users", headers=admin_headers)
    ids = {u["id"] for u in resp.json()["items"]}
    assert viewer["id"] not in ids


# ── GET /api/admin/stats ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_stats_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/admin/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_stats_viewer_forbidden(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/admin/stats", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_success(client: AsyncClient, admin_headers: dict):
    resp = await client.get("/api/admin/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "active_users" in data
    assert "total_predictions" in data
    assert "total_training_jobs" in data
    assert "completed_jobs" in data
    assert "total_datasets" in data
    # At least the admin user exists
    assert data["total_users"] >= 1
    assert data["active_users"] >= 1


@pytest.mark.asyncio
async def test_admin_activity_does_not_truncate_busy_single_category(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
):
    db_session.add_all(
        [
            TrainingJob(
                job_id=f"train-{index}",
                status=JobStatus.running,
                stage="training_global",
                progress=index,
                csv_path="raw/train.csv",
            )
            for index in range(7)
        ]
    )
    await db_session.commit()

    resp = await client.get("/api/admin/activity?limit=7", headers=admin_headers)

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 7
    assert all(item["id"].startswith("training:") for item in items)


@pytest.mark.asyncio
async def test_admin_run_summary_lists_set_short_cache_headers_and_cache_results(
    client: AsyncClient,
    admin_headers: dict,
    db_session,
):
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PrepareRun(
                job_id="prepare-cached-1",
                status="running",
                stage="matching",
                progress=20,
                updated_at=now,
            ),
            TrainingJob(
                job_id="train-cached-1",
                status=JobStatus.running,
                stage="training_global",
                progress=30,
                csv_path="raw/train.csv",
                updated_at=now,
            ),
        ]
    )
    await db_session.commit()

    prepare_first = await client.get("/api/admin/prepare-runs?limit=1", headers=admin_headers)
    training_first = await client.get("/api/admin/training-runs?limit=1", headers=admin_headers)

    assert prepare_first.status_code == 200
    assert training_first.status_code == 200
    assert prepare_first.headers["Cache-Control"] == "private, max-age=15"
    assert training_first.headers["Cache-Control"] == "private, max-age=15"
    assert prepare_first.json()[0]["id"] == "prepare-cached-1"
    assert training_first.json()[0]["id"] == "train-cached-1"

    redis = client._transport.app.state.redis
    assert await redis.get("cache:admin:prepare-runs:1") is not None
    assert await redis.get("cache:admin:training-runs:1") is not None

    db_session.add_all(
        [
            PrepareRun(
                job_id="prepare-cached-2",
                status="completed",
                stage="completed",
                progress=100,
                updated_at=now + timedelta(hours=1),
            ),
            TrainingJob(
                job_id="train-cached-2",
                status=JobStatus.completed,
                stage="completed",
                progress=100,
                csv_path="raw/train.csv",
                updated_at=now + timedelta(hours=1),
            ),
        ]
    )
    await db_session.commit()

    prepare_second = await client.get("/api/admin/prepare-runs?limit=1", headers=admin_headers)
    training_second = await client.get("/api/admin/training-runs?limit=1", headers=admin_headers)

    assert prepare_second.status_code == 200
    assert training_second.status_code == 200
    assert prepare_second.json()[0]["id"] == "prepare-cached-1"
    assert training_second.json()[0]["id"] == "train-cached-1"


# ── GET /api/admin/users — pagination ────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_users_pagination_structure(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001
):
    """Response includes pagination envelope with correct keys and values."""
    resp = await client.get("/api/admin/users?page=1&per_page=1", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "pages" in data
    assert data["page"] == 1
    assert data["per_page"] == 1
    assert len(data["items"]) == 1  # exactly 1 result per page


@pytest.mark.asyncio
async def test_list_users_pagination_page2(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001
):
    """Page 2 with per_page=1 returns the second user."""
    resp_p1 = await client.get("/api/admin/users?page=1&per_page=1", headers=admin_headers)
    resp_p2 = await client.get("/api/admin/users?page=2&per_page=1", headers=admin_headers)
    assert resp_p1.status_code == 200
    assert resp_p2.status_code == 200
    id_p1 = resp_p1.json()["items"][0]["id"]
    id_p2 = resp_p2.json()["items"][0]["id"]
    assert id_p1 != id_p2


@pytest.mark.asyncio
async def test_list_users_search_filter_and_sort(
    client: AsyncClient,
    admin_headers: dict,
    viewer_headers: dict,  # noqa: ARG001
):
    resp = await client.get(
        "/api/admin/users?search=viewer&role=viewer&status=active&sort=email&order=asc",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters"]["search"] == "viewer"
    assert data["filters"]["role"] == "viewer"
    assert data["filters"]["status"] == "active"
    assert data["sort"] == "email"
    assert data["order"] == "asc"
    assert data["page_size"] == data["per_page"]
    assert len(data["items"]) == 1
    assert data["items"][0]["email"] == "viewer@test.com"
