"""Runs whole-document TF-IDF for Relatorio da Administracao and Risk
Factors over the full round-7 expanded corpus (185 companies, 2010-2025),
mirroring what run_full_history_tfidf.py already did for the narrow debt
note and what f19da2b's inline script did for whole_notes.

Reuses build_mgmt_report_corpus.py / build_risk_factors_corpus.py's
functions UNCHANGED (their _corpus_pdfs() globs already cover the extended
PDFs on disk -- run_management_report_extension.py and
run_risk_factors_extension.py wrote into the same RAW_ROOT as the original
acquisition, per their own docstrings). Only the output path differs, to
avoid overwriting the thesis's own input files
(mgmt_report_similarity_results.csv, risk_factors_similarity_results.csv).

Usage:
    python -u -m src.processing.run_alt_sources_full_history_tfidf
"""
from __future__ import annotations

from pathlib import Path

from src.processing import build_mgmt_report_corpus as mgmt
from src.processing import build_risk_factors_corpus as risk

POC = Path("data/interim/poc")


def run_source(mod, out_name: str) -> None:
    print(f"=== {out_name} ===")
    print("Building lines cache...")
    mod.build_lines_cache()

    print("Loading extracted text...")
    docs = mod.load_texts()
    n_total = len(docs)
    n_found = (docs["text"].str.len() > 100).sum()
    print(f"{n_found}/{n_total} filings with substantive text (>100 chars)")

    print("Computing TF-IDF cosine similarities...")
    results = mod.compute_similarities(docs)
    out_path = POC / out_name
    results.to_csv(out_path, index=False)
    print(f"{len(results)} year-over-year pairs, {results['cd_cvm'].nunique()} companies -> {out_path}\n")


def main() -> None:
    run_source(mgmt, "mgmt_report_similarity_results_full_history.csv")
    run_source(risk, "risk_factors_similarity_results_full_history.csv")


if __name__ == "__main__":
    main()
