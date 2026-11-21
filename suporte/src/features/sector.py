"""Company -> consolidated CVM sector (SETOR_ATIV) map.

Moved here from src/analysis/test_sector_control.py, which went to
exploracao/ in the September 2026 reorganization while run_m0_m5_grid.py
(and every M0-M3 script that imports from it) still depended on this
function.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"

# A few sectors appear under two slightly different spellings in CVM's own
# cadastral data (abbreviated vs. full, or a stray case difference).
# Left unmapped means "keep as-is".
_SECTOR_ALIASES = {
    "Const. Civil, Mat. Const. e Decoração": "Construção Civil, Mat. Constr. e Decoração",
    "Serviços médicos": "Serviços Médicos",
    "Máqs., Equip., Veíc. e Peças": "Máquinas, Equipamentos, Veículos e Peças",
}


def _consolidated_sector(raw: str) -> str:
    """Strips the "Emp. Adm. Part. - " (holding company) prefix so a
    holding company is grouped with operating companies in the same
    sector, then folds in the known aliases above."""
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
