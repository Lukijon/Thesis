"""Runs the thesis's own M0-M3 control grid (run_m0_m5_grid.py's M0/M1/M2/M3
constants -- identical control lists, same _fit_panel: TextChange + company/
year fixed effects, clustered by company) over the full expanded universe
(185 companies, 2010-2025) for the narrow annual debt note, using the
round-7-hardened extraction and the extended control panel
(build_m0_m5_controls_extension.py).

Directly comparable, model-for-model, to Tabela 5.2's "Nota de dívida
(anual)" rows in the thesis (n=437/432/432/418 for M0/M1/M2/M3, on the
original 111-company/2015-2024 scope) -- this is the same test, same
control definitions, just run over the bigger sample.

Usage:
    python -u -m src.analysis.run_m0_m3_expanded_universe
"""
from __future__ import annotations

import warnings

import pandas as pd

from src.analysis.run_m0_m5_grid import M0, M1, M2, M3, _fit_panel
from src.features.build_m0_m5_controls_extension import build_panel_extended

warnings.filterwarnings("ignore")

BHAR_CSV = "data/interim/poc/abnormal_returns_alpha_full_expanded_universe.csv"
MODELS = [("M0", M0, "diagnóstico"), ("M1", M1, "baseline"), ("M2", M2, "PRINCIPAL"), ("M3", M3, "robustez econômica")]


def main() -> None:
    sample = pd.read_csv(BHAR_CSV)
    panel = build_panel_extended(sample)

    print("=== M0-M3, nota de dívida anual, universo expandido (185 empresas, 2010-2025) ===\n")
    rows = []
    for name, controls, status in MODELS:
        r = _fit_panel(panel, "BHAR_ajustado", controls)
        rows.append({"Modelo": name, "Status": status, **r})
        print(f"{name} ({status}): n={r['n']:4d}  n_empresas={r['n_companies']:3d}  "
              f"beta={r['beta']:+.4f}  se={r['se']:.4f}  p={r['p']:.4f}" if pd.notna(r["p"]) else
              f"{name} ({status}): n={r['n']:4d} -- insuficiente para estimar")

    out = pd.DataFrame(rows)
    out_path = "data/interim/poc/m0_m3_expanded_universe_results.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
