from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.activity import ActivityEvent
from app.models.prepare_run import PrepareRun
from app.models.training_job import JobStatus, TrainingJob


def _build_market_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price_eur": [210_000, 245_000, 180_000],
            "size_m2": [62, 71, 67],
            "uporabna_povrsina": [60, 69, 64],
            "municipality": ["Ljubljana", "Ljubljana", "Škofja Loka"],
            "property_type": ["stanovanje", "stanovanje", "stanovanje"],
            "source_label": ["2023", "2024", "2024"],
            "statistical_region": ["osrednjeslovenska", "osrednjeslovenska", "gorenjska"],
            "latitude": [100_000.0, 100_100.0, 100_200.0],
            "longitude": [460_000.0, 460_100.0, 460_200.0],
        }
    )


@pytest.mark.asyncio
async def test_workspace_crud_is_user_scoped(
    client: AsyncClient,
    viewer_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    create = await client.post(
        "/api/workspaces",
        headers=viewer_headers,
        json={
            "name": "Ljubljana lens",
            "scope": "private",
            "page": "market",
            "filters": {"municipality": "Ljubljana"},
            "tab": "transactions",
            "sort": "price_eur",
            "columns": ["municipality", "price_eur"],
            "pinned": True,
        },
    )
    assert create.status_code == 201
    workspace = create.json()
    workspace_id = workspace["id"]

    listing = await client.get("/api/workspaces?page=market", headers=viewer_headers)
    assert listing.status_code == 200
    assert listing.json()[0]["name"] == "Ljubljana lens"

    foreign = await client.get(f"/api/workspaces/{workspace_id}", headers=admin_headers)
    assert foreign.status_code == 404

    updated = await client.patch(
        f"/api/workspaces/{workspace_id}",
        headers=viewer_headers,
        json={"name": "Pinned Ljubljana", "pinned": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Pinned Ljubljana"
    assert updated.json()["pinned"] is False

    deleted = await client.delete(f"/api/workspaces/{workspace_id}", headers=viewer_headers)
    assert deleted.status_code == 204

    listing_after = await client.get("/api/workspaces", headers=viewer_headers)
    assert listing_after.status_code == 200
    assert listing_after.json() == []


@pytest.mark.asyncio
async def test_workspace_create_rejects_unknown_page(client: AsyncClient, viewer_headers: dict[str, str]):
    resp = await client.post(
        "/api/workspaces",
        headers=viewer_headers,
        json={
            "name": "Broken page",
            "scope": "private",
            "page": "not-a-real-page",
            "filters": {},
            "tab": None,
            "sort": None,
            "columns": [],
            "pinned": False,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_watchlist_crud_and_feed(
    client: AsyncClient,
    viewer_headers: dict[str, str],
):
    from unittest.mock import patch

    with patch("app.api.workbench._prepare_market_df", return_value=_build_market_df()):
        created = await client.post(
            "/api/watchlists",
            headers=viewer_headers,
            json={
                "entity_type": "municipality",
                "entity_key": "ljubljana",
                "display_label": "Ljubljana",
                "metadata": {"link": "/obcine/ljubljana"},
            },
        )
        assert created.status_code == 201
        watchlist_id = created.json()["id"]

        listing = await client.get("/api/watchlists", headers=viewer_headers)
        assert listing.status_code == 200
        assert listing.json()[0]["display_label"] == "Ljubljana"

        feed = await client.get("/api/watchlists/feed", headers=viewer_headers)
        assert feed.status_code == 200
        assert feed.json()[0]["display_label"] == "Ljubljana"
        assert feed.json()[0]["link"] == "/obcine/ljubljana"

        deleted = await client.delete(f"/api/watchlists/{watchlist_id}", headers=viewer_headers)
        assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_watchlist_create_rejects_unknown_entity_type(client: AsyncClient, viewer_headers: dict[str, str]):
    resp = await client.post(
        "/api/watchlists",
        headers=viewer_headers,
        json={
            "entity_type": "listing",
            "entity_key": "123",
            "display_label": "Listing 123",
            "metadata": {},
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_activity_feed_tracks_read_state(client: AsyncClient, viewer_headers: dict[str, str]):
    created = await client.post(
        "/api/workspaces",
        headers=viewer_headers,
        json={
            "name": "Dashboard pin",
            "scope": "private",
            "page": "dashboard",
            "filters": {},
            "tab": "overview",
            "sort": None,
            "columns": [],
            "pinned": True,
        },
    )
    assert created.status_code == 201

    unread = await client.get("/api/activity/unread", headers=viewer_headers)
    assert unread.status_code == 200
    assert unread.json()["unread"] >= 1

    feed = await client.get("/api/activity/feed", headers=viewer_headers)
    assert feed.status_code == 200
    event = next(item for item in feed.json() if item["id"].startswith("event:"))
    assert event["is_read"] is False

    event_id = int(event["id"].split(":")[1])
    marked = await client.post(f"/api/activity/{event_id}/read", headers=viewer_headers)
    assert marked.status_code == 200
    assert marked.json()["ok"] is True

    unread_after = await client.get("/api/activity/unread", headers=viewer_headers)
    assert unread_after.status_code == 200
    assert unread_after.json()["unread"] == 0


@pytest.mark.asyncio
async def test_workspace_activity_links_use_real_route_paths(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session,
):
    created = await client.post(
        "/api/workspaces",
        headers=admin_headers,
        json={
            "name": "Admin data view",
            "scope": "private",
            "page": "data",
            "filters": {},
            "tab": "library",
            "sort": None,
            "columns": [],
            "pinned": False,
        },
    )
    assert created.status_code == 201

    municipality_view = await client.post(
        "/api/workspaces",
        headers=admin_headers,
        json={
            "name": "Ljubljana municipality",
            "scope": "private",
            "page": "municipality",
            "filters": {"slug": "ljubljana"},
            "tab": "overview",
            "sort": None,
            "columns": [],
            "pinned": False,
        },
    )
    assert municipality_view.status_code == 201

    events = (await db_session.execute(select(ActivityEvent).order_by(ActivityEvent.created_at.desc()))).scalars().all()
    links = {event.title: event.link for event in events if event.category == "workspace_created"}

    assert links["Saved workspace: Admin data view"] == "/admin/podatki"
    assert links["Saved workspace: Ljubljana municipality"] == "/obcine/ljubljana"


@pytest.mark.asyncio
async def test_admin_run_endpoints_serialize_prepare_and_training_details(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session,
):
    prepare = PrepareRun(
        job_id="prepare-1",
        status="running",
        stage="pair_processing",
        progress=55,
        total_pairs=2,
        pairs_completed=1,
        rows=321,
        current_label="2024",
        spatial_phase="kn",
        source_pairs_json=json.dumps([{"year": 2024}, {"year": 2025}]),
        enrichment_options_json=json.dumps({"enable_rn": True, "enable_emv": True}),
        result_json=json.dumps({"output_csv_path": "raw/train.csv", "rows": 321}),
    )
    training = TrainingJob(
        job_id="train-1",
        status=JobStatus.running,
        stage="training_global",
        progress=61,
        csv_path="raw/train.csv",
        rows=321,
        current_model="global",
        current_model_index=1,
        total_models=4,
        current_model_progress=61,
        fitted_trees=610,
        total_trees=1000,
        elapsed_sec=12.5,
        eta_sec=7.5,
    )
    db_session.add_all([prepare, training])
    await db_session.commit()

    prepare_runs = await client.get("/api/admin/prepare-runs", headers=admin_headers)
    assert prepare_runs.status_code == 200
    assert prepare_runs.json()[0]["id"] == "prepare-1"

    prepare_detail = await client.get("/api/admin/prepare-runs/prepare-1", headers=admin_headers)
    assert prepare_detail.status_code == 200
    assert prepare_detail.json()["artifacts"][0]["value"] == "raw/train.csv"
    assert prepare_detail.json()["context"]["current_label"] == "2024"

    training_runs = await client.get("/api/admin/training-runs", headers=admin_headers)
    assert training_runs.status_code == 200
    assert training_runs.json()[0]["id"] == "train-1"

    training_detail = await client.get("/api/admin/training-runs/train-1", headers=admin_headers)
    assert training_detail.status_code == 200
    assert training_detail.json()["context"]["current_model"] == "global"
    assert training_detail.json()["metrics"][0]["value"] == 61


@pytest.mark.asyncio
async def test_admin_run_endpoints_preserve_zero_metrics(
    client: AsyncClient, admin_headers: dict[str, str], db_session
):
    prepare = PrepareRun(
        job_id="prepare-zero",
        status="completed",
        stage="completed",
        progress=100,
        total_pairs=0,
        pairs_completed=0,
        rows=0,
        result_json=json.dumps({"output_csv_path": "raw/train.csv", "rows": 99}),
    )
    training = TrainingJob(
        job_id="train-zero",
        status=JobStatus.running,
        stage="training_global",
        progress=12,
        csv_path="raw/train.csv",
        rows=0,
        elapsed_sec=0,
        eta_sec=0,
    )
    db_session.add_all([prepare, training])
    await db_session.commit()

    prepare_detail = await client.get("/api/admin/prepare-runs/prepare-zero", headers=admin_headers)
    training_detail = await client.get("/api/admin/training-runs/train-zero", headers=admin_headers)

    assert prepare_detail.status_code == 200
    assert training_detail.status_code == 200
    assert prepare_detail.json()["metrics"][1]["value"] == 0
    assert prepare_detail.json()["metrics"][2]["value"] == 0
    assert training_detail.json()["metrics"][1]["value"] == 0
    assert training_detail.json()["metrics"][2]["value"] == 0
    assert training_detail.json()["metrics"][3]["value"] == 0


@pytest.mark.asyncio
async def test_admin_run_endpoints_normalize_absolute_data_paths(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    fake_data_dir = (tmp_path / "data").resolve()
    raw_dir = fake_data_dir / "raw"
    uploads_dir = fake_data_dir / "uploads"
    raw_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    train_csv = (raw_dir / "train.csv").resolve()
    posli_csv = (uploads_dir / "posli.csv").resolve()
    deli_csv = (uploads_dir / "deli.csv").resolve()
    monkeypatch.setattr("app.api.admin.DATA_DIR", str(fake_data_dir))

    prepare = PrepareRun(
        job_id="prepare-paths",
        status="completed",
        stage="completed",
        progress=100,
        source_pairs_json=json.dumps(
            [
                {
                    "year": 2024,
                    "posli_csv_path": str(posli_csv),
                    "delistavb_csv_path": str(deli_csv),
                }
            ]
        ),
        result_json=json.dumps({"output_csv_path": str(train_csv), "rows": 42}),
    )
    training = TrainingJob(
        job_id="train-paths",
        status=JobStatus.completed,
        stage="completed",
        progress=100,
        csv_path=str(train_csv),
        rows=42,
    )
    db_session.add_all([prepare, training])
    await db_session.commit()

    prepare_detail = await client.get("/api/admin/prepare-runs/prepare-paths", headers=admin_headers)
    training_runs = await client.get("/api/admin/training-runs", headers=admin_headers)
    training_detail = await client.get("/api/admin/training-runs/train-paths", headers=admin_headers)

    assert prepare_detail.status_code == 200
    assert training_runs.status_code == 200
    assert training_detail.status_code == 200
    assert prepare_detail.json()["artifacts"][0]["value"] == "raw/train.csv"
    assert prepare_detail.json()["context"]["result"]["output_csv_path"] == "raw/train.csv"
    assert prepare_detail.json()["context"]["pairs"][0]["posli_csv_path"] == "uploads/posli.csv"
    assert prepare_detail.json()["context"]["pairs"][0]["delistavb_csv_path"] == "uploads/deli.csv"
    assert training_runs.json()[0]["summary"] == "raw/train.csv"
    assert training_detail.json()["summary"] == "raw/train.csv"
    assert training_detail.json()["artifacts"][0]["value"] == "raw/train.csv"
