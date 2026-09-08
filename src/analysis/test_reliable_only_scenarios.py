"""Two follow-up robustness checks requested directly, run on top of the
new default methodology (narrow-note results restricted to font_heading/
font_heading pairs, src/analysis/build_reliable_only_datasets.py):

  1. Drop ROA from the control set (leverage + past_12m_return only).
  2. Drop pairs that span more than one fiscal year (year_curr - year_prev
     != 1) -- the silently-bridged-gap issue found earlier
     (src/analysis/test_year_gap_robustness.py), now checked against the
     reliable-only base instead of the full sample.

Covers H1 return (narrow_annual, narrow_quarterly), H1 delisting
(narrow_annual), and H2 revision (narrow_annual, narrow_quarterly) -- the
same scope as the reliable-only switch itself.

Usage:
    python -u -m src.analysis.test_reliable_only_scenarios
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

WITH_ROA = ["leverage", "roa", "past_12m_return"]
NO_ROA = ["leverage", "past_12m_return"]


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year",
    })


def rigor_progression(df: pd.DataFrame, outcome: str, ctrl_year_col: str, controls: list[str], with_fe: bool) -> dict:
    ctrl = _load_controls()
    d = df.dropna(subset=[outcome, "cosine_similarity"]).copy()
    n_simple = len(d)
    p_simple = stats.pearsonr(d["cosine_similarity"], d[outcome])[1] if n_simple >= 3 else np.nan

    d_nc = d.dropna(subset=["cd_cvm"])
    if d_nc["cd_cvm"].nunique() >= 3:
        mod_nc = smf.ols(f"{outcome} ~ cosine_similarity", data=d_nc).fit(
            cov_type="cluster", cov_kwds={"groups": d_nc["cd_cvm"]})
        p_nc, n_nc = mod_nc.pvalues["cosine_similarity"], len(d_nc)
    else:
        p_nc, n_nc = np.nan, len(d_nc)

    if set(controls).issubset(d.columns):
        d_c = d.copy()
        if "ctrl_year" not in d_c.columns:
            d_c["ctrl_year"] = d_c[ctrl_year_col]
    else:
        d_c = d.merge(ctrl, left_on=["cd_cvm", ctrl_year_col], right_on=["cd_cvm", "ctrl_year"], how="left")
    d_c = d_c.dropna(subset=["cd_cvm"] + controls)
    if d_c["cd_cvm"].nunique() >= 3 and controls:
        formula = f"{outcome} ~ cosine_similarity + " + " + ".join(controls)
        mod_c = smf.ols(formula, data=d_c).fit(cov_type="cluster", cov_kwds={"groups": d_c["cd_cvm"]})
        p_c, n_c = mod_c.pvalues["cosine_similarity"], len(d_c)
    else:
        p_c, n_c = np.nan, len(d_c)

    p_fe, n_fe = np.nan, np.nan
    if with_fe:
        d_fe = d_c.dropna(subset=["ctrl_year"]).drop_duplicates(subset=["cd_cvm", "ctrl_year"])
        if d_fe["cd_cvm"].nunique() >= 5 and len(d_fe) >= 20:
            panel_df = d_fe.set_index(["cd_cvm", "ctrl_year"])
            formula_fe = f"{outcome} ~ 1 + cosine_similarity + " + " + ".join(controls) + " + EntityEffects + TimeEffects"
            try:
                mod_fe = PanelOLS.from_formula(formula_fe, data=panel_df).fit(cov_type="clustered", cluster_entity=True)
                p_fe, n_fe = mod_fe.pvalues["cosine_similarity"], int(mod_fe.nobs)
            except Exception:
                pass

    return {"n_simples": n_simple, "p_simples": p_simple, "n_agrup": n_nc, "p_agrup_sc": p_nc,
            "n_ctrl": n_c, "p_agrup_cc": p_c, "n_fe": n_fe, "p_ef_fixos": p_fe}


def main() -> None:
    rows = []

    return_sources = {
        "narrow_annual": (POC / "abnormal_returns_poc_reliable.csv", "year_curr"),
        "narrow_quarterly": (POC / "abnormal_returns_itr_reliable.csv", "quarter_curr"),
    }
    for name, (path, ycol) in return_sources.items():
        df = pd.read_csv(path)
        scenarios = [("base (c/ ROA)", df, WITH_ROA), ("sem ROA", df, NO_ROA)]
        if ycol == "quarter_curr":
            df["ctrl_year_col"] = df["quarter_curr"].str[:4].astype(int)
            ycol_use = "ctrl_year_col"
            # "consecutive years" doesn't map cleanly onto a quarter-indexed
            # series (a year-over-year gap concept was only ever defined for
            # the annual sources) -- skip rather than force an ill-fitting filter.
        else:
            ycol_use = ycol
            gap = df["year_curr"] - df["year_prev"]
            scenarios.append(("sem pares com salto de ano", df[gap == 1], WITH_ROA))

        for scen_label, subset, controls in scenarios:
            r = rigor_progression(subset, "abnormal_return", ycol_use, controls, with_fe=True)
            rows.append({"família": "H1_retorno", "fonte": name, "cenário": scen_label, **r})

    df = pd.read_csv(POC / "delisted_similarity_results_reliable.csv")
    df["is_dropped"] = (df["group"] == "dropped_or_delisted").astype(int)
    gap = df["year_curr"] - df["year_prev"]
    for scen_label, subset, controls in [
        ("base (c/ ROA)", df, WITH_ROA),
        ("sem ROA", df, NO_ROA),
        ("sem pares com salto de ano", df[gap == 1], WITH_ROA),
    ]:
        r = rigor_progression(subset, "is_dropped", "year_curr", controls, with_fe=False)
        rows.append({"família": "H1_delisting", "fonte": "narrow_annual", "cenário": scen_label, **r})

    h2_sources = {
        "narrow_annual": POC / "h2_eps_revision_narrow_annual_all_reliable.csv",
        "narrow_quarterly": POC / "h2_eps_revision_narrow_quarterly_all_reliable.csv",
    }
    for name, path in h2_sources.items():
        df = pd.read_csv(path)
        scenarios = [("base (c/ ROA)", df, WITH_ROA), ("sem ROA", df, NO_ROA)]
        ycol = "year_curr" if "year_curr" in df.columns else None
        if ycol is None:
            df["ctrl_year_col"] = df["quarter_curr"].str[:4].astype(int)
            ycol = "ctrl_year_col"
            # quarter-indexed: no well-defined "consecutive years" gap filter here
        else:
            gap = df["year_curr"] - df["year_prev"]
            scenarios.append(("sem pares com salto de ano", df[gap == 1], WITH_ROA))
        for scen_label, subset, controls in scenarios:
            r = rigor_progression(subset, "revision_pct", ycol, controls, with_fe=False)
            rows.append({"família": "H2_revisão", "fonte": name, "cenário": scen_label, **r})

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(out.round(4).to_string(index=False))
    out_path = POC / "reliable_only_extra_scenarios.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
