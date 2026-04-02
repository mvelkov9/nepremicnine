"""Promote locally prepared dataset/model artifacts to a production server.

This script intentionally deploys only prepared artifacts, not raw uploads.
Typical usage:

    python backend/scripts/promote_local_artifacts_to_production.py \
        --host nepremicnine-hetzner \
        --remote-app-dir /root/nepremicnine \
        --dataset-csv backend/data/models/research_queue/prepared/train_2010_2026.csv \
        --model-path backend/data/models/price_model.joblib
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import textwrap
from pathlib import Path


def _run(cmd: list[str], *, input_text: str | None = None) -> None:
    print("+", " ".join(shlex.quote(part) for part in cmd))
    subprocess.run(cmd, input=input_text, text=True, check=True)


def _copy_to_remote(local_path: Path, host: str, remote_path: str) -> None:
    _run(["scp", str(local_path), f"{host}:{remote_path}"])


def _resolve_optional(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Artifact not found: {path}")
    return path


def _default_sidecar(path: Path, suffix: str) -> Path | None:
    candidate = Path(f"{path}{suffix}")
    return candidate if candidate.exists() else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="nepremicnine-hetzner", help="SSH host or alias")
    parser.add_argument("--remote-app-dir", default="/root/nepremicnine", help="Remote repo path")
    parser.add_argument("--dataset-csv", help="Prepared CSV to promote as /app/data/raw/train.csv")
    parser.add_argument(
        "--dataset-metadata",
        help="Optional metadata JSON for the dataset (defaults to <dataset>.metadata.json when present)",
    )
    parser.add_argument("--model-path", help="Model artifact to promote as price_model.joblib")
    parser.add_argument(
        "--train-summary",
        help="Optional model summary JSON (defaults to train_summary_latest.json next to model when present)",
    )
    parser.add_argument(
        "--prepare-summary",
        help="Optional prepare summary JSON (defaults to prepare_train_latest.json next to model when present)",
    )
    parser.add_argument("--backend-service", default="backend")
    parser.add_argument("--worker-service", default="worker")
    parser.add_argument(
        "--compose-file",
        action="append",
        dest="compose_files",
        default=["docker-compose.yml", "docker-compose.prod.yml"],
        help="Compose files to use on the remote host. May be passed multiple times.",
    )
    parser.add_argument("--skip-restart", action="store_true", help="Do not restart backend/worker after copy")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    dataset_csv = _resolve_optional(args.dataset_csv)
    model_path = _resolve_optional(args.model_path)
    dataset_metadata = _resolve_optional(args.dataset_metadata)
    train_summary = _resolve_optional(args.train_summary)
    prepare_summary = _resolve_optional(args.prepare_summary)

    if dataset_csv and dataset_metadata is None:
        dataset_metadata = _default_sidecar(dataset_csv, ".metadata.json")

    if model_path and train_summary is None:
        candidate = model_path.with_name("train_summary_latest.json")
        train_summary = candidate if candidate.exists() else None

    if model_path and prepare_summary is None:
        candidate = model_path.with_name("prepare_train_latest.json")
        prepare_summary = candidate if candidate.exists() else None

    if dataset_csv is None and model_path is None:
        raise SystemExit("Nothing to promote. Pass at least --dataset-csv or --model-path.")

    compose_args = " ".join(f"-f {shlex.quote(compose_file)}" for compose_file in args.compose_files)
    remote_tmp = f"{args.remote_app_dir}/.artifact-promote"

    files_to_copy: list[tuple[Path, str]] = []
    if dataset_csv:
        files_to_copy.append((dataset_csv, f"{remote_tmp}/dataset.csv"))
    if dataset_metadata:
        files_to_copy.append((dataset_metadata, f"{remote_tmp}/dataset.csv.metadata.json"))
    if model_path:
        files_to_copy.append((model_path, f"{remote_tmp}/price_model.joblib"))
    if train_summary:
        files_to_copy.append((train_summary, f"{remote_tmp}/train_summary_latest.json"))
    if prepare_summary:
        files_to_copy.append((prepare_summary, f"{remote_tmp}/prepare_train_latest.json"))

    print("Preparing remote staging directory...")
    _run(["ssh", args.host, f"mkdir -p {shlex.quote(remote_tmp)}"])

    for local_path, remote_path in files_to_copy:
        if args.dry_run:
            print(f"[dry-run] would copy {local_path} -> {args.host}:{remote_path}")
        else:
            _copy_to_remote(local_path, args.host, remote_path)

    remote_script = textwrap.dedent(
        f"""
        set -euo pipefail
        cd {shlex.quote(args.remote_app_dir)}
        backend_cid=$(docker compose {compose_args} ps -q {shlex.quote(args.backend_service)})
        if [ -z "$backend_cid" ]; then
          echo "Backend container is not running. Start the stack first." >&2
          exit 1
        fi
        docker exec "$backend_cid" sh -lc 'mkdir -p /app/data/raw /app/data/models /app/models'
        if [ -f {shlex.quote(remote_tmp + "/dataset.csv")} ]; then
          docker cp {shlex.quote(remote_tmp + "/dataset.csv")} "$backend_cid":/app/data/raw/train.csv
          rm -f {shlex.quote(remote_tmp + "/dataset.csv")}
        fi
        if [ -f {shlex.quote(remote_tmp + "/dataset.csv.metadata.json")} ]; then
          docker cp {shlex.quote(remote_tmp + "/dataset.csv.metadata.json")} "$backend_cid":/app/data/raw/train.csv.metadata.json
          rm -f {shlex.quote(remote_tmp + "/dataset.csv.metadata.json")}
        fi
        docker exec "$backend_cid" sh -lc 'rm -f /app/data/raw/train.csv.quality-summary.json'
        if [ -f {shlex.quote(remote_tmp + "/price_model.joblib")} ]; then
          docker cp {shlex.quote(remote_tmp + "/price_model.joblib")} "$backend_cid":/app/models/price_model.joblib
          docker cp {shlex.quote(remote_tmp + "/price_model.joblib")} "$backend_cid":/app/data/models/price_model.joblib
          rm -f {shlex.quote(remote_tmp + "/price_model.joblib")}
        fi
        if [ -f {shlex.quote(remote_tmp + "/train_summary_latest.json")} ]; then
          docker cp {shlex.quote(remote_tmp + "/train_summary_latest.json")} "$backend_cid":/app/data/models/train_summary_latest.json
          rm -f {shlex.quote(remote_tmp + "/train_summary_latest.json")}
        fi
        if [ -f {shlex.quote(remote_tmp + "/prepare_train_latest.json")} ]; then
          docker cp {shlex.quote(remote_tmp + "/prepare_train_latest.json")} "$backend_cid":/app/data/models/prepare_train_latest.json
          rm -f {shlex.quote(remote_tmp + "/prepare_train_latest.json")}
        fi
        rmdir {shlex.quote(remote_tmp)} 2>/dev/null || true
        {"docker compose " + compose_args + " restart " + shlex.quote(args.backend_service) + " " + shlex.quote(args.worker_service) if not args.skip_restart else "true"}
        sleep 5
        curl -fsS http://127.0.0.1:${{BACKEND_PORT:-8001}}/api/health || true
        """
    ).strip()

    if args.dry_run:
        print("\n[dry-run] would execute remote script:\n")
        print(remote_script)
        return 0

    print("Applying artifacts on production...")
    _run(["ssh", args.host, "bash -s"], input_text=remote_script)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
