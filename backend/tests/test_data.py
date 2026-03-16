"""Data endpoint tests."""

import io
from pathlib import Path

import pytest
from httpx import AsyncClient


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

    posli = Path("/home/michel/nepremicnine-v2/backend/data/uploads/posli.csv")
    deli = Path("/home/michel/nepremicnine-v2/backend/data/uploads/deli.csv")
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
    assert recorded["pairs"][0]["posli_csv_path"].endswith("/backend/data/uploads/posli.csv")
    assert recorded["pairs"][0]["delistavb_csv_path"].endswith("/backend/data/uploads/deli.csv")
