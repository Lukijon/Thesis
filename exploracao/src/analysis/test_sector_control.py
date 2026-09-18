"""Sanity check requested directly: does adding sector controls (fixed
effects at the pooled-regression stages) change H1's narrow-annual
results? Size was already tested and dropped (Sec. 3.5); sector never
was, and it's a genuine gap -- SETOR_ATIV is already in CVM's cadastral
data for the whole universe, no new acquisition needed.

Company fixed effects (the project's strictest stage) already absorb
sector for virtually every company, since sector membership essentially
never changes within the sample window -- adding sector dummies on top of
company+year FE would be redundant/collinear by construction, so this
only tests the pooled stages (where sector isn't otherwise controlled
for): "Agrup., s/c" becomes "+ sector FE", "Agrup., c/c" becomes
"+ controls + sector FE".

Usage:
    python -u -m src.analysis.test_sector_control
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"

CONTROLS = ["leverage", "roa", "past_12m_return"]


# A few sectors appear under two slightly different spellings in CVM's own
# cadastral data (abbreviated vs. full, or a stray case difference) --
# found by inspecting the raw value_counts output before trusting the
# grouping, the same discipline used everywhere else in this project.
# Left unmapped means "keep as-is".
_SECTOR_ALIASES = {
    "Const. Civil, Mat. Const. e Decoração": "Construção Civil, Mat. Constr. e Decoração",
    "Serviços médicos": "Serviços Médicos",
    "Máqs., Equip., Veíc. e Peças": "Máquinas, Equipamentos, Veículos e Peças",
}


def _consolidated_sector(raw: str) -> str:
    """Strips the "Emp. Adm. Part. - " (holding company) prefix so a
    holding company in a given sector is grouped with operating companies
    in that same sector, rather than treated as its own separate,
    near-singleton category; then folds in the known aliases above."""
    prefix = "Emp. Adm. Part. - "
    s = raw[len(prefix):] if raw.startswith(prefix) else raw
    return _SECTOR_ALIASES.get(s, s)


def build_sector_map() -> pd.Series:
    from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
    from src.acquisition.cvm_dfp import load_cadastral

    cadastral = load_cadastral(CACHE_DIR)
    cadastral = cadastral.assign(CD_CVM_INT=cadastral["CD_CVM"].astype(int))
    sector_by_code = cadastral.drop_duplicates("CD_CVM_INT").set_index("CD_CVM_INT")["SETOR_ATIV"]

    current = pd.read_csv(INTERIM / "ibov_non_financial_universe.csv")
    all_codes = set(current["CD_CVM"]) | set(NEW_HISTORICAL_CD_CVM.keys())
    out = {cd: _consolidated_sector(sector_by_code.get(cd, "Desconhecido")) for cd in all_codes}
    return pd.Series(out, name="setor")


def clustered_ols(df: pd.DataFrame, controls: list[str], with_sector: bool) -> tuple[float, int, int]:
    cols = ["abnormal_return", "cosine_similarity", "cd_cvm"] + controls + (["setor"] if with_sector else [])
    have = df.dropna(subset=cols)
    formula = "abnormal_return ~ cosine_similarity" + "".join(f" + {c}" for c in controls)
    if with_sector:
        formula += " + C(setor)"
    model = smf.ols(formula, data=have).fit(cov_type="cluster", cov_kwds={"groups": have["cd_cvm"]})
    n_sectors = have["setor"].nunique() if with_sector else 0
    return model.pvalues["cosine_similarity"], len(have), n_sectors


def main() -> None:
    sector_map = build_sector_map()
    print(f"{sector_map.nunique()} sectors (consolidated) across {len(sector_map)} companies")
    print(sector_map.value_counts().to_string())
    print()

    df = pd.read_csv(POC / "abnormal_returns_poc.csv")
    df["setor"] = df["cd_cvm"].map(sector_map)
    ctrl = pd.read_csv(INTERIM / "control_variables.csv").rename(columns={"CD_CVM": "cd_cvm", "fiscal_year": "ctrl_year"})
    df = df.merge(ctrl, left_on=["cd_cvm", "year_curr"], right_on=["cd_cvm", "ctrl_year"], how="left")

    rows = []
    for label, controls, with_sector in [
        ("Agrup., s/c (atual)", [], False),
        ("Agrup., s/c + setor", [], True),
        ("Agrup., c/c (atual)", CONTROLS, False),
        ("Agrup., c/c + setor", CONTROLS, True),
    ]:
        p, n, n_sec = clustered_ols(df, controls, with_sector)
        rows.append({"Especificação": label, "n": n, "setores": n_sec if n_sec else "-", "p-valor": round(p, 4)})

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    out.to_csv(POC / "sector_control_test.csv", index=False)
    print(f"\nWritten: {POC / 'sector_control_test.csv'}")


if __name__ == "__main__":
    main()
