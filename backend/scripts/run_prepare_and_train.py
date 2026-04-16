import glob
import json
import os
import time

from app.services.data_processing_service import prepare_training_csv_from_etn_kpp_bulk
from app.services.model_service import train_from_csv


def pick_role_file(candidates, role):
    role = role.upper()
    filtered = []
    for path in candidates:
        name = os.path.basename(path).upper()
        if "SIFRANTI" in name:
            continue
        if (
            role == "POSLI"
            and ("POSLI" in name and "DELISTAVB" not in name and "ZEMLJISC" not in name)
            or role == "DELISTAVB"
            and ("DELISTAVB" in name and "POSLI" not in name and "ZEMLJISC" not in name)
            or role == "ZEMLJISCA"
            and ("ZEMLJISC" in name and "POSLI" not in name and "DELISTAVB" not in name)
        ):
            filtered.append(path)

    if not filtered:
        return None

    def score(path):
        name = os.path.basename(path).upper()
        value = 0
        if "ETN_SLO_" in name:
            value += 20
        if "_KPP_" in name:
            value += 10
        if "_NP_" in name:
            value -= 30
        return (value, os.path.getmtime(path), path)

    return sorted(filtered, key=score, reverse=True)[0]


def build_pairs():
    pairs = []
    for year in range(2007, 2027):
        dir_candidates = sorted(
            glob.glob(f"/app/data/uploads/**/ETN_SLO_{year}_KPP_*", recursive=True),
            key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
            reverse=True,
        )
        chosen = None
        for directory in dir_candidates:
            if not os.path.isdir(directory):
                continue
            csvs = glob.glob(os.path.join(directory, "*.csv"))
            posli = pick_role_file(csvs, "POSLI")
            deli = pick_role_file(csvs, "DELISTAVB")
            zem = pick_role_file(csvs, "ZEMLJISCA")
            if posli and deli:
                chosen = (posli, deli, zem)
                break

        if not chosen:
            print(f"[prepare] missing valid pair for year {year}")
            continue

        posli, deli, zem = chosen
        pairs.append(
            {
                "posli_csv_path": posli,
                "delistavb_csv_path": deli,
                "zemljisca_csv_path": zem,
                "year": str(year),
                "label": str(year),
            }
        )

    return pairs


def main():
    pairs = build_pairs()
    print(f"[prepare] pairs selected: {len(pairs)}")
    if not pairs:
        raise SystemExit("No pairs found, aborting.")

    for pair in pairs:
        print(
            "[prepare] pair",
            pair["label"],
            os.path.basename(pair["posli_csv_path"]),
            os.path.basename(pair["delistavb_csv_path"]),
        )

    prepare_started = time.time()
    prepare_result = prepare_training_csv_from_etn_kpp_bulk(
        pairs,
        "/app/data/processed/train.csv",
        enrichment_options={
            "enable_rn": True,
            "enable_ev": True,
            "enable_kn": True,
            "enable_gji": True,
            "enable_dtm": True,
            "enable_emv": True,
            "variant_label": "default",
        },
    )
    prepare_duration = time.time() - prepare_started

    with open("/app/data/processed/prepare_last_result.json", "w", encoding="utf-8") as fh:
        json.dump(prepare_result, fh, ensure_ascii=False, indent=2)

    print("[prepare] done in", round(prepare_duration, 2), "sec")
    print("[prepare] rows", prepare_result.get("rows"))
    print("[prepare] pairs_used", prepare_result.get("pairs_used"))
    print("[prepare] years", sorted((prepare_result.get("per_year") or {}).keys()))

    if prepare_result.get("rows", 0) <= 0:
        raise SystemExit("Prepare produced 0 rows, aborting training.")

    train_started = time.time()
    train_result = train_from_csv("/app/data/processed/train.csv", None)
    train_duration = time.time() - train_started

    with open("/app/data/processed/train_last_result.json", "w", encoding="utf-8") as fh:
        json.dump(train_result, fh, ensure_ascii=False, indent=2)

    print("[train] done in", round(train_duration, 2), "sec")
    metrics = train_result.get("global_metrics") or {}
    print(
        "[train] metrics",
        {
            "mae": metrics.get("mae"),
            "rmse": metrics.get("rmse"),
            "r2": metrics.get("r2"),
            "mape": metrics.get("mape"),
        },
    )
    print("[train] per_type_count", train_result.get("per_type_count"))


if __name__ == "__main__":
    main()
