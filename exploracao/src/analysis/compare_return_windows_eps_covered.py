"""Sanity-check variant of compare_return_windows.py: same 4-stage rigor
progression, but restricted to companies that have at least one analyst
EPS consensus observation in data/raw/analysts/eps_consensus_bloomberg.csv
(i.e. the same company universe usable for H2), and only the 12-month and
18-month windows (dropping 3-day/3-month, already shown not to change the
conclusion -- see compare_return_windows.py's results).

Usage:
    python -u -m src.analysis.compare_return_windows_eps_covered
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from linearmodels.panel import PanelOLS

from src.analysis.compute_abnormal_returns import build_ticker_map
from src.analysis.compute_eps_revisions import load_eps_panel

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

CONTROLS = ["leverage", "roa", "past_12m_return"]

SCENARIOS = {
    "narrow_annual": {"12m": "abnormal_returns_poc.csv", "18m": "abnormal_returns_poc_18m.csv"},
    "whole_notes":   {"12m": "abnormal_returns_full_notes_VERIFIED.csv", "18m": "abnormal_returns_full_notes_VERIFIED_18m.csv"},
    "mgmt_report":   {"12m": "abnormal_returns_mgmt_report.csv", "18m": "abnormal_returns_mgmt_report_18m.csv"},
    "risk_factors":  {"12m": "abnormal_returns_risk_factors.csv", "18m": "abnormal_returns_risk_factors_18m.csv"},
}


def _eps_covered_cd_cvm() -> set[int]:
    ticker_map = build_ticker_map()
    eps_panel = load_eps_panel()
    tickers_with_eps = set(eps_panel["ticker"].unique())
    return set(ticker_map.loc[ticker_map["ticker"].isin(tickers_with_eps), "CD_CVM"])


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


def _merge_controls(df: pd.DataFrame) -> pd.DataFrame:
    controls = _load_controls()
    return df.merge(controls, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "ctrl_year"], how="left")


def run_one(path: Path, eps_covered: set[int]) -> dict:
    df = pd.read_csv(path)
    df = df[df["cd_cvm"].isin(eps_covered)]
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


def main() -> None:
    eps_covered = _eps_covered_cd_cvm()
    print(f"{len(eps_covered)} companies with at least one EPS consensus observation\n")

    rows = []
    for name, windows in SCENARIOS.items():
        for window_label, fname in windows.items():
            r = run_one(POC / fname, eps_covered)
            rows.append({"scenario": name, "window": window_label, **r})

    out = pd.DataFrame(rows)
    out_path = POC / "return_window_comparison_eps_covered.csv"
    out.to_csv(out_path, index=False)

    pd.set_option("display.width", 200)
    print(out[["scenario", "window", "n_simple", "p_simple", "n_nocontrols", "p_nocontrols",
               "n_controls", "p_controls", "n_fe", "p_fe"]].round(4).to_string(index=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
