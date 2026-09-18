"""Curiosity check: reruns the H1 rigor progression for the narrow debt
note (annual) using Cohen, Malloy & Nguyen (2020)'s own similarity measure
(raw term-frequency cosine, no IDF -- see
src/processing/run_poc_cmn_style.py) instead of this project's TF-IDF
measure, at the 12-month and 18-month windows. Everything else (event
dates, prices, controls) is identical to the project's main tables --
only the similarity measure's construction changes.

Usage:
    python -u -m src.analysis.compare_cmn_style_similarity
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

RETURN_FILES = {"12m": "abnormal_returns_poc.csv", "18m": "abnormal_returns_poc_18m.csv"}


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year"})


def simple_corr(df: pd.DataFrame, sim_col: str) -> tuple[float, int]:
    have = df.dropna(subset=[sim_col, "abnormal_return"])
    if len(have) < 3:
        return float("nan"), len(have)
    _, p = stats.pearsonr(have[sim_col], have["abnormal_return"])
    return p, len(have)


def clustered_ols(df: pd.DataFrame, sim_col: str, controls: list[str]) -> tuple[float, int]:
    cols = ["abnormal_return", sim_col, "cd_cvm"] + controls
    have = df.dropna(subset=cols)
    if len(have) < 20 or have["cd_cvm"].nunique() < 5:
        return float("nan"), len(have)
    formula = f"abnormal_return ~ {sim_col}" + "".join(f" + {c}" for c in controls)
    model = smf.ols(formula, data=have).fit(cov_type="cluster", cov_kwds={"groups": have["cd_cvm"]})
    return model.pvalues[sim_col], len(have)


def fixed_effects(df: pd.DataFrame, sim_col: str) -> tuple[float, int]:
    cols = ["cd_cvm", "year_curr", "abnormal_return", sim_col] + CONTROLS
    have = df.dropna(subset=cols).drop_duplicates(subset=["cd_cvm", "year_curr"]).copy()
    if len(have) < 20 or have["cd_cvm"].nunique() < 5:
        return float("nan"), len(have)
    panel_df = have.set_index(["cd_cvm", "year_curr"])
    formula = f"abnormal_return ~ 1 + {sim_col} + " + " + ".join(CONTROLS) + " + EntityEffects + TimeEffects"
    mod = PanelOLS.from_formula(formula, data=panel_df)
    res = mod.fit(cov_type="clustered", cluster_entity=True)
    return res.pvalues[sim_col], int(res.nobs)


def run_one(returns_path: Path, sim: pd.DataFrame, sim_col: str) -> dict:
    ret = pd.read_csv(returns_path).drop(columns=["cosine_similarity"], errors="ignore")
    df = ret.merge(sim[["cd_cvm", "year_prev", "year_curr", sim_col]], on=["cd_cvm", "year_prev", "year_curr"], how="inner")
    df = df.merge(_load_controls(), left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "ctrl_year"], how="left")

    p_simple, n_simple = simple_corr(df, sim_col)
    p_nc, n_nc = clustered_ols(df, sim_col, [])
    p_c, n_c = clustered_ols(df, sim_col, CONTROLS)
    p_fe, n_fe = fixed_effects(df, sim_col)
    return {
        "n_simple": n_simple, "p_simple": p_simple,
        "n_nocontrols": n_nc, "p_nocontrols": p_nc,
        "n_controls": n_c, "p_controls": p_c,
        "n_fe": n_fe, "p_fe": p_fe,
    }


def run_tfidf_one(returns_path: Path) -> dict:
    """The TF-IDF arm needs no re-merge at all -- abnormal_returns_poc*.csv
    already carries the project's correct, deduplicated cosine_similarity
    column from compute_abnormal_returns.py. Re-deriving it from the raw
    similarity_results.csv + delisted_similarity_results.csv files (as the
    CMN arm must, since that column doesn't exist there yet) double-counts
    the ~508 "stayed" pairs that appear in both raw files."""
    df = pd.read_csv(returns_path)
    df = df.merge(_load_controls(), left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "ctrl_year"], how="left")
    p_simple, n_simple = simple_corr(df, "cosine_similarity")
    p_nc, n_nc = clustered_ols(df, "cosine_similarity", [])
    p_c, n_c = clustered_ols(df, "cosine_similarity", CONTROLS)
    p_fe, n_fe = fixed_effects(df, "cosine_similarity")
    return {
        "n_simple": n_simple, "p_simple": p_simple,
        "n_nocontrols": n_nc, "p_nocontrols": p_nc,
        "n_controls": n_c, "p_controls": p_c,
        "n_fe": n_fe, "p_fe": p_fe,
    }


def main() -> None:
    sim_cmn = pd.read_csv(POC / "similarity_results_cmn_style.csv")

    rows = []
    for window, fname in RETURN_FILES.items():
        r_cmn = run_one(POC / fname, sim_cmn, "cosine_similarity_cmn")
        rows.append({"method": "CMN (TF bruto, sem IDF)", "window": window, **r_cmn})
        r_tfidf = run_tfidf_one(POC / fname)
        rows.append({"method": "TF-IDF (projeto)", "window": window, **r_tfidf})

    out = pd.DataFrame(rows)
    out_path = POC / "cmn_style_vs_tfidf_comparison.csv"
    out.to_csv(out_path, index=False)

    pd.set_option("display.width", 200)
    print(out[["method", "window", "n_simple", "p_simple", "n_nocontrols", "p_nocontrols",
               "n_controls", "p_controls", "n_fe", "p_fe"]].round(4).to_string(index=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
