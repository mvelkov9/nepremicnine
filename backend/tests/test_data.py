"""Data endpoint tests."""

import io
from pathlib import Path

import pandas as pd
import pytest
from httpx import AsyncClient

from app.api.data import DATA_DIR
from app.schemas.dataset import TrainingDatasetResponse
from app.services.data_processing_service import prepare_training_csv_from_etn_kpp_bulk


async def _get_admin_token(client: AsyncClient) -> str:
    await client.post(
        "/api/auth/register",
        json={
            "email": "admin@test.com",
            "password": "testpass123",
            "full_name": "Admin",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "admin@test.com",
            "password": "testpass123",
        },
    )
    return resp.json()["access_token"]


async def _get_viewer_token(client: AsyncClient) -> str:
    # Ensure admin exists first
    await _get_admin_token(client)
    await client.post(
        "/api/auth/register",
        json={
            "email": "viewer@test.com",
            "password": "testpass123",
            "full_name": "Viewer",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={
            "email": "viewer@test.com",
            "password": "testpass123",
        },
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_upload_requires_admin(client: AsyncClient):
    token = await _get_viewer_token(client)
    csv_content = b"col1,col2\n1,2\n3,4\n"
    resp = await client.post(
        "/api/data/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_and_list(client: AsyncClient):
    token = await _get_admin_token(client)
    csv_content = b"col1,col2\n1,2\n3,4\n"

    # Upload
    resp = await client.post(
        "/api/data/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["uploaded"]) == 1
    assert data["uploaded"][0]["original_name"] == "test.csv"
    assert data["uploaded"][0]["relative_path"].endswith("_test.csv")
    assert data["uploaded"][0]["row_count"] == 2

    # List
    resp = await client.get(
        "/api/data/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1
    assert resp.json()["items"][0]["relative_path"].startswith("uploads/")


@pytest.mark.asyncio
async def test_training_dataset_endpoint_reports_prepared_csv(client: AsyncClient):
    token = await _get_admin_token(client)
    resp = await client.get(
        "/api/data/training-dataset",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["relative_path"] == "raw/train.csv"
    assert "exists" in data


@pytest.mark.asyncio
async def test_upload_dedup(client: AsyncClient):
    token = await _get_admin_token(client)
    csv_content = b"col1,col2\nA,B\n"

    # Upload twice
    await client.post(
        "/api/data/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("dup.csv", io.BytesIO(csv_content), "text/csv")},
    )
    resp = await client.post(
        "/api/data/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("dup.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    assert len(resp.json()["skipped"]) == 1


@pytest.mark.asyncio
async def test_delete_requires_admin(client: AsyncClient):
    viewer_token = await _get_viewer_token(client)
    resp = await client.delete(
        "/api/data/datasets/999",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_datasets_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/data/datasets")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_rejects_invalid_extension(client: AsyncClient):
    """Uploading a .exe file must be rejected with 400."""
    token = await _get_admin_token(client)
    resp = await client.post(
        "/api/data/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("malware.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_bulk_delete_limit(client: AsyncClient):
    """BulkDeleteRequest with >500 IDs should fail validation (422)."""
    token = await _get_admin_token(client)
    resp = await client.post(
        "/api/data/datasets/delete-bulk",
        headers={"Authorization": f"Bearer {token}"},
        json={"dataset_ids": list(range(501))},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_etn_bulk_limit(client: AsyncClient):
    """EtnBulkRequest with >50 pairs should fail validation (422)."""
    token = await _get_admin_token(client)
    pairs = [{"posli_csv_path": "/data/p.csv", "delistavb_csv_path": "/data/d.csv"} for _ in range(51)]
    resp = await client.post(
        "/api/data/prepare-etn-kpp-bulk",
        headers={"Authorization": f"Bearer {token}"},
        json={"pairs": pairs},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_prepare_etn_bulk_resolves_relative_paths(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    token = await _get_admin_token(client)

    recorded = {}

    def fake_prepare(pairs, output_csv_path):
        recorded["pairs"] = pairs
        recorded["output_csv_path"] = output_csv_path
        return {
            "rows": 12,
            "columns": ["price_eur"],
            "source": "etn_kpp_bulk",
            "pairs_received": len(pairs),
            "pairs_used": len(pairs),
            "reports": [],
        }

    monkeypatch.setattr("app.api.data.prepare_training_csv_from_etn_kpp_bulk", fake_prepare)
    monkeypatch.setattr(
        "app.api.data._get_training_dataset_metadata",
        lambda: type(
            "Meta", (), {"model_dump": lambda self, mode="json": {"exists": False, "relative_path": "raw/train.csv"}}
        )(),
    )
    monkeypatch.setattr("app.api.data.TRAIN_CSV", "/tmp/train.csv")

    uploads_dir = Path(DATA_DIR) / "uploads"
    posli = uploads_dir / "posli.csv"
    deli = uploads_dir / "deli.csv"
    posli.parent.mkdir(parents=True, exist_ok=True)
    posli.write_text("id\n1\n", encoding="utf-8")
    deli.write_text("id\n1\n", encoding="utf-8")

    resp = await client.post(
        "/api/data/prepare-etn-kpp-bulk",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "pairs": [
                {
                    "posli_csv_path": "uploads/posli.csv",
                    "delistavb_csv_path": "uploads/deli.csv",
                    "year": "2020",
                    "label": "2020",
                }
            ]
        },
    )

    assert resp.status_code == 200
    assert recorded["pairs"][0]["posli_csv_path"] == str(posli.resolve())
    assert recorded["pairs"][0]["delistavb_csv_path"] == str(deli.resolve())


def test_prepare_etn_bulk_uses_stable_source_keys_for_dedup_and_reports_per_year(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    frames = [
        pd.DataFrame(
            [
                {
                    "source_row_key": "deal-1:part-1",
                    "size_m2": 50,
                    "year_built": 2001,
                    "municipality": "ljubljana",
                    "property_type": "stanovanje",
                    "price_eur": 200000,
                },
                {
                    "source_row_key": "deal-2:part-1",
                    "size_m2": 65,
                    "year_built": 2008,
                    "municipality": "koper",
                    "property_type": "stanovanje",
                    "price_eur": 230000,
                },
            ]
        ),
        pd.DataFrame(
            [
                {
                    "source_row_key": "deal-1:part-1",
                    "size_m2": 50,
                    "year_built": 2001,
                    "municipality": "ljubljana",
                    "property_type": "stanovanje",
                    "price_eur": 200000,
                },
                {
                    "source_row_key": "deal-3:part-1",
                    "size_m2": 74,
                    "year_built": 2014,
                    "municipality": "maribor",
                    "property_type": "hisa",
                    "price_eur": 310000,
                },
            ]
        ),
    ]

    monkeypatch.setattr("app.services.data_processing_service.read_csv_flexible", lambda _path: pd.DataFrame())

    def fake_build(*_args, **_kwargs):
        return frames.pop(0), {"used_size_column": "PRODANA_POVRSINA"}

    monkeypatch.setattr("app.services.data_processing_service.build_training_df_from_etn_kpp", fake_build)

    output_csv = tmp_path / "train.csv"
    result = prepare_training_csv_from_etn_kpp_bulk(
        [
            {"posli_csv_path": "2024_posli.csv", "delistavb_csv_path": "2024_deli.csv", "label": "2024"},
            {"posli_csv_path": "2024_posli_copy.csv", "delistavb_csv_path": "2024_deli_copy.csv", "label": "2024"},
        ],
        str(output_csv),
    )

    saved_df = pd.read_csv(output_csv)
    assert len(saved_df) == 3
    assert result["deduplicated_rows"] == 1
    assert result["per_year"] == {"2024": 3}
    assert "filter_summary" in result
    assert output_csv.with_name("train.csv.metadata.json").exists()


@pytest.mark.asyncio
async def test_training_dataset_endpoint_includes_preparation_metadata(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    token = await _get_admin_token(client)

    monkeypatch.setattr(
        "app.api.data._get_training_dataset_metadata",
        lambda: TrainingDatasetResponse(
            exists=True,
            relative_path="raw/train.csv",
            rows=12,
            columns=["price_eur"],
            preparation_metadata={
                "source": "etn_kpp_bulk",
                "filter_summary": {
                    "building": [{"stage": "building_merged_rows", "rows": 20, "dropped_since_previous": 0}],
                    "land": [{"stage": "land_final_rows", "rows": 5, "dropped_since_previous": 1}],
                },
            },
        ),
    )

    resp = await client.get(
        "/api/data/training-dataset",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["preparation_metadata"]["source"] == "etn_kpp_bulk"
    assert data["preparation_metadata"]["filter_summary"]["building"][0]["stage"] == "building_merged_rows"
