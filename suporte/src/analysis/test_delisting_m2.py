"""Rebuilds the delisting/survivorship validity checks (Seção 5.3) using
M2's actual control set (Size, ROA, Leverage, Momentum, ΔROA, ΔLeverage,
ΔDebt -- src/analysis/run_m0_m5_grid.py's M2) instead of the older ad hoc
leverage/ROA/tamanho set, per user request: wherever a table shows a
single control specification, it should be M2 specifically, not an
unlabeled leftover from before the M0-M3 grade existed.

Two designs, matching what each check already used:
  1. Pair-level, clustered by company (narrow_annual, whole_notes,
     mgmt_report): is_dropped ~ TextChange + M2 controls.
  2. Company-level cross-sectional (risk_factors, n=1 row per company,
     TextChange and M2 controls averaged across each company's pairs):
     avoids the repeated-observations problem by construction, same
     design as the original Fatores de Risco check.

Usage:
    python -u -m src.analysis.test_delisting_m2
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

from src.analysis.run_m0_m5_grid import M2
from src.analysis.test_control_specifications import _delisting_group_map
from src.features.build_m0_m5_controls import build_fundamentals_panel

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"

PAIR_LEVEL_SOURCES = {
    "narrow_annual": "delisted_similarity_results_reliable.csv",
    "whole_notes": "full_notes_similarity_results_VERIFIED.csv",
    "mgmt_report": "mgmt_report_similarity_results.csv",
}


def run_pair_level() -> pd.DataFrame:
    group_map = _delisting_group_map()
    fund = build_fundamentals_panel()

    rows = []
    for name, fname in PAIR_LEVEL_SOURCES.items():
        df = pd.read_csv(POC / fname)
        if "group" not in df.columns:
            df = df.merge(group_map, on="cd_cvm", how="left")
        df["is_dropped"] = (df["group"] == "dropped_or_delisted").astype(int)
        df["TextChange"] = 1 - df["cosine_similarity"]
        panel = df.merge(fund, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "fiscal_year"], how="left")

        needed = ["cd_cvm", "is_dropped", "TextChange"] + M2
        d = panel.dropna(subset=needed)
        formula = "is_dropped ~ TextChange + " + " + ".join(M2)
        m = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["cd_cvm"]})
        rows.append({"fonte": name, "n": len(d), "n_empresas": d["cd_cvm"].nunique(),
                     "beta": m.params["TextChange"], "se": m.bse["TextChange"], "p": m.pvalues["TextChange"]})
    return pd.DataFrame(rows)


def run_risk_factors_cross_section() -> pd.DataFrame:
    group_map = _delisting_group_map()
    fund = build_fundamentals_panel()

    df = pd.read_csv(POC / "risk_factors_similarity_results.csv")
    df["TextChange"] = 1 - df["cosine_similarity"]
    panel = df.merge(fund, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "fiscal_year"], how="left")

    agg = panel.groupby("cd_cvm").agg({"TextChange": "mean", **{c: "mean" for c in M2}}).reset_index()
    agg = agg.merge(group_map, on="cd_cvm", how="left")
    agg["is_dropped"] = (agg["group"] == "dropped_or_delisted").astype(int)

    needed = ["is_dropped", "TextChange"] + M2
    d = agg.dropna(subset=needed)
    formula = "is_dropped ~ TextChange + " + " + ".join(M2)

    rows = []
    no_ctrl = smf.ols("is_dropped ~ TextChange", data=d).fit(cov_type="HC1")
    rows.append({"especificacao": "Sem controles", "n": len(d),
                 "beta": no_ctrl.params["TextChange"], "p": no_ctrl.pvalues["TextChange"]})

    ols = smf.ols(formula, data=d).fit(cov_type="HC1")
    rows.append({"especificacao": "Modelo principal (M2), MQO", "n": len(d),
                 "beta": ols.params["TextChange"], "p": ols.pvalues["TextChange"]})

    logit = smf.logit(formula, data=d).fit(disp=0)
    rows.append({"especificacao": "Modelo principal (M2), logit", "n": len(d),
                 "beta": logit.params["TextChange"], "p": logit.pvalues["TextChange"]})

    return pd.DataFrame(rows)


def main() -> None:
    pair_level = run_pair_level()
    print("=== Deslistamento, pair-level, M2 ===")
    print(pair_level.round(4).to_string(index=False))
    pair_level.to_csv(POC / "delisting_m2.csv", index=False)

    print("\n=== Fatores de Risco, transversal (n=1/empresa), M2 ===")
    cross = run_risk_factors_cross_section()
    print(cross.round(4).to_string(index=False))
    cross.to_csv(POC / "risk_factors_delisting_m2.csv", index=False)


if __name__ == "__main__":
    main()
