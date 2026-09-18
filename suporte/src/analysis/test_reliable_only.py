"""Direct empirical answer to a specific question: does restricting H1/H2
to pairs where BOTH years have reliable extraction (diagnostic ==
"font_heading") change any conclusion, versus the current default of using
every computable pair (font_heading + regex_only)?

Only narrow_annual and narrow_quarterly carry this diagnostic at all -- it
comes from the font-size/bold heading heuristic used to isolate the debt
note inside a larger filing (locate_note_section.py). The other three
sources (whole_notes, mgmt_report, risk_factors) are acquired as either the
entire document or an already-isolated PDF attachment, so the
font_heading/regex_only distinction does not apply to them and they are
not part of this check.

Reruns the same rigor progression used throughout the project -- simple
correlation, clustered OLS without controls, clustered OLS with controls,
and (for the return outcome only) company+year fixed effects -- for H1
return, H1 delisting, and H2 revision, under "todos os pares" (current)
vs. "apenas font_heading/font_heading".

Usage:
    python -u -m src.analysis.test_reliable_only
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from linearmodels.panel import PanelOLS
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

CONTROLS = ["leverage", "roa", "past_12m_return"]


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year",
    })


def _both_reliable(df: pd.DataFrame) -> pd.Series:
    return (df["diagnostic_prev"] == "font_heading") & (df["diagnostic_curr"] == "font_heading")


def rigor_progression(df: pd.DataFrame, outcome: str, ctrl_year_col: str, with_fe: bool) -> dict:
    ctrl = _load_controls()
    d = df.dropna(subset=[outcome, "cosine_similarity"]).copy()
    n_simple = len(d)
    if n_simple >= 3:
        _, p_simple = stats.pearsonr(d["cosine_similarity"], d[outcome])
    else:
        p_simple = np.nan

    d_nc = d.dropna(subset=["cd_cvm"])
    if d_nc["cd_cvm"].nunique() >= 3:
        mod_nc = smf.ols(f"{outcome} ~ cosine_similarity", data=d_nc).fit(
            cov_type="cluster", cov_kwds={"groups": d_nc["cd_cvm"]})
        p_nc, n_nc = mod_nc.pvalues["cosine_similarity"], len(d_nc)
    else:
        p_nc, n_nc = np.nan, len(d_nc)

    if set(CONTROLS).issubset(d.columns):
        d_c = d.copy()
        if "ctrl_year" not in d_c.columns:
            d_c["ctrl_year"] = d_c[ctrl_year_col]
    else:
        d_c = d.merge(ctrl, left_on=["cd_cvm", ctrl_year_col], right_on=["cd_cvm", "ctrl_year"], how="left")
    d_c = d_c.dropna(subset=["cd_cvm"] + CONTROLS)
    if d_c["cd_cvm"].nunique() >= 3:
        formula = f"{outcome} ~ cosine_similarity + " + " + ".join(CONTROLS)
        mod_c = smf.ols(formula, data=d_c).fit(cov_type="cluster", cov_kwds={"groups": d_c["cd_cvm"]})
        p_c, n_c = mod_c.pvalues["cosine_similarity"], len(d_c)
    else:
        p_c, n_c = np.nan, len(d_c)

    p_fe, n_fe = np.nan, np.nan
    if with_fe:
        d_fe = d_c.dropna(subset=["ctrl_year"]).drop_duplicates(subset=["cd_cvm", "ctrl_year"])
        if d_fe["cd_cvm"].nunique() >= 5 and len(d_fe) >= 20:
            panel_df = d_fe.set_index(["cd_cvm", "ctrl_year"])
            formula_fe = f"{outcome} ~ 1 + cosine_similarity + " + " + ".join(CONTROLS) + " + EntityEffects + TimeEffects"
            try:
                mod_fe = PanelOLS.from_formula(formula_fe, data=panel_df).fit(cov_type="clustered", cluster_entity=True)
                p_fe, n_fe = mod_fe.pvalues["cosine_similarity"], int(mod_fe.nobs)
            except Exception:
                pass

    return {"n_simples": n_simple, "p_simples": p_simple, "n_agrup": n_nc, "p_agrup_sc": p_nc,
            "n_ctrl": n_c, "p_agrup_cc": p_c, "n_fe": n_fe, "p_ef_fixos": p_fe}


def main() -> None:
    rows = []

    # ---- H1 return: narrow_annual, narrow_quarterly ----
    return_sources = {
        "narrow_annual": (POC / "abnormal_returns_poc.csv", "year_curr"),
        "narrow_quarterly": (POC / "abnormal_returns_itr.csv", "quarter_curr"),
    }
    for name, (path, ycol) in return_sources.items():
        df = pd.read_csv(path)
        if ycol == "quarter_curr":
            df["ctrl_year_col"] = df["quarter_curr"].str[:4].astype(int)
            ycol_use = "ctrl_year_col"
        else:
            ycol_use = ycol
        for tag, subset in [("todos os pares", df), ("apenas font_heading", df[_both_reliable(df)])]:
            r = rigor_progression(subset, "abnormal_return", ycol_use, with_fe=True)
            rows.append({"família": "H1_retorno", "fonte": name, "amostra": tag, **r})

    # ---- H1 delisting: narrow_annual only ----
    df = pd.read_csv(POC / "delisted_similarity_results.csv")
    df["is_dropped"] = (df["group"] == "dropped_or_delisted").astype(int)
    for tag, subset in [("todos os pares", df), ("apenas font_heading", df[_both_reliable(df)])]:
        r = rigor_progression(subset, "is_dropped", "year_curr", with_fe=False)
        rows.append({"família": "H1_delisting", "fonte": "narrow_annual", "amostra": tag, **r})

    # ---- H2 revision: narrow_annual, narrow_quarterly ----
    h2_sources = {
        "narrow_annual": POC / "h2_eps_revision_narrow_annual_all.csv",
        "narrow_quarterly": POC / "h2_eps_revision_narrow_quarterly_all.csv",
    }
    for name, path in h2_sources.items():
        df = pd.read_csv(path)
        ycol = "year_curr" if "year_curr" in df.columns else "ctrl_year"
        if ycol not in df.columns and "quarter_curr" in df.columns:
            df["ctrl_year_col"] = df["quarter_curr"].str[:4].astype(int)
            ycol = "ctrl_year_col"
        for tag, subset in [("todos os pares", df), ("apenas font_heading", df[_both_reliable(df)])]:
            r = rigor_progression(subset, "revision_pct", ycol, with_fe=False)
            rows.append({"família": "H2_revisão", "fonte": name, "amostra": tag, **r})

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(out.round(4).to_string(index=False))
    out_path = POC / "reliable_only_comparison.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
