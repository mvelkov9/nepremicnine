"""Re-register dataset files that exist on disk but are missing from the DB.

Run inside the backend container:
    python scripts/reregister_datasets.py
"""

import asyncio
import hashlib
import os
import sys

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session
from app.models.dataset import DatasetFile

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")


def _compute_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_type_from_ext(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".gpkg"):
        return "gpkg"
    if lower.endswith(".zip"):
        return "shape-zip"
    return "csv"


def _original_name_from_stored(filename: str) -> str:
    """Strip the UUID prefix (32 hex + underscore) from stored filenames."""
    # Format: <32hex>_<original_name>
    if len(filename) > 33 and filename[32] == "_":
        return filename[33:]
    return filename


async def main():
    if not os.path.isdir(UPLOADS_DIR):
        print(f"Uploads directory not found: {UPLOADS_DIR}")
        return

    files = sorted(os.listdir(UPLOADS_DIR))
    print(f"Found {len(files)} files on disk in {UPLOADS_DIR}")

    registered = 0
    skipped = 0

    async with async_session() as session:
        # Get all existing hashes
        result = await session.execute(select(DatasetFile.file_hash))
        existing_hashes = {row[0] for row in result.all()}
        print(f"Already registered in DB: {len(existing_hashes)} files")

        for filename in files:
            filepath = os.path.join(UPLOADS_DIR, filename)
            if not os.path.isfile(filepath):
                continue

            file_hash = _compute_sha256(filepath)
            if file_hash in existing_hashes:
                skipped += 1
                continue

            original_name = _original_name_from_stored(filename)
            source_type = _source_type_from_ext(original_name)
            stored_path = f"uploads/{filename}"

            record = DatasetFile(
                original_name=original_name,
                stored_path=stored_path,
                source_type=source_type,
                file_hash=file_hash,
                uploaded_by=1,  # admin user
            )
            session.add(record)
            existing_hashes.add(file_hash)
            registered += 1

            if registered % 50 == 0:
                print(f"  ... registered {registered} so far")

        await session.commit()

    print(f"\nDone: {registered} files registered, {skipped} already existed")


if __name__ == "__main__":
    asyncio.run(main())
