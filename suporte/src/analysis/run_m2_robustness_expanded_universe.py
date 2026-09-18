"""Formalizes the M2 (principal) robustness battery for the narrow annual
debt note over the full expanded universe (185 companies, 2010-2025) --
previously run as an ad hoc script. Same three checks used throughout the
project: degenerate-similarity exclusion, raw (non-winsorized) BHAR, and
leave-one-company-out.

Usage:
    python -u -m src.analysis.run_m2_robustness_expanded_universe
"""
from __future__ import annotations

import warnings

import pandas as pd

from src.analysis.run_m0_m5_grid import M2, _fit_panel
from src.features.build_m0_m5_controls_extension import build_panel_extended

warnings.filterwarnings("ignore")

BHAR_CSV = "data/interim/poc/abnormal_returns_alpha_full_expanded_universe.csv"


def main() -> None:
    sample = pd.read_csv(BHAR_CSV)
    panel = build_panel_extended(sample)

    headline = _fit_panel(panel, "BHAR_ajustado", M2)
    print(f"M2 headline: beta={headline['beta']:+.4f}  p={headline['p']:.4f}  n={headline['n']}  "
          f"n_companies={headline['n_companies']}")

    degenerate = (panel["TextChange"] <= 0.001) | (panel["TextChange"] >= 0.999)
    clean = panel[~degenerate]
    r_clean = _fit_panel(clean, "BHAR_ajustado", M2)
    print(f"Excluding {int(degenerate.sum())} degenerate-similarity pairs: p={r_clean['p']:.4f}  n={r_clean['n']}")

    df_raw = panel.copy()
    df_raw["BHAR_ajustado"] = df_raw["BHAR_raw"]
    r_raw = _fit_panel(df_raw, "BHAR_ajustado", M2)
    print(f"Raw (non-winsorized) BHAR: p={r_raw['p']:.4f}")

    worst_p, worst_cd = -1.0, None
    for cd in panel["cd_cvm"].unique():
        sub = panel[panel["cd_cvm"] != cd]
        r = _fit_panel(sub, "BHAR_ajustado", M2)
        if pd.notna(r["p"]) and r["p"] > worst_p:
            worst_p, worst_cd = r["p"], cd
    print(f"Leave-one-company-out worst case: p={worst_p:.4f} (dropping cd_cvm={worst_cd})")


if __name__ == "__main__":
    main()
