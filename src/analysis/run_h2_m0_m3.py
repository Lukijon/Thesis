"""Extends the M0-M3 control grid (src/analysis/run_m0_m5_grid.py,
src/features/build_m0_m5_controls.py) to H2 (EPS consensus revision),
matching the treatment already applied to H1. TextChange = 1 -
cosine_similarity throughout (feedback item 2.6); revision_pct is the
outcome (Seção h2_metodologia), unaffected by the BHAR/alpha change since
it isn't derived from stock returns at all -- what changes here is only
the control set (M0-M3 instead of the old leverage/ROA/past_return-only
set) and the TextChange relabeling.

H2's data files use "event_date" instead of "window_start" for the
pre-filing reference date; the two are identical in content (both are the
DFP/ITR disclosure date), so it's renamed before reuse.

Sources: narrow_annual, narrow_quarterly, whole_notes, mgmt_report (no
risk_factors -- H2 was never built for that source).

Usage:
    python -u -m src.analysis.run_h2_m0_m3
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from src.analysis.run_m0_m5_grid import M0, M1, M2, M3, _fit_panel
from src.features.build_m0_m5_controls import build_panel

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"

SOURCES = {
    "narrow_annual": "h2_eps_revision_narrow_annual_all_reliable.csv",
    "narrow_quarterly": "h2_eps_revision_narrow_quarterly_all_reliable.csv",
    "whole_notes": "h2_eps_revision_whole_notes_all.csv",
    "mgmt_report": "h2_eps_revision_mgmt_report_all.csv",
}

MODELS = [("M0", M0, "diagnóstico"), ("M1", M1, "baseline"), ("M2", M2, "PRINCIPAL"),
          ("M3", M3, "robustez econômica")]


def prepare(fname: str) -> pd.DataFrame:
    df = pd.read_csv(POC / fname)
    df = df.rename(columns={"event_date": "window_start"})
    if "year_curr" not in df.columns:
        df["year_curr"] = df["quarter_curr"].str[:4].astype(int)
    # build_panel merges fundamentals on (cd_cvm, year_curr) via
    # control_variables.csv/debt_line_item.csv, dropping the pre-existing
    # leverage/roa/etc. columns already present in these H2 files to avoid
    # merge-suffix collisions.
    df = df.drop(columns=[c for c in ["leverage", "roa", "ln_total_assets", "past_12m_return"] if c in df.columns])
    df = build_panel(df)
    df["TextChange"] = 1 - df["cosine_similarity"]
    return df


def main() -> None:
    rows = []
    for name, fname in SOURCES.items():
        print(f"{name} ({fname})...")
        df = prepare(fname)
        for m_name, controls, status in MODELS:
            r = _fit_panel(df, "revision_pct", controls)
            rows.append({"Fonte": name, "Modelo": m_name, "Status": status, **r})

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    for name in SOURCES:
        print(f"\n=== {name} ===")
        sub = out[out["Fonte"] == name].drop(columns=["Fonte"])
        print(sub.round(4).to_string(index=False))

    out_path = POC / "h2_m0_m3_results.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
