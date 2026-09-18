"""Runs the same four-stage H1 rigor progression used throughout this
project (simple correlation -> clustered OLS, no controls -> clustered OLS,
with controls -> company+year fixed effects) on both the 12-month and the
3-month abnormal-return window, for every annual text source, so the two
windows can be compared under identical code.

Controls are leverage/roa/past_12m_return (size excluded, per the
project's own established decision -- see
reports/control_specification_test.md and Sec. 3.5 of the thesis).

Usage:
    python -u -m src.analysis.compare_return_windows
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from linearmodels.panel import PanelOLS

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

CONTROLS = ["leverage", "roa", "past_12m_return"]

SCENARIOS = {
    "narrow_annual": {
        "3d": "abnormal_returns_poc_3d.csv", "3m": "abnormal_returns_poc_3m.csv",
        "12m": "abnormal_returns_poc.csv", "18m": "abnormal_returns_poc_18m.csv",
    },
    "whole_notes": {
        "3d": "abnormal_returns_full_notes_VERIFIED_3d.csv", "3m": "abnormal_returns_full_notes_VERIFIED_3m.csv",
        "12m": "abnormal_returns_full_notes_VERIFIED.csv", "18m": "abnormal_returns_full_notes_VERIFIED_18m.csv",
    },
    "mgmt_report": {
        "3d": "abnormal_returns_mgmt_report_3d.csv", "3m": "abnormal_returns_mgmt_report_3m.csv",
        "12m": "abnormal_returns_mgmt_report.csv", "18m": "abnormal_returns_mgmt_report_18m.csv",
    },
    "risk_factors": {
        "3d": "abnormal_returns_risk_factors_3d.csv", "3m": "abnormal_returns_risk_factors_3m.csv",
        "12m": "abnormal_returns_risk_factors.csv", "18m": "abnormal_returns_risk_factors_18m.csv",
    },
}


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year",
    })


def simple_corr(df: pd.DataFrame) -> tuple[float, int]:
    have = df.dropna(subset=["cosine_similarity", "abnormal_return"])
    if len(have) < 3:
        return float("nan"), len(have)
    _, p = stats.pearsonr(have["cosine_similarity"], have["abnormal_return"])
    return p, len(have)


def clustered_ols(df: pd.DataFrame, controls: list[str]) -> tuple[float, int]:
    cols = ["abnormal_return", "cosine_similarity", "cd_cvm"] + controls
    have = df.dropna(subset=cols)
    if len(have) < 20 or have["cd_cvm"].nunique() < 5:
        return float("nan"), len(have)
    formula = "abnormal_return ~ cosine_similarity" + "".join(f" + {c}" for c in controls)
    model = smf.ols(formula, data=have).fit(cov_type="cluster", cov_kwds={"groups": have["cd_cvm"]})
    return model.pvalues["cosine_similarity"], len(have)


def fixed_effects(df: pd.DataFrame) -> tuple[float, int]:
    cols = ["cd_cvm", "year_curr", "abnormal_return", "cosine_similarity"] + CONTROLS
    have = df.dropna(subset=cols).drop_duplicates(subset=["cd_cvm", "year_curr"]).copy()
    if len(have) < 20 or have["cd_cvm"].nunique() < 5:
        return float("nan"), len(have)
    panel_df = have.set_index(["cd_cvm", "year_curr"])
    formula = "abnormal_return ~ 1 + cosine_similarity + " + " + ".join(CONTROLS) + " + EntityEffects + TimeEffects"
    mod = PanelOLS.from_formula(formula, data=panel_df)
    res = mod.fit(cov_type="clustered", cluster_entity=True)
    return res.pvalues["cosine_similarity"], int(res.nobs)


def run_one(path: Path) -> dict:
    df = pd.read_csv(path)
    df = _merge_controls(df)
    p_simple, n_simple = simple_corr(df)
    p_nc, n_nc = clustered_ols(df, [])
    p_c, n_c = clustered_ols(df, CONTROLS)
    p_fe, n_fe = fixed_effects(df)
    return {
        "n_simple": n_simple, "p_simple": p_simple,
        "n_nocontrols": n_nc, "p_nocontrols": p_nc,
        "n_controls": n_c, "p_controls": p_c,
        "n_fe": n_fe, "p_fe": p_fe,
    }


def _merge_controls(df: pd.DataFrame) -> pd.DataFrame:
    controls = _load_controls()
    return df.merge(controls, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "ctrl_year"], how="left")


def main() -> None:
    rows = []
    for name, windows in SCENARIOS.items():
        for window_label, fname in windows.items():
            r = run_one(POC / fname)
            rows.append({"scenario": name, "window": window_label, **r})

    out = pd.DataFrame(rows)
    out_path = POC / "return_window_comparison.csv"
    out.to_csv(out_path, index=False)

    pd.set_option("display.width", 200)
    print(out[["scenario", "window", "n_simple", "p_simple", "n_nocontrols", "p_nocontrols",
               "n_controls", "p_controls", "n_fe", "p_fe"]].round(4).to_string(index=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
