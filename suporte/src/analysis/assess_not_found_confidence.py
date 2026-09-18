"""For every "not_found" annual (DFP) company-year -- the note-locator
never matched a qualifying debt keyword anywhere in the filing -- looks up
the company's actual "Empréstimos e Financiamentos" balance-sheet line
(CVM's own structured chart of accounts, CD_CONTA "2.01.04" current +
"2.02.01" non-current, which already includes debêntures as a sub-account
of the same parent line -- confirmed by direct inspection before trusting
it) to assess whether the note plausibly doesn't exist at all (balance is
zero or negligible) versus the note likely exists and was simply missed by
the extraction heuristic (a real, non-trivial balance is on the books).

This replaces the cruder proxy used earlier (aggregate leverage, which
mixes debt with every other liability) with the one CVM field that
directly answers the question.

Usage:
    python -u -m src.analysis.assess_not_found_confidence
"""
from __future__ import annotations

import warnings
import zipfile
from pathlib import Path

import pandas as pd

from src.processing.eval_note_locator import evaluate, load_cached_lines

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "raw" / "dfp" / "_cache"
INTERIM = ROOT / "data" / "interim"
POC = INTERIM / "poc"

DEBT_CODES = {"2.01.04", "2.02.01"}  # Empréstimos e Financiamentos, current + non-current
ASSET_CODE = "1"  # Ativo Total, for a materiality ratio


def _load_bpp(year: int, consolidation: str) -> pd.DataFrame | None:
    zip_path = CACHE_DIR / f"dfp_cia_aberta_{year}.zip"
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path) as zf:
        name = f"dfp_cia_aberta_BPP_{consolidation}_{year}.csv"
        if name not in zf.namelist():
            return None
        with zf.open(name) as f:
            return pd.read_csv(f, sep=";", encoding="latin1", dtype=str)


def _load_bpa(year: int, consolidation: str) -> pd.DataFrame | None:
    zip_path = CACHE_DIR / f"dfp_cia_aberta_{year}.zip"
    if not zip_path.exists():
        return None
    with zipfile.ZipFile(zip_path) as zf:
        name = f"dfp_cia_aberta_BPA_{consolidation}_{year}.csv"
        if name not in zf.namelist():
            return None
        with zf.open(name) as f:
            return pd.read_csv(f, sep=";", encoding="latin1", dtype=str)


def _debt_and_assets(cd_cvm_padded: str, year: int) -> tuple[float | None, float | None, str]:
    """Returns (debt_value, total_assets, source) trying consolidated
    first, falling back to individual -- the same preference order already
    established in build_control_variables.py."""
    for consolidation in ("con", "ind"):
        bpp = _load_bpp(year, consolidation)
        if bpp is None:
            continue
        sub = bpp[bpp["CD_CVM"] == cd_cvm_padded]
        if sub.empty:
            continue
        debt_rows = sub[sub["CD_CONTA"].isin(DEBT_CODES)].drop_duplicates("CD_CONTA")
        if debt_rows.empty:
            continue
        debt_value = pd.to_numeric(debt_rows["VL_CONTA"], errors="coerce").sum()

        bpa = _load_bpa(year, consolidation)
        total_assets = None
        if bpa is not None:
            asub = bpa[(bpa["CD_CVM"] == cd_cvm_padded) & (bpa["CD_CONTA"] == ASSET_CODE)]
            if not asub.empty:
                total_assets = pd.to_numeric(asub["VL_CONTA"].iloc[0], errors="coerce")
        return debt_value, total_assets, consolidation
    return None, None, "não encontrado"


def classify(debt_value: float | None, total_assets: float | None, n_chars: int) -> tuple[str, str]:
    """Returns (confiança de que a nota genuinamente não existe, motivo)."""
    if n_chars < 200:
        return "indeterminado", "texto extraído quase vazio (provável falha de extração/leitura do PDF, não dá para avaliar)"
    if debt_value is None:
        return "indeterminado", "linha de Empréstimos e Financiamentos não encontrada nos dados estruturados da CVM para essa empresa-ano"
    if debt_value <= 0:
        return "alta", "saldo de Empréstimos e Financiamentos é zero (ou negativo por erro de sinal) nos dados estruturados"
    ratio = debt_value / total_assets if total_assets and total_assets > 0 else None
    if ratio is not None and ratio < 0.001:
        return "moderada-alta", f"saldo positivo mas irrisório (~{ratio:.4%} do ativo total)"
    if ratio is not None and ratio < 0.01:
        return "moderada", f"saldo pequeno em relação ao ativo total (~{ratio:.2%})"
    return "baixa", f"saldo de Empréstimos e Financiamentos é material (~{ratio:.2%} do ativo total)" if ratio else "saldo de Empréstimos e Financiamentos é positivo e não irrisório"


def main() -> None:
    r = evaluate("dfp")
    nf_keys = [k for k, v in r["per_key_diag"].items() if v == "not_found"]
    print(f"{len(nf_keys)} casos not_found (DFP) a avaliar\n")

    rows = []
    for key in nf_keys:
        _, cd, year = key.split("_")
        cd_int = int(cd)
        year_int = int(year)
        cd_padded = f"{cd_int:06d}"

        lines = load_cached_lines(key)
        n_chars = sum(len(l.text) for l in lines)

        debt_value, total_assets, source = _debt_and_assets(cd_padded, year_int)
        confidence, reason = classify(debt_value, total_assets, n_chars)

        rows.append({
            "cd_cvm": cd_int, "ano": year_int, "n_chars_extraidos": n_chars,
            "saldo_emprestimos_financiamentos": debt_value, "ativo_total": total_assets,
            "fonte_dado": source, "confianca_nota_nao_existe": confidence, "motivo": reason,
        })

    out = pd.DataFrame(rows).sort_values(["confianca_nota_nao_existe", "cd_cvm", "ano"])
    out_path = POC / "not_found_confidence_assessment.csv"
    out.to_csv(out_path, index=False)

    print(out["confianca_nota_nao_existe"].value_counts().to_string())
    print()
    print(out[["cd_cvm", "ano", "n_chars_extraidos", "saldo_emprestimos_financiamentos", "confianca_nota_nao_existe", "motivo"]].to_string(index=False))
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
