"""First, POC-scale look at H1: does year-over-year debt-note textual change
(cosine similarity, from src/processing/run_poc_tfidf.py and
run_delisted_analysis.py) line up with the stock's abnormal return in the
12 months after the note is *disclosed*?

This is deliberately simple, not the thesis's final regression:
  - Market-adjusted return only (stock buy-and-hold minus Ibovespa
    buy-and-hold over the same window) -- no market-model beta, no size/
    value/momentum controls. A real market-model or Fama-French/Carhart
    abnormal return belongs in src/analysis/ once control variables (still
    outstanding, see TODO.md) are available.
  - Event date is the DFP's actual CVM receipt date (DT_RECEB) for the
    *current* fiscal year of each (year_prev, year_curr) similarity pair --
    i.e. when the changed note actually became public -- not the fiscal
    year-end (DT_REFER), which nobody could trade on.
  - Only the POC's already-computed similarity pairs are used (the 20
    core companies + the 45-company historical/delisted set), since those
    are the only company-years with a note-extraction diagnostic attached.
    Scaling this to the full universe is part 2 of acquisition, not here.

Prerequisite: python -u -m src.acquisition.build_filing_dates (writes
data/interim/dfp_filing_dates.csv, the event-date reference this reads).

Ticker resolution: the 66 current-IBOV companies map directly via
data/interim/ibov_non_financial_universe.csv (COD). The 45 historical/
delisted companies have no such mapping yet -- resolved here via B3's live
company registry (issuer-code prefix), which only succeeds for companies
still listed under *some* ticker today (~30/45 -- the other ~15 went
private, merged away entirely, or are bankruptcy estates, which is exactly
the kind of company this section can't compute a forward return for).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.acquisition.b3_ibov import fetch_b3_company_registry

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"
MARKET = ROOT / "data" / "raw" / "market" / "prices"
WINDOW_TRADING_DAYS = 252  # ~12 months


def load_event_dates() -> pd.DataFrame:
    """(cd_cvm, year_curr) -> event_date, from the filing-dates reference
    table (src/acquisition/build_filing_dates.py) -- the actual CVM receipt
    date, i.e. when the market could first react to the changed note."""
    filing_dates = pd.read_csv(INTERIM / "dfp_filing_dates.csv")
    return filing_dates.rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "year_curr", "filing_date": "event_date",
    })[["cd_cvm", "year_curr", "event_date"]].assign(
        event_date=lambda d: pd.to_datetime(d["event_date"])
    )


def build_ticker_map() -> pd.DataFrame:
    """CD_CVM -> best price-file ticker, for the 66 current-universe
    companies (direct) plus whichever historical/delisted companies still
    resolve to a live B3 ticker."""
    universe = pd.read_csv(INTERIM / "ibov_non_financial_universe.csv")
    current_map = universe[["CD_CVM", "COD"]].rename(columns={"COD": "ticker"})

    price_cols = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", nrows=0).columns
    price_tickers = [c.replace(" BS Equity", "") for c in price_cols if c != "Unnamed: 0"]
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1])
    n_valid = {t: prices[f"{t} BS Equity"].apply(pd.to_numeric, errors="coerce").notna().sum() for t in price_tickers}

    import re

    issuer_of = {t: re.sub(r"\d+$", "", t) for t in price_tickers}
    by_issuer: dict[str, list[str]] = {}
    for t, issuer in issuer_of.items():
        by_issuer.setdefault(issuer, []).append(t)

    registry = fetch_b3_company_registry(CACHE_DIR)
    registry = registry.assign(codeCVM=pd.to_numeric(registry["codeCVM"], errors="coerce")).dropna(subset=["codeCVM"])
    registry["codeCVM"] = registry["codeCVM"].astype(int)

    hist_codes = set(pd.read_csv(POC / "delisted_similarity_results.csv")["cd_cvm"].unique()) - set(current_map["CD_CVM"])
    hist_rows = []
    for cd_cvm in hist_codes:
        issuer_rows = registry.loc[registry["codeCVM"] == cd_cvm, "issuingCompany"]
        if issuer_rows.empty:
            continue
        issuer = issuer_rows.iloc[0]
        candidates = by_issuer.get(issuer, [])
        if not candidates:
            continue
        best = max(candidates, key=lambda t: n_valid[t])
        hist_rows.append({"CD_CVM": cd_cvm, "ticker": best})

    hist_map = pd.DataFrame(hist_rows)
    return pd.concat([current_map, hist_map], ignore_index=True).drop_duplicates("CD_CVM")


def compute_returns(events: pd.DataFrame, ticker_map: pd.DataFrame) -> pd.DataFrame:
    prices = pd.read_csv(MARKET / "stock_prices_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date"})
    prices["date"] = pd.to_datetime(prices["date"], format="%m/%d/%Y")
    for c in prices.columns:
        if c != "date":
            prices[c] = pd.to_numeric(prices[c], errors="coerce")
    prices = prices.set_index("date").sort_index()

    ibov = pd.read_csv(MARKET / "ibov_index_bloomberg.csv", skiprows=[1]).rename(columns={"Unnamed: 0": "date", "IBOV Index": "ibov"})
    ibov["date"] = pd.to_datetime(ibov["date"], format="%m/%d/%Y")
    ibov["ibov"] = pd.to_numeric(ibov["ibov"], errors="coerce")
    ibov = ibov.set_index("date").sort_index()["ibov"].dropna()

    last_date = ibov.index.max()

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
        if stock.empty:
            continue
        t0 = stock.index[0]
        if len(stock) <= WINDOW_TRADING_DAYS:
            continue  # not enough forward trading history yet
        t1 = stock.index[WINDOW_TRADING_DAYS]
        if t1 > last_date:
            continue

        p0, p1 = stock.iloc[0], stock.loc[t1]
        stock_return = p1 / p0 - 1

        ibov_window = ibov[(ibov.index >= t0) & (ibov.index <= t1)]
        if len(ibov_window) < 2:
            continue
        ibov_return = ibov_window.iloc[-1] / ibov_window.iloc[0] - 1

        rows.append({
            "cd_cvm": row.cd_cvm,
            "year_curr": row.year_curr,
            "ticker": row.ticker,
            "event_date": row.event_date,
            "window_start": t0,
            "window_end": t1,
            "stock_return": stock_return,
            "ibov_return": ibov_return,
            "abnormal_return": stock_return - ibov_return,
        })
    return pd.DataFrame(rows)


def main() -> None:
    core = pd.read_csv(POC / "similarity_results.csv")
    core["poc_group"] = "core_20"
    delisted = pd.read_csv(POC / "delisted_similarity_results.csv")
    delisted["poc_group"] = delisted["group"]
    sim = pd.concat([core, delisted], ignore_index=True, sort=False)

    events = load_event_dates()
    ticker_map = build_ticker_map()
    returns = compute_returns(events, ticker_map)

    merged = sim.merge(returns, on=["cd_cvm", "year_curr"], how="inner")
    merged = merged.drop_duplicates(subset=["cd_cvm", "year_prev", "year_curr"])

    out_path = POC / "abnormal_returns_poc.csv"
    merged.to_csv(out_path, index=False)

    both_reliable = merged[(merged["diagnostic_prev"] == "font_heading") & (merged["diagnostic_curr"] == "font_heading")]

    print(f"{len(sim)} note-similarity pairs in the POC corpus")
    print(f"{ticker_map['CD_CVM'].nunique()} companies with a resolved ticker "
          f"({ticker_map['CD_CVM'].isin(delisted['cd_cvm']).sum()} of the historical/delisted set)")
    print(f"{len(merged)} pairs have both a similarity score and a computable 12-month abnormal return\n")

    for label, df in [("All computable pairs", merged), ("Reliable extraction only (font_heading/font_heading)", both_reliable)]:
        if len(df) < 3:
            print(f"{label}: n={len(df)} -- too few to correlate")
            continue
        pearson = df["cosine_similarity"].corr(df["abnormal_return"], method="pearson")
        spearman = df["cosine_similarity"].corr(df["abnormal_return"], method="spearman")
        print(f"{label}: n={len(df)}")
        print(f"  Pearson  r(similarity, abnormal return) = {pearson:.3f}")
        print(f"  Spearman rho(similarity, abnormal return) = {spearman:.3f}")

    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
