"""Follow-up robustness checks requested directly, run on top of the new
default methodology (narrow-note results restricted to font_heading/
font_heading pairs, src/analysis/build_reliable_only_datasets.py). Six
control/sample specifications, each producing one full battery table
(all sources x all applicable rigor stages), organized one table per
scenario rather than one row per source:

  1. Base -- leverage + ROA + past_12m_return (the thesis's current default).
  2. Sem ROA -- leverage + past_12m_return.
  3. Com tamanho -- ln_total_assets + leverage + ROA + past_12m_return.
  4. Com tamanho, sem ROA -- ln_total_assets + leverage + past_12m_return.
  5. Sem pares com salto de ano -- base controls, dropping pairs where
     year_curr - year_prev != 1 (the silently-bridged-gap issue, see
     test_year_gap_robustness.py). Annual sources only -- "consecutive
     years" has no analogue in the quarter-indexed series.
  6. Combinado -- sem ROA AND sem pares com salto de ano.
  7. Com indústria -- base controls plus sector fixed effects (C(setor)),
     pooled stage only. Company+year fixed effects already absorb sector
     (it's time-invariant per company), so the FE column is marked N/A
     here rather than reported as a redundant, collinear estimate --
     mirrors the reasoning in test_sector_control.py.
  8. Com indústria, sem ROA -- same, without ROA in the control set.
  9. Com passivo -- base controls plus total liabilities at year_curr
     (level) and its change over the pair (year_curr - year_prev).
  10. Com passivo, sem ROA -- same, without ROA in the control set.
  11. Com passivo (só nível), sem ROA -- level only, no ROA.
  12. Com passivo (só variação), sem ROA -- change only, no ROA.
  13. Com passivo (só variação), sem ROA, com tamanho -- change only,
      no ROA, plus ln_total_assets.
  14. Com Empréstimos+Financiamentos+Debêntures, sem ROA -- the specific
      debt-line-item balance-sheet account (CD_CONTA 2.01.04 current +
      2.02.01 non-current, which already includes debêntures as a
      sub-account -- src/features/build_debt_line_item.py) added as a
      control, in place of ROA.

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
WITH_SIZE = ["ln_total_assets", "leverage", "roa", "past_12m_return"]
WITH_SIZE_NO_ROA = ["ln_total_assets", "leverage", "past_12m_return"]
WITH_LIAB = ["leverage", "roa", "past_12m_return", "total_liabilities_curr", "delta_liabilities"]
WITH_LIAB_NO_ROA = ["leverage", "past_12m_return", "total_liabilities_curr", "delta_liabilities"]
WITH_LIAB_LEVEL_NO_ROA = ["leverage", "past_12m_return", "total_liabilities_curr"]
WITH_LIAB_DELTA_NO_ROA = ["leverage", "past_12m_return", "delta_liabilities"]
WITH_LIAB_DELTA_NO_ROA_SIZE = ["ln_total_assets", "leverage", "past_12m_return", "delta_liabilities"]
WITH_DEBT_LINE_NO_ROA = ["leverage", "past_12m_return", "debt_line_item"]
WITH_DEBT_LINE_DELTA_LIAB_NO_ROA = ["leverage", "past_12m_return", "debt_line_item", "delta_liabilities"]

SCENARIOS = [
    ("Base (c/ ROA)", WITH_ROA, False, False),
    ("Sem ROA", NO_ROA, False, False),
    ("Com tamanho", WITH_SIZE, False, False),
    ("Com tamanho, sem ROA", WITH_SIZE_NO_ROA, False, False),
    ("Sem pares com salto de ano", WITH_ROA, True, False),
    ("Combinado (sem ROA + sem salto)", NO_ROA, True, False),
    ("Com indústria", WITH_ROA, False, True),
    ("Com indústria, sem ROA", NO_ROA, False, True),
    ("Com passivo (nível + variação)", WITH_LIAB, False, False),
    ("Com passivo (nível + variação), sem ROA", WITH_LIAB_NO_ROA, False, False),
    ("Com passivo (só nível), sem ROA", WITH_LIAB_LEVEL_NO_ROA, False, False),
    ("Com passivo (só variação), sem ROA", WITH_LIAB_DELTA_NO_ROA, False, False),
    ("Com passivo (só variação), sem ROA, com tamanho", WITH_LIAB_DELTA_NO_ROA_SIZE, False, False),
    ("Com Empréstimos+Financiamentos+Debêntures, sem ROA", WITH_DEBT_LINE_NO_ROA, False, False),
    ("Com Empréstimos+Financiamentos+Debêntures, sem ROA, com variação do passivo", WITH_DEBT_LINE_DELTA_LIAB_NO_ROA, False, False),
]


def _load_controls() -> pd.DataFrame:
    return pd.read_csv(INTERIM / "control_variables.csv").rename(columns={
        "CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year",
    })


def _add_liability_controls(df: pd.DataFrame, year_prev_col: str, year_curr_col: str) -> pd.DataFrame:
    """Adds total_liabilities_curr (level, at year_curr) and
    delta_liabilities (year_curr - year_prev) to df, merging
    control_variables.csv on both sides of the pair."""
    liab = pd.read_csv(INTERIM / "control_variables.csv")[["CD_CVM", "fiscal_year", "total_liabilities"]]
    d = df.merge(liab.rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": year_curr_col, "total_liabilities": "total_liabilities_curr"}),
                 on=["cd_cvm", year_curr_col], how="left")
    d = d.merge(liab.rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": year_prev_col, "total_liabilities": "total_liabilities_prev"}),
                on=["cd_cvm", year_prev_col], how="left")
    d["delta_liabilities"] = d["total_liabilities_curr"] - d["total_liabilities_prev"]
    return d


def _add_debt_line_item(df: pd.DataFrame, year_curr_col: str) -> pd.DataFrame:
    """Adds debt_line_item (Empréstimos e Financiamentos + Debêntures,
    CD_CONTA 2.01.04 + 2.02.01, at year_curr) to df."""
    debt = pd.read_csv(INTERIM / "debt_line_item.csv")[["cd_cvm", "fiscal_year", "debt_line_item"]]
    return df.merge(debt.rename(columns={"fiscal_year": year_curr_col}), on=["cd_cvm", year_curr_col], how="left")


def rigor_progression(df: pd.DataFrame, outcome: str, ctrl_year_col: str, controls: list[str], with_fe: bool,
                       with_sector: bool = False) -> dict:
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
    dropna_cols = ["cd_cvm"] + controls + (["setor"] if with_sector else [])
    d_c = d_c.dropna(subset=dropna_cols)
    if d_c["cd_cvm"].nunique() >= 3 and controls:
        formula = f"{outcome} ~ cosine_similarity + " + " + ".join(controls)
        if with_sector:
            formula += " + C(setor)"
        mod_c = smf.ols(formula, data=d_c).fit(cov_type="cluster", cov_kwds={"groups": d_c["cd_cvm"]})
        p_c, n_c = mod_c.pvalues["cosine_similarity"], len(d_c)
    else:
        p_c, n_c = np.nan, len(d_c)

    # Sector FE is collinear with company fixed effects (sector doesn't
    # change within-company over the sample window), so the FE stage is
    # left N/A here rather than reported as a redundant estimate.
    p_fe, n_fe = np.nan, np.nan
    if with_fe and not with_sector:
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


def _load_sources() -> dict:
    """Returns {(família, fonte): (df, outcome, ctrl_year_col, with_fe, supports_gap_filter)}."""
    from src.analysis.test_sector_control import build_sector_map
    sector_map = build_sector_map()

    sources = {}

    ret_annual = pd.read_csv(POC / "abnormal_returns_poc_reliable.csv")
    ret_annual = _add_liability_controls(ret_annual, "year_prev", "year_curr")
    ret_annual = _add_debt_line_item(ret_annual, "year_curr")
    sources[("H1_retorno", "narrow_annual")] = (ret_annual, "abnormal_return", "year_curr", True, True)

    ret_qtr = pd.read_csv(POC / "abnormal_returns_itr_reliable.csv")
    ret_qtr["ctrl_year_col"] = ret_qtr["quarter_curr"].str[:4].astype(int)
    ret_qtr["ctrl_year_col_prev"] = ret_qtr["quarter_prev"].str[:4].astype(int)
    ret_qtr = _add_liability_controls(ret_qtr, "ctrl_year_col_prev", "ctrl_year_col")
    ret_qtr = _add_debt_line_item(ret_qtr, "ctrl_year_col")
    sources[("H1_retorno", "narrow_quarterly")] = (ret_qtr, "abnormal_return", "ctrl_year_col", True, False)

    dl = pd.read_csv(POC / "delisted_similarity_results_reliable.csv")
    dl["is_dropped"] = (dl["group"] == "dropped_or_delisted").astype(int)
    dl = _add_liability_controls(dl, "year_prev", "year_curr")
    dl = _add_debt_line_item(dl, "year_curr")
    sources[("H1_delisting", "narrow_annual")] = (dl, "is_dropped", "year_curr", False, True)

    h2_annual = pd.read_csv(POC / "h2_eps_revision_narrow_annual_all_reliable.csv")
    h2_annual = _add_liability_controls(h2_annual, "year_prev", "year_curr")
    h2_annual = _add_debt_line_item(h2_annual, "year_curr")
    sources[("H2_revisão", "narrow_annual")] = (h2_annual, "revision_pct", "year_curr", False, True)

    h2_qtr = pd.read_csv(POC / "h2_eps_revision_narrow_quarterly_all_reliable.csv")
    h2_qtr["ctrl_year_col"] = h2_qtr["quarter_curr"].str[:4].astype(int)
    h2_qtr["ctrl_year_col_prev"] = h2_qtr["quarter_prev"].str[:4].astype(int)
    h2_qtr = _add_liability_controls(h2_qtr, "ctrl_year_col_prev", "ctrl_year_col")
    h2_qtr = _add_debt_line_item(h2_qtr, "ctrl_year_col")
    sources[("H2_revisão", "narrow_quarterly")] = (h2_qtr, "revision_pct", "ctrl_year_col", False, False)

    for (df, *_rest) in sources.values():
        df["setor"] = df["cd_cvm"].map(sector_map)

    return sources


def main() -> None:
    sources = _load_sources()
    all_tables = {}

    for scen_label, controls, needs_gap_filter, with_sector in SCENARIOS:
        rows = []
        for (familia, fonte), (df, outcome, ycol, with_fe, supports_gap) in sources.items():
            if needs_gap_filter:
                if not supports_gap:
                    continue
                gap = df["year_curr"] - df["year_prev"]
                subset = df[gap == 1]
            else:
                subset = df
            r = rigor_progression(subset, outcome, ycol, controls, with_fe, with_sector=with_sector)
            rows.append({"Família": familia, "Fonte": fonte, **r})
        all_tables[scen_label] = pd.DataFrame(rows)

    pd.set_option("display.width", 200)
    combined_rows = []
    for scen_label, table in all_tables.items():
        print(f"\n=== Cenário: {scen_label} ===")
        print(table.round(4).to_string(index=False))
        t = table.copy()
        t.insert(0, "Cenário", scen_label)
        combined_rows.append(t)

    out = pd.concat(combined_rows, ignore_index=True)
    out_path = POC / "reliable_only_extra_scenarios.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
