"""New methodology rule (2026-09): for the narrow debt note (the two
sources that carry a font_heading/regex_only extraction diagnostic --
annual and quarterly), all thesis results now use only pairs where BOTH
years have diagnostic == "font_heading". Sec 5.1 already showed this
restricted sample behaves better (Figura 5.2), and the reliable-only rerun
(src/analysis/test_reliable_only.py) showed no H1/H2 conclusion changes
from restricting -- this makes that stricter sample the default, not just
a side comparison.

This does NOT apply to whole_notes, mgmt_report, or risk_factors: those
three sources are acquired as an entire document or an already-isolated
PDF attachment, with no font-heading/regex heuristic involved, so the
diagnostic column doesn't exist for them and nothing changes.

Builds one filtered "_reliable" copy of each file that feeds a narrow-note
number in the thesis. The original ("all pairs") files are left untouched
-- Sec 5.1's own before/after comparison (Figura 5.2) needs both versions
to make its point, and any future robustness check may want the full
sample too.

Usage:
    python -u -m src.analysis.build_reliable_only_datasets
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"

FILES = [
    "abnormal_returns_poc.csv",
    "abnormal_returns_poc_18m.csv",
    "abnormal_returns_poc_3m.csv",
    "abnormal_returns_poc_3d.csv",
    "abnormal_returns_itr.csv",
    "delisted_similarity_results.csv",
    "itr_similarity_results.csv",
    "h2_eps_revision_narrow_annual_all.csv",
    "h2_eps_revision_narrow_quarterly_all.csv",
]


def main() -> None:
    for fname in FILES:
        path = POC / fname
        if not path.exists():
            print(f"skip (not found): {fname}")
            continue
        df = pd.read_csv(path)
        if "diagnostic_prev" not in df.columns or "diagnostic_curr" not in df.columns:
            print(f"skip (no diagnostic columns): {fname}")
            continue
        reliable = df[(df["diagnostic_prev"] == "font_heading") & (df["diagnostic_curr"] == "font_heading")].copy()
        out_path = POC / fname.replace(".csv", "_reliable.csv")
        reliable.to_csv(out_path, index=False)
        print(f"{fname}: {len(df)} -> {len(reliable)} pares ({100*len(reliable)/len(df):.1f}%)  ->  {out_path.name}")


if __name__ == "__main__":
    main()
