"""Bridges eval_note_locator's already-built lines_cache (raw PDF lines,
997 DFP + 2915 ITR filings, no re-parsing needed) into the sections/
itr_sections/ cache format run_poc_tfidf.py / run_delisted_analysis.py /
run_itr_tfidf_full.py expect -- so regenerating similarity_results.csv
after a locate_note_section.py change doesn't need a slow full PDF
re-parse, just a fast rerun of the (now-changed) heuristic against
already-extracted lines.

Run this once after any locate_note_section.py change, before rerunning
run_poc_tfidf.py / run_delisted_analysis.py (run_itr_tfidf_full.py already
reads straight from lines_cache and needs no bridge).

Usage:
    python -u -m src.processing.rebuild_sections_cache
"""
from __future__ import annotations

import json
from pathlib import Path

from src.acquisition.b3_ibov_historical import NEW_HISTORICAL_CD_CVM
from src.processing.eval_note_locator import LINES_CACHE, load_cached_bookmarks, load_cached_lines
from src.processing.locate_note_section import locate_note_section
from src.processing.run_poc_tfidf import POC_COMPANIES

SECTIONS_DIR = Path("data/interim/poc/sections")
ITR_SECTIONS_DIR = Path("data/interim/poc/itr_sections")


def main() -> None:
    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    ITR_SECTIONS_DIR.mkdir(parents=True, exist_ok=True)

    name_map = dict(POC_COMPANIES)
    name_map.update({f"{cd:06d}": name for cd, name in NEW_HISTORICAL_CD_CVM.items()})

    n_dfp = n_itr = 0
    for cache_path in sorted(LINES_CACHE.glob("*.json")):
        key = cache_path.stem  # "dfp_002437_2015" or "itr_002437_2015Q1"
        source, rest = key.split("_", 1)
        cd_cvm, period = rest.split("_", 1)

        lines = load_cached_lines(key)
        bookmarks = load_cached_bookmarks(key) if source == "dfp" else None
        section = locate_note_section(lines, bookmarks=bookmarks)
        name = name_map.get(cd_cvm, "")

        if source == "dfp":
            year = int(period)
            out = {
                "cd_cvm": cd_cvm, "name": name, "year": year,
                "diagnostic": section.diagnostic, "heading": section.heading,
                "n_total_lines": len(lines), "text": section.text,
            }
            (SECTIONS_DIR / f"{cd_cvm}_{year}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            n_dfp += 1
        else:
            out = {
                "cd_cvm": cd_cvm, "name": name, "quarter": period,
                "diagnostic": section.diagnostic, "heading": section.heading,
                "n_total_lines": len(lines), "text": section.text,
            }
            (ITR_SECTIONS_DIR / f"{cd_cvm}_{period}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            n_itr += 1

    print(f"Rebuilt {n_dfp} DFP + {n_itr} ITR section caches from lines_cache.")


if __name__ == "__main__":
    main()
