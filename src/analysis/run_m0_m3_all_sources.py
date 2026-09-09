"""Extends the M0-M3 control grid (locked in as the confirmatory core --
M4/M5 dropped per user decision) to all five text sources, using BHAR
ajustado (winsorized alpha/residual abnormal return) as the sole
dependent variable, now the project's chosen metric.

TextChange = 1 - cosine_similarity throughout (feedback item 2.6).

Reuses _fit_panel from run_m0_m5_grid.py and build_panel from
src/features/build_m0_m5_controls.py; narrow_quarterly needs a
year_curr column derived from quarter_curr before the annual
fundamentals (control_variables.csv, debt_line_item.csv) can be merged.

Usage:
    python -u -m src.analysis.run_m0_m3_all_sources
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from src.analysis.run_m0_m5_grid import M0, M1, M2, M3, WINSOR_HI, WINSOR_LO, _fit_panel
from src.features.build_m0_m5_controls import build_panel

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"

SOURCES = {
    "narrow_annual": "abnormal_returns_alpha_narrow_annual.csv",
    "narrow_quarterly": "abnormal_returns_alpha_narrow_quarterly.csv",
    "whole_notes": "abnormal_returns_alpha_whole_notes.csv",
    "mgmt_report": "abnormal_returns_alpha_mgmt_report.csv",
    "risk_factors": "abnormal_returns_alpha_risk_factors.csv",
}

MODELS = [("M0", M0, "diagnóstico"), ("M1", M1, "baseline"), ("M2", M2, "PRINCIPAL"),
          ("M3", M3, "robustez econômica")]


def prepare(fname: str) -> pd.DataFrame:
    df = pd.read_csv(POC / fname)
    if "year_curr" not in df.columns:
        df["year_curr"] = df["quarter_curr"].str[:4].astype(int)
    df = build_panel(df)
    df["TextChange"] = 1 - df["cosine_similarity"]
    lo, hi = df["alpha_ar_compound"].quantile([WINSOR_LO, WINSOR_HI])
    df["alpha_ar_compound_winsorized"] = df["alpha_ar_compound"].clip(lo, hi)
    return df


def main() -> None:
    rows = []
    for name, fname in SOURCES.items():
        print(f"{name} ({fname})...")
        df = prepare(fname)
        for m_name, controls, status in MODELS:
            r = _fit_panel(df, "alpha_ar_compound_winsorized", controls)
            rows.append({"Fonte": name, "Modelo": m_name, "Status": status, **r})

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    for name in SOURCES:
        print(f"\n=== {name} ===")
        sub = out[out["Fonte"] == name].drop(columns=["Fonte"])
        print(sub.round(4).to_string(index=False))

    out_path = POC / "m0_m3_all_sources_results.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
