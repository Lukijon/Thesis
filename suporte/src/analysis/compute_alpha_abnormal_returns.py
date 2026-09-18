"""Implements "Opção A" from recomendacoes.txt (pré-feedback do orientador,
addressing feedback_dissertacao.pdf items 2.4/5.1/6.1 -- fortalecer a
medida de retorno anormal): a per-company alpha/residual abnormal-return
measure from a 4-factor (Fama-French/Carhart) model, replacing the
market-adjusted (Ibovespa-only, no beta) return used everywhere in the
thesis so far.

Method, per company-year event (same event windows already in use --
window_start = the day after the DFP filing's CVM disclosure date,
window_end = window_start + 12 months):

  1. Estimation window: trailing 252 trading days of daily stock excess
     returns (R_i,d - Rf_d), ending strictly BEFORE window_start (no
     overlap with the event window -- no look-ahead bias).
  2. OLS with an intercept: R_i,d - Rf_d = alpha_i + beta_M*MKT_d +
     beta_S*SMB_d + beta_H*HML_d + beta_Mom*WML_d + eps_i,d.
     Unlike the earlier CAPM/FF4 comparison (compare_abnormal_return_
     models.py), which discarded the fitted alpha (implicitly assuming
     zero abnormal average return in the estimation window), this keeps
     alpha_i as part of the "expected" return -- i.e., a company's own
     idiosyncratic average performance during the estimation window is
     treated as its normal baseline, and only deviations from THAT
     baseline count as abnormal in the event window.
  3. Event window: for each day d in [window_start, window_end], compute
     the out-of-sample residual eps_i,d = (R_i,d - Rf_d) - [alpha_i +
     beta_M*MKT_d + beta_S*SMB_d + beta_H*HML_d + beta_Mom*WML_d], using
     the ESTIMATION window's alpha/betas applied to the EVENT window's
     realized factor returns.
  4. Two aggregations, both reported (recomendacoes.txt leaves the choice
     open -- "ou faça a versão composta"):
       - alpha_ar_sum: cumulative abnormal return, sum(eps_d) over the
         window (CAR-style, the formula given first/primarily).
       - alpha_ar_compound: compounded abnormal return, prod(1+eps_d)-1
         over the window (BHAR-style, compounding the residual itself).

A minimum of 100 valid daily observations is required in the estimation
window; events that don't clear it are dropped (reported).

Usage:
    python -u -m src.analysis.compute_alpha_abnormal_returns
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
FACTORS_PATH = ROOT / "data" / "raw" / "market" / "factors" / "nefin_factors.csv"

ESTIMATION_WINDOW = 252
MIN_OBS = 100
FACTOR_COLS = ["Rm_minus_Rf", "SMB", "HML", "WML"]


def load_prices() -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    return prices.set_index("date").sort_index()


def load_factors() -> pd.DataFrame:
    f = pd.read_csv(FACTORS_PATH)
    f["date"] = pd.to_datetime(f["Date"])
    f = f.set_index("date").sort_index()
    return f[FACTOR_COLS + ["Risk_Free"]]


def daily_returns(price_series: pd.Series) -> pd.Series:
    s = price_series.dropna()
    return s.pct_change().dropna()


def estimate_alpha_model(ret: pd.Series, factors: pd.DataFrame, window_start) -> tuple[float, dict, int] | None:
    """Returns (alpha, betas_dict, n_obs) from a trailing window ending
    strictly before window_start."""
    est_ret = ret[ret.index < window_start].tail(ESTIMATION_WINDOW)
    df = pd.concat([est_ret.rename("r"), factors], axis=1, join="inner").dropna()
    if len(df) < MIN_OBS:
        return None
    y = df["r"] - df["Risk_Free"]
    X = sm.add_constant(df[FACTOR_COLS])
    model = sm.OLS(y, X).fit()
    alpha = float(model.params["const"])
    betas = {k: float(model.params[k]) for k in FACTOR_COLS}
    return alpha, betas, len(df)


def event_window_residuals(ret: pd.Series, factors: pd.DataFrame, alpha: float, betas: dict,
                            window_start, window_end) -> pd.Series | None:
    factors_window = factors[(factors.index >= window_start) & (factors.index <= window_end)]
    df = pd.concat([ret.rename("r"), factors_window], axis=1, join="inner").dropna()
    if df.empty:
        return None
    expected = pd.Series(alpha, index=df.index) + df["Risk_Free"]
    for k, b in betas.items():
        expected = expected + b * df[k]
    return df["r"] - expected


# One base file per text source. narrow_annual/narrow_quarterly already
# use the reliable-only (font_heading) sample, the current default for
# those two sources; the other three have no such distinction (Sec 4.3).
SOURCES = {
    "narrow_annual": ("abnormal_returns_poc_reliable.csv", "year_prev", "year_curr"),
    "narrow_quarterly": ("abnormal_returns_itr_reliable.csv", "quarter_prev", "quarter_curr"),
    "whole_notes": ("abnormal_returns_full_notes_VERIFIED.csv", "year_prev", "year_curr"),
    "mgmt_report": ("abnormal_returns_mgmt_report.csv", "year_prev", "year_curr"),
    "risk_factors": ("abnormal_returns_risk_factors.csv", "year_prev", "year_curr"),
    # 18-month window variants, for the Santos & Coelho (2018) style comparison
    "narrow_annual_18m": ("abnormal_returns_poc_18m_reliable.csv", "year_prev", "year_curr"),
    "whole_notes_18m": ("abnormal_returns_full_notes_VERIFIED_18m.csv", "year_prev", "year_curr"),
    "mgmt_report_18m": ("abnormal_returns_mgmt_report_18m.csv", "year_prev", "year_curr"),
    "risk_factors_18m": ("abnormal_returns_risk_factors_18m.csv", "year_prev", "year_curr"),
}


def process_source(fname: str, pair_prev_col: str, pair_curr_col: str, prices: pd.DataFrame,
                    factors: pd.DataFrame) -> pd.DataFrame:
    base = pd.read_csv(POC / fname)
    base["window_start"] = pd.to_datetime(base["window_start"])
    base["window_end"] = pd.to_datetime(base["window_end"])

    rows = []
    n_dropped_estimation = n_dropped_event = 0
    for row in base.itertuples(index=False):
        col = f"{row.ticker} BS Equity"
        if col not in prices.columns:
            continue
        ret = daily_returns(prices[col])

        est = estimate_alpha_model(ret, factors, row.window_start)
        if est is None:
            n_dropped_estimation += 1
            continue
        alpha, betas, n_est = est

        eps = event_window_residuals(ret, factors, alpha, betas, row.window_start, row.window_end)
        if eps is None or len(eps) < 20:
            n_dropped_event += 1
            continue

        rows.append({
            "cd_cvm": row.cd_cvm, pair_prev_col: getattr(row, pair_prev_col), pair_curr_col: getattr(row, pair_curr_col),
            "cosine_similarity": row.cosine_similarity,
            "ticker": row.ticker, "window_start": row.window_start, "window_end": row.window_end,
            "stock_return": row.stock_return, "ar_market_adjusted": row.abnormal_return,
            "alpha_i": alpha, "beta_mkt": betas["Rm_minus_Rf"], "beta_smb": betas["SMB"],
            "beta_hml": betas["HML"], "beta_mom": betas["WML"], "n_est_obs": n_est,
            "n_event_days": len(eps),
            "alpha_ar_sum": float(eps.sum()),
            "alpha_ar_compound": float((1 + eps).prod() - 1),
        })

    df = pd.DataFrame(rows)
    print(f"  {len(df)} computable ({n_dropped_estimation} dropped <{MIN_OBS} est.-window obs, "
          f"{n_dropped_event} dropped insufficient event-window data)")
    return df


def main() -> None:
    prices = load_prices()
    factors = load_factors()

    for name, (fname, prev_col, curr_col) in SOURCES.items():
        print(f"{name} ({fname}):")
        df = process_source(fname, prev_col, curr_col, prices, factors)
        out_path = POC / f"abnormal_returns_alpha_{name}.csv"
        df.to_csv(out_path, index=False)
        print(f"  Written: {out_path}")

        if not df.empty:
            print("  beta_mkt median:", round(df["beta_mkt"].median(), 3),
                  " alpha_ar_sum median:", round(df["alpha_ar_sum"].median(), 4),
                  " alpha_ar_compound median:", round(df["alpha_ar_compound"].median(), 4))
        print()


if __name__ == "__main__":
    main()
