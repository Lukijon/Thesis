"""Computes BHAR ajustado (the thesis's definitive H1 dependent variable --
see compute_alpha_abnormal_returns.py and docs/latex/main.tex Secao 3.3)
for the round-7 universe expansion (111-company panel's 2010-2014
extension + 74 IBX-extra companies), then regresses it on TextChange
(1 - cosine similarity) to answer "what's the p-value for the new
universe" honestly, including the real market-data constraint: Bloomberg
price coverage (data/raw/market/prices/stock_prices_bloomberg.csv) only
starts 2014-01-01, and only 7 of the 74 IBX-extra companies' tickers
appear in that file at all (it was built for the original 111-company
scope, not the broader IBX) -- so the computable sample here is a small
fraction of the reliable TextChange pairs in
similarity_results_new_universe_reliable.csv, not all 796 of them.

Two-stage pipeline, mirroring compute_abnormal_returns.py ->
compute_alpha_abnormal_returns.py: first the simple window/ticker
resolution (event date, first trading day on/after it, 252 trading days
forward), then the 4-factor alpha/BHAR computation on top (252-trading-day
PRE-event estimation window, needs >=100 obs -- this is the binding
constraint for how far back into 2010-2014 this can actually reach).

Usage:
    python -u -m src.analysis.compute_new_universe_returns
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from src.acquisition.b3_ibov import fetch_b3_company_registry
from src.analysis.compute_abnormal_returns import build_ticker_map as build_original_ticker_map
from src.analysis.compute_alpha_abnormal_returns import (
    FACTOR_COLS,
    estimate_alpha_model,
    event_window_residuals,
    load_factors,
    load_prices,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
WINDOW_TRADING_DAYS = 252

SIMILARITY_CSV = POC / "similarity_results_new_universe_reliable.csv"
IBX_EXTRA_UNIVERSE = INTERIM / "ibx_extra_universe.csv"
OUT_CSV = POC / "abnormal_returns_alpha_new_universe.csv"


def build_full_ticker_map() -> pd.DataFrame:
    """Original 111-panel companies via the existing resolution logic, plus
    a best-effort extension for the 74 IBX-extra companies: ibx.xlsx's own
    Bloomberg ID checked directly against the price file first (fast path,
    covers the case the ticker never changed), then the same B3-registry
    issuer-code resolution used for historical/delisted companies in
    compute_abnormal_returns.py for the rest.
    """
    original_map = build_original_ticker_map()

    price_cols = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", nrows=0).columns
    price_tickers = set(c.replace(" BS Equity", "") for c in price_cols if c != "Unnamed: 0")

    ibx_extra = pd.read_csv(IBX_EXTRA_UNIVERSE, dtype={"CD_CVM": str})
    ibx_extra["ticker_guess"] = ibx_extra["ID"].str.replace(" BS Equity", "", regex=False)
    direct_hits = ibx_extra[ibx_extra["ticker_guess"].isin(price_tickers)]
    extra_rows = [{"CD_CVM": int(r.CD_CVM), "ticker": r.ticker_guess} for r in direct_hits.itertuples()]

    unresolved = set(ibx_extra["CD_CVM"].astype(int)) - {r["CD_CVM"] for r in extra_rows}
    if unresolved:
        registry = fetch_b3_company_registry(CACHE_DIR)
        registry = registry.assign(codeCVM=pd.to_numeric(registry["codeCVM"], errors="coerce")).dropna(subset=["codeCVM"])
        registry["codeCVM"] = registry["codeCVM"].astype(int)
        issuer_of = {t: re.sub(r"\d+$", "", t) for t in price_tickers}
        by_issuer: dict[str, list[str]] = {}
        for t, issuer in issuer_of.items():
            by_issuer.setdefault(issuer, []).append(t)
        for cd_cvm in unresolved:
            issuer_rows = registry.loc[registry["codeCVM"] == cd_cvm, "issuingCompany"]
            if issuer_rows.empty:
                continue
            candidates = by_issuer.get(issuer_rows.iloc[0], [])
            if candidates:
                extra_rows.append({"CD_CVM": cd_cvm, "ticker": candidates[0]})

    extra_map = pd.DataFrame(extra_rows)
    print(f"IBX-extra ticker resolution: {len(extra_map)}/{len(ibx_extra)} companies resolved to a priced ticker "
          f"({len(direct_hits)} direct, {len(extra_map) - len(direct_hits)} via B3 registry)")

    return pd.concat([original_map, extra_map], ignore_index=True).drop_duplicates("CD_CVM")


def load_combined_event_dates() -> pd.DataFrame:
    original = pd.read_csv(INTERIM / "dfp_filing_dates.csv")
    extension = pd.read_csv(INTERIM / "dfp_filing_dates_extension.csv")
    combined = pd.concat([original, extension], ignore_index=True).drop_duplicates(["CD_CVM", "fiscal_year"])
    return combined.rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "year_curr", "filing_date": "event_date"})[
        ["cd_cvm", "year_curr", "event_date"]
    ].assign(event_date=lambda d: pd.to_datetime(d["event_date"]))


def compute_windows(events: pd.DataFrame, ticker_map: pd.DataFrame) -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    prices = prices.set_index("date").sort_index()
    last_date = prices.index.max()

    rows = []
    events = events.merge(ticker_map, left_on="cd_cvm", right_on="CD_CVM", how="left")
    for row in events.itertuples(index=False):
        if pd.isna(row.event_date) or pd.isna(row.ticker):
            continue
        col = f"{row.ticker} BS Equity"
        if col not in prices.columns:
            continue
        stock = prices[col].dropna()
        stock = stock[stock.index >= row.event_date]
        if stock.empty or len(stock) <= WINDOW_TRADING_DAYS:
            continue
        t0 = stock.index[0]
        t1 = stock.index[WINDOW_TRADING_DAYS]
        if t1 > last_date:
            continue
        rows.append({"cd_cvm": row.cd_cvm, "year_curr": row.year_curr, "ticker": row.ticker,
                      "window_start": t0, "window_end": t1})
    return pd.DataFrame(rows)


def main() -> None:
    sim = pd.read_csv(SIMILARITY_CSV, dtype={"cd_cvm": str})
    sim["cd_cvm"] = sim["cd_cvm"].astype(int)
    sim["TextChange"] = 1 - sim["cosine_similarity"]
    print(f"{len(sim)} reliable TextChange pairs in the new universe (input)")

    ticker_map = build_full_ticker_map()
    events = load_combined_event_dates()
    windows = compute_windows(events, ticker_map)
    print(f"{len(windows)} pairs have a resolvable ticker + valid 252-trading-day forward window")

    merged = sim.merge(windows, on=["cd_cvm", "year_curr"], how="inner")
    print(f"{len(merged)} pairs after merging with TextChange (have both text and a price window)")

    daily_returns = load_prices()
    factors = load_factors()

    rows = []
    n_dropped_estimation = n_dropped_event = 0
    for row in merged.itertuples(index=False):
        col = f"{row.ticker} BS Equity"
        if col not in daily_returns.columns:
            continue
        ret = daily_returns[col].dropna().pct_change().dropna()

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
            "cd_cvm": row.cd_cvm, "year_curr": row.year_curr, "ticker": row.ticker,
            "TextChange": row.TextChange, "cosine_similarity": row.cosine_similarity,
            "window_start": row.window_start, "window_end": row.window_end,
            "n_est_obs": n_est, "n_event_days": len(eps),
            "BHAR_ajustado_raw": float((1 + eps).prod() - 1),
        })

    df = pd.DataFrame(rows)
    print(f"\n{len(df)} pairs with a computable BHAR ajustado "
          f"({n_dropped_estimation} dropped <100 estimation-window obs, {n_dropped_event} dropped insufficient event-window data)")

    if len(df) < 5:
        print("\nToo few observations for a meaningful regression -- reporting the raw data only.")
        df.to_csv(OUT_CSV, index=False)
        print(f"Written: {OUT_CSV}")
        return

    # Winsorize at 1/99 pct, same convention as the thesis's BHAR ajustado (Secao 3.3)
    lo, hi = df["BHAR_ajustado_raw"].quantile([0.01, 0.99])
    df["BHAR_ajustado"] = df["BHAR_ajustado_raw"].clip(lo, hi)
    df.to_csv(OUT_CSV, index=False)
    print(f"Written: {OUT_CSV}")

    n_companies = df["cd_cvm"].nunique()
    print(f"\n{len(df)} observations, {n_companies} companies")

    model_pooled = smf.ols("BHAR_ajustado ~ TextChange", data=df).fit(cov_type="HC1")
    print("\n=== Pooled OLS, HC1 robust SE (no clustering -- see note below) ===")
    print(f"beta={model_pooled.params['TextChange']:.4f}  se={model_pooled.bse['TextChange']:.4f}  "
          f"p={model_pooled.pvalues['TextChange']:.4f}  n={int(model_pooled.nobs)}  R2={model_pooled.rsquared:.4f}")

    if n_companies >= 10:
        model_clustered = smf.ols("BHAR_ajustado ~ TextChange", data=df).fit(
            cov_type="cluster", cov_kwds={"groups": df["cd_cvm"]}
        )
        print("\n=== OLS, clustered by company (the thesis's standard practice) ===")
        print(f"beta={model_clustered.params['TextChange']:.4f}  se={model_clustered.bse['TextChange']:.4f}  "
              f"p={model_clustered.pvalues['TextChange']:.4f}  n={int(model_clustered.nobs)}  n_companies={n_companies}")
    else:
        print(f"\nOnly {n_companies} distinct companies -- too few for clustered SEs to be meaningful "
              f"(clustering needs many clusters to be trustworthy); pooled HC1 above is the honest number here.")


if __name__ == "__main__":
    main()
