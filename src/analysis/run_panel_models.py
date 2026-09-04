"""The panel/fixed-effects model recommended repeatedly across this
session's reports (most recently reports/control_specification_test.md) as
the real replacement for the pooled clustered-OLS screening tests used
everywhere else. Every prior test asks "does similarity correlate with the
outcome across the pooled sample" (even once clustered, that's still a
between-company comparison at heart); this asks the sharper question --
"when a company's own similarity moves relative to its own normal level,
does that same company's outcome move too" -- which rules out any
*time-invariant* company confound (industry, typical governance quality,
whichever firms just always write stable text and also perform well) that
a pooled comparison, however carefully clustered, cannot.

Model: outcome_it = b*similarity_it + controls_it + company FE + year FE,
fit via linearmodels.PanelOLS, SEs clustered by company (FE and clustering
solve different problems -- omitted-variable bias vs. correlated errors --
so both stay in together). Controls are leverage/roa/past_12m_return, size
deliberately excluded (see control_specification_test.md: it does
essentially no work in this data, r=0.12 with similarity, r=-0.008 with
return).

Run across all 8 scenarios where this is well-posed: H1 returns and H2
revisions, x the four text sources each. The delisting/survivorship check
is deliberately NOT included here -- see demonstrate_delisting_degeneracy()
below for why company fixed effects are mathematically inappropriate for
that specific outcome (it's constant within company, so the within
transformation demeans it to exactly zero and any "coefficient" the model
reports is a numerical artifact, not an estimate).
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
from linearmodels.panel import PanelOLS

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

CONTROLS = ["leverage", "roa", "past_12m_return"]


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr"})


def _prep_panel(df: pd.DataFrame, time_col: str, outcome_col: str) -> pd.DataFrame:
    cols = ["cd_cvm", time_col, outcome_col, "cosine_similarity", *CONTROLS]
    d = df.dropna(subset=cols).drop_duplicates(subset=["cd_cvm", time_col]).copy()
    return d.set_index(["cd_cvm", time_col])


def _fit(panel_df: pd.DataFrame, outcome_col: str, effects: bool) -> dict:
    tail = " + EntityEffects + TimeEffects" if effects else ""
    formula = f"{outcome_col} ~ 1 + cosine_similarity + " + " + ".join(CONTROLS) + tail
    mod = PanelOLS.from_formula(formula, data=panel_df)
    res = mod.fit(cov_type="clustered", cluster_entity=True)
    out = {
        "coef": res.params["cosine_similarity"],
        "p_value": res.pvalues["cosine_similarity"],
        "n_obs": int(res.nobs),
    }
    if effects:
        entity_ids = panel_df.index.get_level_values(0)
        out["n_entities"] = entity_ids.nunique()
        out["avg_obs_per_entity"] = res.nobs / entity_ids.nunique()
        out["rsquared_within"] = res.rsquared_within
        out["poolability_p"] = res.f_pooled.pval
    return out


def run_scenario(name: str, df: pd.DataFrame, time_col: str, outcome_col: str) -> dict:
    panel_df = _prep_panel(df, time_col, outcome_col)
    pooled = _fit(panel_df, outcome_col, effects=False)
    fe = _fit(panel_df, outcome_col, effects=True)
    return {
        "scenario": name, "outcome": outcome_col,
        "n_obs": fe["n_obs"], "n_entities": fe["n_entities"], "avg_T": fe["avg_obs_per_entity"],
        "pooled_coef": pooled["coef"], "pooled_p": pooled["p_value"],
        "fe_coef": fe["coef"], "fe_p": fe["p_value"],
        "rsquared_within": fe["rsquared_within"], "poolability_p": fe["poolability_p"],
    }


def demonstrate_delisting_degeneracy() -> None:
    """Shows, rather than just asserts, why company FE is skipped for the
    delisting outcome: is_dropped never varies within a company (a company
    either stayed or dropped for its entire time in the sample), so the
    entity-demeaning step that makes fixed effects work subtracts each
    company's own mean and leaves exactly zero to explain. The model still
    runs and still reports a p-value -- that p-value is meaningless, not
    conservative -- which is the actual danger of applying this
    mechanically without checking."""
    sim = pd.read_csv(POC / "delisted_similarity_results.csv")
    sim["is_dropped"] = (sim["group"] == "dropped_or_delisted").astype(int)
    ctrl = _load_controls()
    merged = sim.merge(ctrl, on=["cd_cvm", "year_curr"], how="left")
    panel_df = _prep_panel(merged, "year_curr", "is_dropped")
    fe = _fit(panel_df, "is_dropped", effects=True)
    print("Delisting outcome forced through company+year FE anyway, to show why it's excluded above:")
    print(f"  coefficient on cosine_similarity = {fe['coef']:.2e}  (machine-precision zero, not a real estimate)")
    print(f"  p-value = {fe['p_value']:.6f}  (looks 'significant' -- it is reporting whether ~0 differs from 0)")
    print("  --> company FE is not applicable to a time-invariant-per-company outcome. Excluded from the battery above.\n")


def main() -> None:
    ctrl = _load_controls()
    results = []

    return_scenarios = {
        "narrow_annual": (POC / "abnormal_returns_poc.csv", "year_curr", None),
        "narrow_quarterly": (POC / "abnormal_returns_itr.csv", "quarter_curr", "quarterly"),
        "whole_notes": (POC / "abnormal_returns_full_notes_VERIFIED.csv", "year_curr", None),
        "mgmt_report": (POC / "abnormal_returns_mgmt_report.csv", "year_curr", None),
        "risk_factors": (POC / "abnormal_returns_risk_factors.csv", "year_curr", None),
    }
    print("=== H1 returns: two-way fixed-effects panel vs. pooled clustered OLS ===")
    for name, (path, time_col, mode) in return_scenarios.items():
        df = pd.read_csv(path)
        if mode == "quarterly":
            df["ctrl_year"] = df["quarter_curr"].str[:4].astype(int)
            df = df.merge(ctrl.rename(columns={"year_curr": "ctrl_year"}), on=["cd_cvm", "ctrl_year"], how="left")
            df["time_idx"] = pd.PeriodIndex(df["quarter_curr"], freq="Q").to_timestamp()
            r = run_scenario(name, df, "time_idx", "abnormal_return")
        else:
            df = df.merge(ctrl, on=["cd_cvm", "year_curr"], how="left")
            r = run_scenario(name, df, "year_curr", "abnormal_return")
        results.append(r)
        print(f"{name:20s} n={r['n_obs']:4d}  entities={r['n_entities']:3d}  avgT={r['avg_T']:.1f}  "
              f"pooled_p={r['pooled_p']:.4f}  ->  FE coef={r['fe_coef']:+.4f}  FE p={r['fe_p']:.4f}  "
              f"(within R2={r['rsquared_within']:.3f}, poolability p={r['poolability_p']:.4f})")

    print("\n=== H2 revisions: two-way fixed-effects panel vs. pooled clustered OLS ===")
    h2_scenarios = {
        "narrow_annual": (POC / "h2_eps_revision_narrow_annual_all.csv", "year_curr", None),
        "narrow_quarterly": (POC / "h2_eps_revision_narrow_quarterly_all.csv", "quarter_curr", "quarterly"),
        "whole_notes": (POC / "h2_eps_revision_whole_notes_all.csv", "year_curr", None),
        "mgmt_report": (POC / "h2_eps_revision_mgmt_report_all.csv", "year_curr", None),
    }
    for name, (path, time_col, mode) in h2_scenarios.items():
        df = pd.read_csv(path)
        if mode == "quarterly":
            df["time_idx"] = pd.PeriodIndex(df["quarter_curr"], freq="Q").to_timestamp()
            r = run_scenario(name, df, "time_idx", "revision_pct")
        else:
            r = run_scenario(name, df, "year_curr", "revision_pct")
        results.append(r)
        print(f"{name:20s} n={r['n_obs']:4d}  entities={r['n_entities']:3d}  avgT={r['avg_T']:.1f}  "
              f"pooled_p={r['pooled_p']:.4f}  ->  FE coef={r['fe_coef']:+.4f}  FE p={r['fe_p']:.4f}  "
              f"(within R2={r['rsquared_within']:.3f}, poolability p={r['poolability_p']:.4f})")

    print()
    demonstrate_delisting_degeneracy()

    out_path = POC / "panel_model_results.csv"
    pd.DataFrame(results).to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
