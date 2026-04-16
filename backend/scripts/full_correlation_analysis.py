"""Comprehensive per-type correlation analysis against log(price/m²).

For each property type, compute Spearman correlation between EVERY column
and log(price/m²). Identify unused high-signal features.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # noqa: E402

from app.services.model_service import (  # noqa: E402
    ALWAYS_INCLUDE_NUMERIC,
    PERTYPE_NUMERIC,
    TYPE_EXCLUDE_FEATURES,
    TYPE_FEATURE_CONFIGS,
)

CSV = ROOT / "data" / "raw" / "train_2020_2026.csv"
OUT = ROOT / "data" / "models" / "v8_full_correlation.json"

SALE_TYPE_COL = "vrsta_kupoprodajnega_posla"
TYPE_COL = "property_type"

TYPES = [
    "stanovanje",
    "hisa",
    "parcela",
    "kmetijsko",
    "garaza",
    "poslovni_prostor",
    "industrijski",
    "turisticni",
    "gostinstvo",
]


def main() -> int:
    print(f"Loading {CSV}")
    df = pd.read_csv(CSV, low_memory=False)
    print(f"Rows: {len(df)}, cols: {len(df.columns)}")

    # Filter to market transactions
    if SALE_TYPE_COL in df.columns:
        df = df[df[SALE_TYPE_COL].astype(str) == "1"].reset_index(drop=True)
        print(f"After sale_type=1 filter: {len(df)}")

    # Compute log(price/m²)
    size = pd.to_numeric(df["size_m2"], errors="coerce").clip(lower=1)
    price = pd.to_numeric(df["price_eur"], errors="coerce")
    df["_log_ppm2"] = np.log(price / size)

    # Drop rows with bad target
    df = df[df["_log_ppm2"].notna() & np.isfinite(df["_log_ppm2"])].reset_index(drop=True)
    print(f"After target filter: {len(df)}")

    report: dict = {}

    for ptype in TYPES:
        sub = df[df[TYPE_COL] == ptype].reset_index(drop=True)
        n = len(sub)
        if n < 100:
            print(f"[{ptype}] skip: {n} rows")
            continue
        print(f"\n=== {ptype} (n={n}) ===")

        target = sub["_log_ppm2"].values

        # All numeric columns
        results = []
        for col in sub.columns:
            if col in {"_log_ppm2", "price_eur", "size_m2"}:
                continue
            values = sub[col]
            # Skip non-numeric columns
            numeric = pd.to_numeric(values, errors="coerce")
            valid = numeric.notna()
            n_valid = int(valid.sum())
            if n_valid < max(50, n // 20):
                continue
            if numeric[valid].nunique() <= 1:
                continue
            try:
                spearman = numeric[valid].corr(pd.Series(target[valid], index=numeric[valid].index), method="spearman")
            except Exception:
                continue
            if spearman is None or not np.isfinite(spearman):
                continue
            results.append(
                {
                    "col": col,
                    "corr": float(spearman),
                    "abs_corr": float(abs(spearman)),
                    "fill_rate": float(n_valid / n),
                }
            )

        results.sort(key=lambda x: -x["abs_corr"])

        # What's already in use (ALWAYS_INCLUDE_NUMERIC + type-specific always_numeric)
        cfg = TYPE_FEATURE_CONFIGS.get(ptype, {})
        already = set(cfg.get("always_numeric", ALWAYS_INCLUDE_NUMERIC))
        excluded = TYPE_EXCLUDE_FEATURES.get(ptype, {}).get("numeric", set())
        pool = set(PERTYPE_NUMERIC)

        top_signal = [r for r in results if r["abs_corr"] >= 0.10][:60]

        # Flag: in_always / in_pool / in_excluded / unused
        for r in top_signal:
            c = r["col"]
            if c in excluded:
                r["status"] = "EXCLUDED"
            elif c in already:
                r["status"] = "always_include"
            elif c in pool:
                r["status"] = "in_pool (signal-scored)"
            else:
                r["status"] = "UNUSED"

        # The most interesting set: UNUSED high-signal features
        unused_high_signal = [r for r in top_signal if r["status"] == "UNUSED"]
        excluded_signal = [r for r in top_signal if r["status"] == "EXCLUDED" and r["abs_corr"] >= 0.15]

        print(f"  n_cols_tested: {len(results)}")
        print("  Top 10 by |corr|:")
        for r in top_signal[:10]:
            print(f"    {r['col']:40s} corr={r['corr']:+.3f} fill={r['fill_rate']:.2f} [{r['status']}]")

        if unused_high_signal:
            print(f"  UNUSED high-signal features ({len(unused_high_signal)}):")
            for r in unused_high_signal[:15]:
                print(f"    {r['col']:40s} corr={r['corr']:+.3f} fill={r['fill_rate']:.2f}")

        if excluded_signal:
            print(f"  EXCLUDED but signal > 0.15 ({len(excluded_signal)}):")
            for r in excluded_signal[:10]:
                print(f"    {r['col']:40s} corr={r['corr']:+.3f} fill={r['fill_rate']:.2f}")

        report[ptype] = {
            "n_rows": n,
            "n_cols_tested": len(results),
            "top_40": top_signal[:40],
            "unused_high_signal": unused_high_signal,
            "excluded_with_signal": excluded_signal,
        }

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n\nWrote: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
