"""Extracts raw text from every acquired Relatório da Administração PDF
(src/acquisition/cvm_management_report.py) and computes year-over-year
TF-IDF cosine similarity, mirroring run_full_notes_tfidf.py's approach for
the whole notes document -- same measure, same corpus-wide IDF fit, applied
to a different text source. See
reports/return_predictability_exploration.md for why.

Usage:
    python -m src.processing.build_mgmt_report_corpus
"""
from __future__ import annotations

import json
import re
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.processing.pdf_text import extract_lines, lines_to_dicts

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAW_ROOT = Path("data/raw/dfp_mgmt_report")
LINES_CACHE = Path("data/interim/poc/mgmt_report_lines_cache")
POC_INTERIM = Path("data/interim/poc")
RESULTS_CSV = POC_INTERIM / "mgmt_report_similarity_results.csv"


def _corpus_pdfs() -> list[tuple[str, int, int, Path]]:
    items = []
    for pdf_path in sorted(RAW_ROOT.glob("*/*/relatorio_administracao.pdf")):
        cd_cvm, year = pdf_path.parts[-3], int(pdf_path.parts[-2])
        items.append((f"{cd_cvm}_{year}", int(cd_cvm), year, pdf_path))
    return items


def _extract_one(item: tuple[str, int, int, Path]) -> tuple[str, int, str | None]:
    key, _, _, pdf_path = item
    cache_path = LINES_CACHE / f"{key}.json"
    if cache_path.exists():
        return key, 0, None
    try:
        lines = extract_lines(pdf_path)
        cache_path.write_text(json.dumps(lines_to_dicts(lines), ensure_ascii=False), encoding="utf-8")
        return key, len(lines), None
    except Exception as exc:  # noqa: BLE001
        return key, 0, str(exc)


def build_lines_cache(workers: int = 8) -> None:
    LINES_CACHE.mkdir(parents=True, exist_ok=True)
    items = _corpus_pdfs()
    todo = [it for it in items if not (LINES_CACHE / f"{it[0]}.json").exists()]
    print(f"{len(items)} PDFs total, {len(todo)} to extract")
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_extract_one, it) for it in todo]
        for fut in as_completed(futures):
            key, n_lines, error = fut.result()
            done += 1
            if error:
                print(f"  [{done}/{len(todo)}] ERROR {key}: {error}")
            elif done % 100 == 0 or done == len(todo):
                print(f"  [{done}/{len(todo)}] {key} ({n_lines} lines)")


def _clean_for_tfidf(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\d.,%]+", " NUM ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_texts() -> pd.DataFrame:
    rows = []
    for key, cd_cvm, year, _ in _corpus_pdfs():
        cache_path = LINES_CACHE / f"{key}.json"
        if not cache_path.exists():
            continue
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        text = "\n".join(d["text"] for d in data)
        rows.append({"cd_cvm": cd_cvm, "year": year, "text": text, "chars": len(text), "n_lines": len(data)})
    return pd.DataFrame(rows)


def compute_similarities(docs: pd.DataFrame) -> pd.DataFrame:
    docs = docs[docs["text"].str.len() > 100].reset_index(drop=True).copy()
    docs["clean_text"] = docs["text"].apply(_clean_for_tfidf)

    vectorizer = TfidfVectorizer(max_df=0.85, min_df=2, max_features=50000)
    tfidf_matrix = vectorizer.fit_transform(docs["clean_text"])

    results = []
    for cd_cvm, group in docs.groupby("cd_cvm"):
        group = group.sort_values("year")
        positions = group.index.tolist()
        years = group["year"].tolist()
        for i in range(1, len(positions)):
            sim = cosine_similarity(tfidf_matrix[positions[i - 1]], tfidf_matrix[positions[i]])[0, 0]
            results.append({
                "cd_cvm": cd_cvm, "year_prev": years[i - 1], "year_curr": years[i],
                "cosine_similarity": round(float(sim), 4),
                "chars_prev": int(group["chars"].iloc[i - 1]), "chars_curr": int(group["chars"].iloc[i]),
            })
    return pd.DataFrame(results)


def main() -> None:
    print("Building lines cache...")
    build_lines_cache()

    print("\nLoading extracted text...")
    docs = load_texts()
    n_total = len(docs)
    n_found = (docs["text"].str.len() > 100).sum()
    print(f"{n_found}/{n_total} management reports with substantive text (>100 chars)")

    print("\nComputing TF-IDF cosine similarities...")
    results = compute_similarities(docs)
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_CSV, index=False)

    print(f"\n{len(results)} year-over-year pairs computed.")
    print(results["cosine_similarity"].describe())
    print(f"\nResults: {RESULTS_CSV}")


if __name__ == "__main__":
    main()
