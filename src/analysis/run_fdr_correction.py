"""Formal multiple-testing correction (feedback items 2.8/5.5), applied to
the confirmatory family only: the 9 principal-specification (M2) p-values
across H1 (5 text sources, m0_m3_all_sources_results.csv) and H2 (4 text
sources, h2_m0_m3_results.csv). M0/M1/M3 are not included -- they are
cumulative robustness variants of the same per-source coefficient, not
independent hypotheses, so correcting all 36 M0-M3 cells together would
misrepresent the family BH assumes. Exploratory checks (delisting,
Santos-Coelho comparison, portfolio sort, H2's secondary tercile/delisting
battery) are deliberately excluded too -- they are already labeled and
interpreted as exploratory in the text (Secao 5.9's "separar confirmatorio
de exploratorio"), which is the appropriate response to their multiplicity,
not a formal correction meant for a pre-specified confirmatory family.

Usage:
    python -m src.analysis.run_fdr_correction
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"


def main() -> None:
    h1 = pd.read_csv(POC / "m0_m3_all_sources_results.csv")
    h1 = h1[h1["Modelo"] == "M2"][["Fonte", "p"]].assign(hipotese="H1")

    h2 = pd.read_csv(POC / "h2_m0_m3_results.csv")
    h2 = h2[h2["Modelo"] == "M2"][["Fonte", "p"]].assign(hipotese="H2")

    combined = pd.concat([h1, h2], ignore_index=True)
    rejected, p_adj, _, _ = multipletests(combined["p"], alpha=0.05, method="fdr_bh")
    combined["p_adj_bh"] = p_adj
    combined["rejected_5pct"] = rejected
    combined = combined.sort_values("p").reset_index(drop=True)

    print(combined.to_string(index=False))
    print(f"\nn testes na familia confirmatoria: {len(combined)}")
    print(f"menor p bruto: {combined['p'].min():.4f}  ->  menor p ajustado (BH): {combined['p_adj_bh'].min():.4f}")
    print(f"rejeicoes a 5% apos correcao: {combined['rejected_5pct'].sum()}")

    out_path = POC / "fdr_correction_confirmatory.csv"
    combined.to_csv(out_path, index=False)
    print(f"\nWritten: {out_path}")


if __name__ == "__main__":
    main()
