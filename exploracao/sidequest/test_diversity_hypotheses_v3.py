"""v3 test battery: adds market-to-book, ROA, ROE, and past-return as
outcomes (race-diversity-vs-performance is still an open gap per the
literature verification, even though gender-diversity-vs-performance is
already published for Brazil), and a sector-group control as an
additional specification, motivated by v2's unexplained
workforce-leadership-gender result.

Usage:
    python -m sidequest.test_diversity_hypotheses_v3
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sidequest" / "diversity_analysis_dataset_v3.csv"
CONTROLS = ["ln_total_assets", "leverage", "roa"]
CONTROLS_NO_ROA = ["ln_total_assets", "leverage"]  # for outcomes that are themselves roa/roe

PREDICTORS = {
    "pct_female_board": "Board: % female",
    "pct_black_brown_board": "Board: % Black/Brown",
    "has_black_brown_board": "Board: has any Black/Brown (0/1)",
    "pct_female_exec": "Exec board: % female",
    "pct_black_brown_exec": "Exec board: % Black/Brown",
    "pct_female_leadership": "Leadership: % female",
    "pct_black_brown_leadership": "Leadership: % Black/Brown",
}
OUTCOMES = {
    "cost_of_debt_proxy": "Cost of debt proxy",
    "return_volatility": "Return volatility",
    "market_to_book": "Market-to-book (Tobin's Q proxy)",
    "roa": "ROA",
    "roe": "ROE",
    "past_12m_return": "Trailing 12m stock return",
}


def clustered_ols(df: pd.DataFrame, outcome: str, predictor: str, controls: list[str], extra_dummies: str | None = None):
    cols = [outcome, predictor, "CD_CVM"] + controls + ([extra_dummies] if extra_dummies else [])
    have = df.dropna(subset=cols)
    if len(have) < 20 or have["CD_CVM"].nunique() < 10:
        return None, None, len(have)
    formula = f"{outcome} ~ {predictor}" + "".join(f" + {c}" for c in controls)
    if extra_dummies:
        formula += f" + C({extra_dummies})"
    model = smf.ols(formula, data=have).fit(cov_type="cluster", cov_kwds={"groups": have["CD_CVM"]})
    return model.params[predictor], model.pvalues[predictor], len(have)


def try_fixed_effects(df: pd.DataFrame, outcome: str, predictor: str, controls: list[str]):
    try:
        from linearmodels.panel import PanelOLS
    except ImportError:
        return None, None, None
    cols = ["CD_CVM", "year", outcome, predictor] + controls
    have = df.dropna(subset=cols).drop_duplicates(subset=["CD_CVM", "year"])
    if len(have) < 30 or have["CD_CVM"].nunique() < 10 or have["year"].nunique() < 2:
        return None, None, None
    panel_df = have.set_index(["CD_CVM", "year"])
    formula = f"{outcome} ~ 1 + {predictor} + " + " + ".join(controls) + " + EntityEffects + TimeEffects"
    try:
        mod = PanelOLS.from_formula(formula, data=panel_df)
        res = mod.fit(cov_type="clustered", cluster_entity=True)
        return res.params[predictor], res.pvalues[predictor], int(res.nobs)
    except Exception:
        return None, None, None


def main() -> None:
    df = pd.read_csv(DATA)
    results = []

    for outcome in OUTCOMES:
        controls = CONTROLS_NO_ROA if outcome in ("roa", "roe") else CONTROLS
        print(f"\n=== Outcome: {OUTCOMES[outcome]} ===")
        for predictor in PREDICTORS:
            have = df.dropna(subset=[outcome, predictor])
            if len(have) < 20:
                continue
            r, p = stats.pearsonr(have[predictor], have[outcome])
            coef0, p0, n0 = clustered_ols(df, outcome, predictor, [])
            coef1, p1, n1 = clustered_ols(df, outcome, predictor, controls)
            coef2, p2, n2 = clustered_ols(df, outcome, predictor, controls, extra_dummies="sector_group")
            fe_coef, fe_p, fe_n = try_fixed_effects(df, outcome, predictor, controls)
            row = {
                "outcome": outcome, "predictor": predictor, "n_simple": len(have),
                "simple_r": r, "simple_p": p,
                "clustered_no_controls_p": p0, "n_clustered": n0,
                "clustered_with_controls_p": p1, "n_full": n1,
                "clustered_with_sector_p": p2, "n_sector": n2,
                "fe_coef": fe_coef, "fe_p": fe_p, "fe_n": fe_n,
            }
            results.append(row)
            best_p = min([x for x in [p, p0, p1, p2, fe_p] if x is not None])
            flag = " <=====" if best_p < 0.05 else ""
            print(f"  {PREDICTORS[predictor]:34s} n={len(have):3d}  simple p={p:.3f}  clust p={p0:.3f}  "
                  f"+ctrl p={p1 if p1 is not None else float('nan'):.3f}  +sector p={p2 if p2 is not None else float('nan'):.3f}  "
                  f"FE p={fe_p if fe_p is not None else float('nan'):.3f}{flag}")

    out = pd.DataFrame(results)
    out.to_csv(ROOT / "sidequest" / "diversity_test_results_v3.csv", index=False)
    print(f"\nWrote sidequest/diversity_test_results_v3.csv ({len(out)} rows)")

    sig = out[(out[["clustered_with_controls_p", "clustered_with_sector_p", "fe_p"]].min(axis=1) < 0.05)]
    print(f"\n{len(sig)} predictor/outcome combos with ANY specification below p=0.05:")
    print(sig[["outcome", "predictor", "clustered_with_controls_p", "clustered_with_sector_p", "fe_p"]].to_string())


if __name__ == "__main__":
    main()
