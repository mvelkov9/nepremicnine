from __future__ import annotations

import json

import pandas as pd
import pytest
from httpx import AsyncClient

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
