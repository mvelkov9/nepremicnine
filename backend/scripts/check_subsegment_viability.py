"""Check fill rates and value distributions for candidate sub-segmentation keys."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CSV = ROOT / "data" / "raw" / "train_2020_2026.csv"

CANDIDATES = {
    "stanovanje": ["lega_v_stavbi", "ev_id_tip_stavbe", "ev_id_dr_dst", "ev_id_lega", "vrsta_dela_stavbe", "ev_id_konstrukcija", "floor"],
    "hisa":       ["ev_id_tip_stavbe", "ev_id_dr_dst", "vrsta_dela_stavbe", "ev_id_konstrukcija", "ev_id_lega"],
    "garaza":     ["vrsta_dela_stavbe", "lega_v_stavbi", "ev_id_lega", "ev_id_dr_dst", "ev_id_tip_stavbe"],
    "poslovni_prostor": ["vrsta_dela_stavbe", "ev_id_dr_dst", "lega_v_stavbi", "ev_id_tip_stavbe"],
    "industrijski": ["vrsta_dela_stavbe", "ev_id_dr_dst", "ev_id_tip_stavbe"],
    "turisticni":   ["vrsta_dela_stavbe", "ev_id_dr_dst", "ev_id_tip_stavbe"],
}

print(f"Loading {CSV}")
df = pd.read_csv(CSV, low_memory=False)
df = df[df["vrsta_kupoprodajnega_posla"].astype(str) == "1"].reset_index(drop=True)
df["_log_ppm2"] = np.log(
    pd.to_numeric(df["price_eur"], errors="coerce").clip(lower=1)
    / pd.to_numeric(df["size_m2"], errors="coerce").clip(lower=1)
)
df = df[df["_log_ppm2"].notna() & np.isfinite(df["_log_ppm2"])].reset_index(drop=True)
print(f"Total rows: {len(df)}\n")

for ptype, cols in CANDIDATES.items():
    sub = df[df["property_type"] == ptype]
    n = len(sub)
    if n < 100:
        continue
    print(f"=== {ptype} (n={n}) ===")
    for col in cols:
        if col not in sub.columns:
            continue
        values = sub[col].fillna("__missing__")
        n_valid = int((sub[col].notna()).sum())
        counts = values.value_counts()
        # Top 5 values
        top5 = counts.head(5)
        # Count viable buckets (n>=200)
        viable = counts[counts >= 200]
        viable_coverage = int(viable.sum())

        # Target spread: log_ppm2 median per value (top 5)
        medians = {}
        for v in top5.index[:5]:
            mask = values == v
            m = sub.loc[mask, "_log_ppm2"].median()
            if pd.notna(m):
                medians[str(v)[:20]] = float(m)

        ratio = max(medians.values()) / min(medians.values()) if medians and min(medians.values()) > 0 else 0.0
        spread_pct = (max(medians.values()) - min(medians.values())) * 100 if medians else 0

        print(f"  {col:25s} fill={n_valid/n:.2f} viable_buckets(n>=200)={len(viable)} viable_cov={viable_coverage}/{n} ({viable_coverage/n*100:.0f}%)")
        print(f"    top values: {dict(top5.head(5))}")
        if medians:
            print(f"    log_ppm2 medians: {medians}  spread={spread_pct:.0f}pp")
    print()
