"""Robustness check requested directly: `compute_similarities()` (and its
per-source equivalents) silently bridges over a not_found year -- if 2021's
note isn't located, the pair reported is 2020->2022, indistinguishable in
the data from a genuine 1-year pair. 34/816 narrow-annual pairs (4.2%) skip
at least one year. Given Sec 4.3's own finding that most not_found cases
are extraction failures, not genuine absence, these bridged pairs mix two
(or more) years of accumulated change into what is treated everywhere else
as a single year-over-year comparison -- a real, previously undocumented
inconsistency.

This reruns the H1 rigor progression (annual sources only; ITR's
quarter-gap semantics differ and aren't covered here) after dropping every
pair with year_curr - year_prev != 1, and compares p-values against the
current (bridged) results, to check whether the inconsistency actually
changes any conclusion.

Usage:
    python -u -m src.analysis.test_year_gap_robustness
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from linearmodels.panel import PanelOLS
from scipy import stats

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"
INTERIM = ROOT / "data" / "interim"

CONTROLS = ["leverage", "roa", "past_12m_return"]

SOURCES = {
    "Nota de dívida (anual)": "abnormal_returns_poc.csv",
    "Conjunto completo de notas": "abnormal_returns_full_notes_VERIFIED.csv",
    "Relatório da Administração": "abnormal_returns_mgmt_report.csv",
    "Fatores de Risco": "abnormal_returns_risk_factors.csv",
}


def rigor_progression(df: pd.DataFrame, ctrl: pd.DataFrame) -> dict:
    d = df.dropna(subset=["cosine_similarity", "abnormal_return"]).copy()
    n_simple = len(d)
    _, p_simple = stats.pearsonr(d["cosine_similarity"], d["abnormal_return"]) if n_simple >= 3 else (np.nan, np.nan)

    d_nc = d.dropna(subset=["cd_cvm"])
    if d_nc["cd_cvm"].nunique() >= 3:
        mod_nc = smf.ols("abnormal_return ~ cosine_similarity", data=d_nc).fit(
            cov_type="cluster", cov_kwds={"groups": d_nc["cd_cvm"]})
        p_nc = mod_nc.pvalues["cosine_similarity"]
    else:
        p_nc = np.nan

    d_c = d.merge(ctrl, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "ctrl_year"], how="left")
    d_c = d_c.dropna(subset=["cd_cvm"] + CONTROLS)
    if d_c["cd_cvm"].nunique() >= 3:
        formula = "abnormal_return ~ cosine_similarity + " + " + ".join(CONTROLS)
        mod_c = smf.ols(formula, data=d_c).fit(cov_type="cluster", cov_kwds={"groups": d_c["cd_cvm"]})
        p_c = mod_c.pvalues["cosine_similarity"]
    else:
        p_c = np.nan

    d_fe = d_c.dropna(subset=["year_curr"]).drop_duplicates(subset=["cd_cvm", "year_curr"])
    if d_fe["cd_cvm"].nunique() >= 5 and len(d_fe) >= 20:
        panel_df = d_fe.set_index(["cd_cvm", "year_curr"])
        formula_fe = "abnormal_return ~ 1 + cosine_similarity + " + " + ".join(CONTROLS) + " + EntityEffects + TimeEffects"
        try:
            mod_fe = PanelOLS.from_formula(formula_fe, data=panel_df).fit(cov_type="clustered", cluster_entity=True)
            p_fe = mod_fe.pvalues["cosine_similarity"]
        except Exception:
            p_fe = np.nan
    else:
        p_fe = np.nan

    return {"n": n_simple, "p_simples": p_simple, "p_agrup_sc": p_nc, "p_agrup_cc": p_c, "p_ef_fixos": p_fe}


def main() -> None:
    ctrl = pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year"})

    rows = []
    for label, fname in SOURCES.items():
        df = pd.read_csv(POC / fname)
        gap = df["year_curr"] - df["year_prev"]
        n_gap = int((gap > 1).sum())

        full = rigor_progression(df, ctrl)
        no_gap = rigor_progression(df[gap == 1], ctrl)

        rows.append({"Fonte": label, "n_pares_salto": n_gap, "pct_salto": round(100 * n_gap / len(df), 1),
                      "n_completo": full["n"], "p_simples_completo": full["p_simples"], "p_simples_sem_salto": no_gap["p_simples"],
                      "p_agrup_sc_completo": full["p_agrup_sc"], "p_agrup_sc_sem_salto": no_gap["p_agrup_sc"],
                      "p_agrup_cc_completo": full["p_agrup_cc"], "p_agrup_cc_sem_salto": no_gap["p_agrup_cc"],
                      "p_ef_fixos_completo": full["p_ef_fixos"], "p_ef_fixos_sem_salto": no_gap["p_ef_fixos"]})

    out = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(out.round(4).to_string(index=False))
    out_path = POC / "year_gap_robustness.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
