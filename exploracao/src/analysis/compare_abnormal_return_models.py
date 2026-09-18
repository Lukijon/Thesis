"""Sanity check requested directly: rebuild the H1 narrow-annual abnormal
return under three alternative benchmark models (CAPM, a four-factor
Fama-French/Carhart model for Brazil, and a size-matched reference
portfolio) and compare the resulting H1 rigor-progression p-values against
this project's actual specification (market-adjusted, no beta).

Data:
  - Daily risk factors for Brazil (Rm-Rf, SMB, HML, WML, Risk_Free) from
    NEFIN/USP (https://nefin.com.br/data/risk-factors/), a public academic
    series, not Bloomberg-restricted. Cached at
    data/raw/market/factors/nefin_factors.csv (fetched 2026-09-06).
  - Daily stock prices already on disk (data/raw/market/prices/), same
    source used for the project's own market-adjusted return.
  - Size (ln_total_assets) from data/interim/control_variables.csv, for
    the size-matched reference-portfolio benchmark.

Method, all three models:
  1. For each company-year event already in abnormal_returns_poc.csv
     (same events, same [window_start, window_end] used everywhere else
     in this project -- only the benchmark changes), estimate the model's
     risk loadings (beta, or beta_mkt/beta_smb/beta_hml/beta_wml) via OLS
     on daily excess returns over a trailing 252-trading-day window ending
     the day before window_start (no overlap with the event window).
  2. Compound the model's daily expected returns over [window_start,
     window_end] to get an expected buy-and-hold return for that window.
  3. Abnormal return = actual buy-and-hold return - expected buy-and-hold
     return (CAPM, FF/Carhart) or - peer-group average buy-and-hold return
     (size-matched, no beta estimation involved at all).

A minimum of 100 valid daily observations is required in the estimation
window; events that don't clear it are dropped for that model (reported).

Usage:
    python -u -m src.analysis.compare_abnormal_return_models
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
import statsmodels.formula.api as smf
from linearmodels.panel import PanelOLS

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
FACTORS_PATH = ROOT / "data" / "raw" / "market" / "factors" / "nefin_factors.csv"

ESTIMATION_WINDOW = 252
MIN_OBS = 100
CONTROLS = ["leverage", "roa", "past_12m_return"]


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
    return f[["Rm_minus_Rf", "SMB", "HML", "WML", "Risk_Free"]]


def daily_returns(price_series: pd.Series) -> pd.Series:
    s = price_series.dropna()
    return s.pct_change().dropna()


def estimate_capm(ret: pd.Series, factors: pd.DataFrame, window_start) -> tuple[float, int] | None:
    """Returns (beta, n_obs) from a trailing window ending before window_start."""
    est_ret = ret[ret.index < window_start].tail(ESTIMATION_WINDOW)
    df = pd.concat([est_ret.rename("r"), factors["Rm_minus_Rf"], factors["Risk_Free"]], axis=1, join="inner").dropna()
    if len(df) < MIN_OBS:
        return None
    y = df["r"] - df["Risk_Free"]
    X = sm.add_constant(df["Rm_minus_Rf"])
    model = sm.OLS(y, X).fit()
    return float(model.params["Rm_minus_Rf"]), len(df)


def estimate_ff4(ret: pd.Series, factors: pd.DataFrame, window_start) -> tuple[dict, int] | None:
    est_ret = ret[ret.index < window_start].tail(ESTIMATION_WINDOW)
    df = pd.concat([est_ret.rename("r"), factors], axis=1, join="inner").dropna()
    if len(df) < MIN_OBS:
        return None
    y = df["r"] - df["Risk_Free"]
    X = sm.add_constant(df[["Rm_minus_Rf", "SMB", "HML", "WML"]])
    model = sm.OLS(y, X).fit()
    betas = {k: float(model.params[k]) for k in ["Rm_minus_Rf", "SMB", "HML", "WML"]}
    return betas, len(df)


def expected_bh_return(factors_window: pd.DataFrame, betas: dict) -> float:
    """Compounds daily expected returns (Rf + sum(beta_k * factor_k)) over
    the event window into a single expected buy-and-hold return."""
    daily_expected = factors_window["Risk_Free"].copy()
    for k, b in betas.items():
        daily_expected = daily_expected + b * factors_window[k]
    return float((1 + daily_expected).prod() - 1)


def main() -> None:
    base = pd.read_csv(POC / "abnormal_returns_poc.csv")
    base["window_start"] = pd.to_datetime(base["window_start"])
    base["window_end"] = pd.to_datetime(base["window_end"])
    prices = load_prices()
    factors = load_factors()
    ctrl = pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year"})

    rows = []
    n_capm_dropped = n_ff_dropped = 0
    for row in base.itertuples(index=False):
        col = f"{row.ticker} BS Equity"
        if col not in prices.columns:
            continue
        ret = daily_returns(prices[col])
        factors_window = factors[(factors.index >= row.window_start) & (factors.index <= row.window_end)]
        if factors_window.empty:
            continue

        out = {
            "cd_cvm": row.cd_cvm, "year_prev": row.year_prev, "year_curr": row.year_curr,
            "cosine_similarity": row.cosine_similarity,
            "diagnostic_prev": row.diagnostic_prev, "diagnostic_curr": row.diagnostic_curr,
            "stock_return": row.stock_return,
            "ar_market_adjusted": row.abnormal_return,  # what the thesis uses today
        }

        capm = estimate_capm(ret, factors, row.window_start)
        if capm is None:
            out["ar_capm"] = np.nan
            n_capm_dropped += 1
        else:
            beta, _ = capm
            exp_ret = expected_bh_return(factors_window, {"Rm_minus_Rf": beta})
            out["ar_capm"] = row.stock_return - exp_ret

        ff4 = estimate_ff4(ret, factors, row.window_start)
        if ff4 is None:
            out["ar_ff4"] = np.nan
            n_ff_dropped += 1
        else:
            betas, _ = ff4
            exp_ret = expected_bh_return(factors_window, betas)
            out["ar_ff4"] = row.stock_return - exp_ret

        rows.append(out)

    df = pd.DataFrame(rows)
    print(f"{len(df)} events with prices; CAPM estimable for {df['ar_capm'].notna().sum()} "
          f"({n_capm_dropped} dropped, <{MIN_OBS} obs); FF4 estimable for {df['ar_ff4'].notna().sum()} ({n_ff_dropped} dropped)")

    # size-matched reference portfolio: within each fiscal year, average
    # buy-and-hold stock_return of same-size-tercile peers (excluding self)
    df = df.merge(ctrl, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "ctrl_year"], how="left")
    df["size_tercile"] = df.groupby("year_curr")["ln_total_assets"].transform(
        lambda s: pd.qcut(s, 3, labels=False, duplicates="drop") if s.notna().sum() >= 6 else np.nan
    )
    peer_avg = {}
    for (yr, tercile), g in df.groupby(["year_curr", "size_tercile"]):
        if pd.isna(tercile):
            continue
        for idx in g.index:
            peers = g.drop(idx)["stock_return"]
            peer_avg[idx] = peers.mean() if len(peers) >= 2 else np.nan
    df["peer_bh_return"] = df.index.map(peer_avg)
    df["ar_size_matched"] = df["stock_return"] - df["peer_bh_return"]

    out_path = POC / "abnormal_returns_model_comparison.csv"
    df.to_csv(out_path, index=False)
    print(f"Written: {out_path}")

    # ---- H1 rigor progression under each model ----
    methods = {
        "Ajustado ao mercado (hoje)": "ar_market_adjusted",
        "CAPM": "ar_capm",
        "Fama-French/Carhart (4 fatores)": "ar_ff4",
        "Carteira pareada por tamanho": "ar_size_matched",
    }

    results = []
    for label, col in methods.items():
        d = df.dropna(subset=[col, "cosine_similarity"]).copy()
        d = d.rename(columns={col: "abnormal_return"})

        n_simple = len(d)
        _, p_simple = stats.pearsonr(d["cosine_similarity"], d["abnormal_return"])

        d_nc = d.dropna(subset=["cd_cvm"])
        mod_nc = smf.ols("abnormal_return ~ cosine_similarity", data=d_nc).fit(
            cov_type="cluster", cov_kwds={"groups": d_nc["cd_cvm"]})
        p_nc, n_nc = mod_nc.pvalues["cosine_similarity"], len(d_nc)

        d_c = d.dropna(subset=["cd_cvm"] + CONTROLS)
        formula = "abnormal_return ~ cosine_similarity + " + " + ".join(CONTROLS)
        mod_c = smf.ols(formula, data=d_c).fit(cov_type="cluster", cov_kwds={"groups": d_c["cd_cvm"]})
        p_c, n_c = mod_c.pvalues["cosine_similarity"], len(d_c)

        d_fe = d.dropna(subset=["cd_cvm", "year_curr"] + CONTROLS).drop_duplicates(subset=["cd_cvm", "year_curr"])
        if d_fe["cd_cvm"].nunique() >= 5 and len(d_fe) >= 20:
            panel_df = d_fe.set_index(["cd_cvm", "year_curr"])
            formula_fe = "abnormal_return ~ 1 + cosine_similarity + " + " + ".join(CONTROLS) + " + EntityEffects + TimeEffects"
            mod_fe = PanelOLS.from_formula(formula_fe, data=panel_df).fit(cov_type="clustered", cluster_entity=True)
            p_fe, n_fe = mod_fe.pvalues["cosine_similarity"], int(mod_fe.nobs)
        else:
            p_fe, n_fe = np.nan, len(d_fe)

        results.append({
            "Metodo": label, "n_simples": n_simple, "p_simples": p_simple,
            "n_agrup": n_nc, "p_agrup_sc": p_nc, "n_controles": n_c, "p_agrup_cc": p_c,
            "n_fe": n_fe, "p_ef_fixos": p_fe,
        })

    out = pd.DataFrame(results)
    pd.set_option("display.width", 200)
    print()
    print(out.round(4).to_string(index=False))
    out.to_csv(POC / "abnormal_return_model_comparison_table.csv", index=False)
    print(f"\nWritten: {POC / 'abnormal_return_model_comparison_table.csv'}")


if __name__ == "__main__":
    main()
