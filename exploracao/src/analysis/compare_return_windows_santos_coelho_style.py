"""Sanity check: what if this project's own data were analyzed with the
same (looser) panel methodology as Santos & Coelho (2018) -- the closest
Brazilian paper to this topic (risk-factor disclosure vs. market value) --
instead of this project's own two-way company+year fixed-effects standard?

Santos & Coelho's design, confirmed by reading the actual paper:
  - Single-dimension company effect only (no year effects).
  - Chosen per regression via a Hausman test (fixed effects vs. random
    effects), not a fixed a priori commitment to the stricter option.
  - Heteroskedasticity-robust standard errors, not firm-clustered.
  - A 3-year panel (2012-2014, n=300) -- which they flag themselves as a
    limitation ("painel curto", can produce unstable FE-vs-RE differences).

This script applies the same *style* of test (company-only effect,
Hausman-selected, robust SEs, no clustering) to this project's 12-month and
18-month abnormal-return data, which has a decade-long panel (2015-2024)
instead of 3 years -- to see whether the longer panel plus their looser
effect-selection procedure changes anything.

Usage:
    python -u -m src.analysis.compare_return_windows_santos_coelho_style
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from linearmodels.panel import PanelOLS, RandomEffects

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


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr"})


def _prep_panel(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["cd_cvm", "year_curr", "abnormal_return", "cosine_similarity"] + CONTROLS
    d = df.dropna(subset=cols).drop_duplicates(subset=["cd_cvm", "year_curr"]).copy()
    return d.set_index(["cd_cvm", "year_curr"])


def hausman(fe_res, re_res) -> tuple[float, float]:
    """Standard Hausman specification test comparing FE vs. RE coefficient
    vectors (excluding the intercept, which RE has and FE doesn't).
    Returns (chi2 statistic, p-value). A significant (low p) result means
    the two estimators diverge systematically -- FE is preferred. A
    non-significant result means RE isn't rejected (the model Santos &
    Coelho would keep, since RE is more efficient when valid)."""
    common = [p for p in fe_res.params.index if p in re_res.params.index]
    b_fe = fe_res.params[common].values
    b_re = re_res.params[common].values
    v_fe = fe_res.cov.loc[common, common].values
    v_re = re_res.cov.loc[common, common].values
    diff = b_fe - b_re
    var_diff = v_fe - v_re
    try:
        stat = float(diff @ np.linalg.inv(var_diff) @ diff)
    except np.linalg.LinAlgError:
        stat = float(diff @ np.linalg.pinv(var_diff) @ diff)
    stat = abs(stat)  # guard against numerical noise producing a tiny negative
    dof = len(common)
    p = float(1 - scipy_stats.chi2.cdf(stat, dof))
    return stat, p


def run_one(path: Path) -> dict:
    df = pd.read_csv(path)
    df = df.merge(_load_controls(), on=["cd_cvm", "year_curr"], how="left")
    panel_df = _prep_panel(df)
    if panel_df.index.get_level_values(0).nunique() < 5 or len(panel_df) < 20:
        return {"n": len(panel_df), "n_companies": panel_df.index.get_level_values(0).nunique(),
                "fe_coef": np.nan, "fe_p": np.nan, "re_coef": np.nan, "re_p": np.nan,
                "hausman_p": np.nan, "chosen": "n/a", "chosen_coef": np.nan, "chosen_p": np.nan}

    formula = "abnormal_return ~ 1 + cosine_similarity + " + " + ".join(CONTROLS)

    fe_mod = PanelOLS.from_formula(formula + " + EntityEffects", data=panel_df)
    fe_res = fe_mod.fit(cov_type="robust")

    re_mod = RandomEffects.from_formula(formula, data=panel_df)
    re_res = re_mod.fit(cov_type="robust")

    hstat, hp = hausman(fe_res, re_res)
    # Santos & Coelho's own rule: Hausman rejects (low p) -> use FE; else RE
    # is preferred (more efficient, still consistent).
    chosen = "FE" if hp < 0.05 else "RE"
    chosen_res = fe_res if chosen == "FE" else re_res

    return {
        "n": int(fe_res.nobs), "n_companies": panel_df.index.get_level_values(0).nunique(),
        "fe_coef": fe_res.params["cosine_similarity"], "fe_p": fe_res.pvalues["cosine_similarity"],
        "re_coef": re_res.params["cosine_similarity"], "re_p": re_res.pvalues["cosine_similarity"],
        "hausman_p": hp, "chosen": chosen,
        "chosen_coef": chosen_res.params["cosine_similarity"], "chosen_p": chosen_res.pvalues["cosine_similarity"],
    }


def main() -> None:
    rows = []
    for name, windows in SCENARIOS.items():
        for window_label, fname in windows.items():
            r = run_one(POC / fname)
            rows.append({"scenario": name, "window": window_label, **r})

    out = pd.DataFrame(rows)
    out_path = POC / "santos_coelho_style_comparison.csv"
    out.to_csv(out_path, index=False)

    pd.set_option("display.width", 200)
    print(out[["scenario", "window", "n", "n_companies", "fe_p", "re_p", "hausman_p", "chosen", "chosen_p"]]
          .round(4).to_string(index=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
