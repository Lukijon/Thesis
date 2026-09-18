"""Implements the M0-M5 control grid (especificacoes_m0_m5_dissertacao.pdf)
for H1's narrow-annual debt note, across the three abnormal-return
specifications now on the table: the original market-adjusted (no beta)
return, and the two new alpha/residual measures from Opção A
(recomendacoes.txt) -- CAR (sum of daily residuals) and BHAR (compounded
residual).

TextChange = 1 - cosine_similarity is used throughout (feedback item 2.6),
so a positive coefficient means "more textual change -> higher abnormal
return".

Models (cumulative, per the especificacoes document):
  M0 = TextChange + FE empresa + FE ano                          [diagnóstico]
  M1 = M0 + Size + ROA + Leverage + Momentum                     [baseline]
  M2 = M1 + delta_ROA + delta_Leverage + delta_Debt              [PRINCIPAL]
  M3 = M2 + BTM + Volatility                                     [robustez econômica]
  M4 = M3 + Liquidity (Amihud)                                   [robustez/mecanismo,
                                                                    PARCIAL: sem AnalystCoverage,
                                                                    não construível com os
                                                                    dados disponíveis]
  M5 = M3 + FE(Setor x Ano) em vez de FE ano simples              [robustez exigente]

M0-M4 use company+year two-way fixed effects (PanelOLS). M5 keeps company
FE but replaces year FE with sector x year FE, implemented via OLS with
company and sector:year dummy columns (linearmodels' PanelOLS doesn't
support a non-panel-index interacted FE dimension directly), clustered by
company either way.

Usage:
    python -u -m src.analysis.run_m0_m5_grid
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from linearmodels.panel import PanelOLS

from src.analysis.test_sector_control import build_sector_map
from src.features.build_m0_m5_controls import build_panel

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"

DV_LABELS = {
    "ar_market_adjusted": "Ajustado ao mercado (original)",
    "alpha_ar_sum": "CAR (alpha, soma dos resíduos)",
    "alpha_ar_compound": "BHAR (alpha, resíduo composto)",
    "alpha_ar_compound_winsorized": "BHAR ajustado (winsorizado 1/99)",
}

WINSOR_LO, WINSOR_HI = 0.01, 0.99

M0 = []
M1 = ["ln_total_assets", "roa", "leverage", "past_12m_return"]
M2 = M1 + ["delta_roa", "delta_leverage", "delta_debt"]
M3 = M2 + ["btm", "volatility"]
M4 = M3 + ["amihud_illiquidity_scaled"]
M5_CONTROLS = M3  # FE changes, not controls


def _fit_panel(df: pd.DataFrame, outcome: str, controls: list[str]) -> dict:
    needed = ["cd_cvm", "year_curr", outcome, "TextChange"] + controls
    d = df.dropna(subset=needed).drop_duplicates(subset=["cd_cvm", "year_curr"]).copy()
    n_companies = d["cd_cvm"].nunique()
    if n_companies < 5 or len(d) < 20:
        return {"n": len(d), "n_companies": n_companies, "beta": np.nan, "se": np.nan,
                "ci_low": np.nan, "ci_high": np.nan, "p": np.nan, "r2_within": np.nan}

    panel_df = d.set_index(["cd_cvm", "year_curr"])
    rhs = " + ".join(["TextChange"] + controls)
    formula = f"{outcome} ~ 1 + {rhs} + EntityEffects + TimeEffects"
    model = PanelOLS.from_formula(formula, data=panel_df).fit(cov_type="clustered", cluster_entity=True)
    b = model.params["TextChange"]
    se = model.std_errors["TextChange"]
    ci = model.conf_int().loc["TextChange"]
    return {"n": int(model.nobs), "n_companies": n_companies, "beta": b, "se": se,
            "ci_low": ci.iloc[0], "ci_high": ci.iloc[1], "p": model.pvalues["TextChange"],
            "r2_within": model.rsquared_within}


def _fit_sector_year_fe(df: pd.DataFrame, outcome: str, controls: list[str]) -> dict:
    needed = ["cd_cvm", "year_curr", "setor", outcome, "TextChange"] + controls
    d = df.dropna(subset=needed).drop_duplicates(subset=["cd_cvm", "year_curr"]).copy()
    n_companies = d["cd_cvm"].nunique()
    if n_companies < 5 or len(d) < 20:
        return {"n": len(d), "n_companies": n_companies, "beta": np.nan, "se": np.nan,
                "ci_low": np.nan, "ci_high": np.nan, "p": np.nan, "r2_within": np.nan}

    rhs = " + ".join(["TextChange"] + controls)
    formula = f"{outcome} ~ 1 + {rhs} + C(cd_cvm) + C(setor):C(year_curr)"
    try:
        model = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d["cd_cvm"]})
    except Exception:
        return {"n": len(d), "n_companies": n_companies, "beta": np.nan, "se": np.nan,
                "ci_low": np.nan, "ci_high": np.nan, "p": np.nan, "r2_within": np.nan}
    b = model.params["TextChange"]
    se = model.bse["TextChange"]
    ci = model.conf_int().loc["TextChange"]
    return {"n": len(d), "n_companies": n_companies, "beta": b, "se": se,
            "ci_low": ci[0], "ci_high": ci[1], "p": model.pvalues["TextChange"], "r2_within": np.nan}


def main() -> None:
    sample = pd.read_csv(POC / "abnormal_returns_alpha_narrow_annual.csv")
    df = build_panel(sample)
    df["TextChange"] = 1 - df["cosine_similarity"]
    df["amihud_illiquidity_scaled"] = df["amihud_illiquidity"] * 1e6  # rescaled for coefficient readability

    # BHAR ajustado: winsorized at 1/99 to tame the compounding-induced
    # right skew (raw skewness ~10.1 -> ~1.9 after winsorizing), the same
    # treatment already used elsewhere in this project for extreme values.
    lo, hi = df["alpha_ar_compound"].quantile([WINSOR_LO, WINSOR_HI])
    df["alpha_ar_compound_winsorized"] = df["alpha_ar_compound"].clip(lo, hi)

    sector_map = build_sector_map()
    df["setor"] = df["cd_cvm"].map(sector_map)

    model_specs = [
        ("M0", M0, "diagnóstico", "panel"),
        ("M1", M1, "baseline", "panel"),
        ("M2", M2, "PRINCIPAL", "panel"),
        ("M3", M3, "robustez econômica", "panel"),
        ("M4", M4, "robustez/mecanismo (parcial: sem AnalystCoverage)", "panel"),
        ("M5", M5_CONTROLS, "robustez exigente (FE setor×ano)", "sector_year"),
    ]

    rows = []
    for dv_col, dv_label in DV_LABELS.items():
        for m_name, controls, status, fe_type in model_specs:
            r = _fit_panel(df, dv_col, controls) if fe_type == "panel" else _fit_sector_year_fe(df, dv_col, controls)
            rows.append({"VD": dv_label, "Modelo": m_name, "Status": status, **r})

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    for dv_label in DV_LABELS.values():
        print(f"\n=== {dv_label} ===")
        sub = out[out["VD"] == dv_label].drop(columns=["VD"])
        print(sub.round(4).to_string(index=False))

    out_path = POC / "m0_m5_grid_results.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
