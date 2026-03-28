"""Delete empty per-municipality ZIP stubs from uploads/ and clean DB records.

These 424 files (212 municipalities × kupoprodajni/najemni) are 0-byte placeholders.
ETN_SLO_YYYY_KPP/NP files already cover all municipalities.

DB cleanup is automatic: _sync_upload_directory_records() removes stale DB records
on the next /api/data/datasets/rescan call (it deletes records where file no longer exists).

Run from the backend directory:
    python scripts/delete_municipal_zips.py
    python scripts/delete_municipal_zips.py --dry-run
"""

import argparse
import os
import re
import sys

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")
PATTERN = re.compile(r"^\d+_.+_(kupoprodajni|najemni)\.zip$", re.IGNORECASE)


def main(dry_run: bool) -> None:
    if not os.path.isdir(UPLOADS_DIR):
        print(f"Uploads directory not found: {UPLOADS_DIR}")
        sys.exit(1)

    mode = "[DRY RUN] " if dry_run else ""
    print(f"{mode}Scanning {UPLOADS_DIR} for municipal ZIP stubs...")

    to_delete: list[str] = []
    skipped_nonempty: list[str] = []

    for filename in sorted(os.listdir(UPLOADS_DIR)):
        if not PATTERN.match(filename):
            continue
        filepath = os.path.join(UPLOADS_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        size = os.path.getsize(filepath)
        if size != 0:
            skipped_nonempty.append(f"  SKIP (size={size} bytes): {filename}")
            continue
        to_delete.append(filepath)

    print(f"Found {len(to_delete)} empty municipal ZIPs to delete")
    if skipped_nonempty:
        print(f"Skipped {len(skipped_nonempty)} non-empty files (safety check):")
        for s in skipped_nonempty:
            print(s)

    if not to_delete:
        print("Nothing to delete.")
        return

    deleted = 0
    for filepath in to_delete:
        if not dry_run:
            os.remove(filepath)
        deleted += 1
        if deleted % 100 == 0:
            print(f"  {mode}Processed {deleted} files...")

    print(f"\n{mode}Done: {deleted} files deleted from disk.")
    if dry_run:
        print("Run without --dry-run to apply changes.")
    else:
        print("DB cleanup: call POST /api/data/datasets/rescan to remove stale DB records.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete empty municipal ZIP stubs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
