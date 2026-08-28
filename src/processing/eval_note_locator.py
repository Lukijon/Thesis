"""Iteration harness for tuning `locate_note_section.py` against the full
acquired corpus without re-parsing PDFs on every heuristic change.

PDF text/layout extraction (`extract_lines`) is the expensive step (I/O +
per-page layout parsing); `locate_note_section` itself is cheap, pure-Python
logic over already-extracted lines. This splits the two: `build_lines_cache`
extracts once and caches raw lines per company-year/quarter; `evaluate`
reloads from that cache and reruns just the heuristic, so a locate_note_section
change can be measured against the whole corpus in seconds, not minutes.

Usage:
    python -m src.processing.eval_note_locator build   # one-time, slow
    python -m src.processing.eval_note_locator eval     # fast, rerun after each change
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from src.processing.locate_note_section import locate_note_section
from src.processing.pdf_text import Line, extract_bookmarks, extract_lines, lines_to_dicts

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LINES_CACHE = Path("data/interim/poc/lines_cache")
BOOKMARKS_CACHE = Path("data/interim/poc/bookmarks_cache")
DFP_ROOT = Path("data/raw/dfp")
ITR_ROOT = Path("data/raw/itr")


def _corpus_pdfs() -> list[tuple[str, Path]]:
    """(cache_key, pdf_path) for every acquired notas_explicativas.pdf,
    annual (DFP) and quarterly (ITR) both -- cache_key encodes source+company+period
    so annual/quarterly never collide.
    """
    items = []
    for pdf_path in sorted(DFP_ROOT.glob("*/*/notas_explicativas.pdf")):
        cd_cvm, period = pdf_path.parts[-3], pdf_path.parts[-2]
        items.append((f"dfp_{cd_cvm}_{period}", pdf_path))
    for pdf_path in sorted(ITR_ROOT.glob("*/*/notas_explicativas.pdf")):
        cd_cvm, period = pdf_path.parts[-3], pdf_path.parts[-2]
        items.append((f"itr_{cd_cvm}_{period}", pdf_path))
    return items


def _extract_one(key_and_path: tuple[str, Path]) -> tuple[str, int, str | None]:
    key, pdf_path = key_and_path
    try:
        lines = extract_lines(pdf_path)
        (LINES_CACHE / f"{key}.json").write_text(
            json.dumps(lines_to_dicts(lines), ensure_ascii=False), encoding="utf-8"
        )
        return key, len(lines), None
    except Exception as exc:  # noqa: BLE001 - report and move on, one bad PDF shouldn't kill the batch
        return key, 0, str(exc)


def build_lines_cache(force: bool = False, workers: int = 8) -> None:
    """CPU-bound (per-page layout parsing, no network), so this parallelizes
    well across processes -- worth it given the corpus is ~1000+ filings.
    """
    LINES_CACHE.mkdir(parents=True, exist_ok=True)
    items = _corpus_pdfs()
    todo = [(key, path) for key, path in items if force or not (LINES_CACHE / f"{key}.json").exists()]
    print(f"{len(items)} filings total, {len(todo)} to process")
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_extract_one, item) for item in todo]
        for fut in as_completed(futures):
            key, n_lines, error = fut.result()
            done += 1
            if error:
                print(f"  [{done}/{len(todo)}] ERROR {key}: {error}")
            elif done % 50 == 0 or done == len(todo):
                print(f"  [{done}/{len(todo)}] {key} ({n_lines} lines)")
    print("done")


def load_cached_lines(key: str) -> list[Line]:
    data = json.loads((LINES_CACHE / f"{key}.json").read_text(encoding="utf-8"))
    return [Line(**d) for d in data]


def build_bookmarks_cache(force: bool = False) -> None:
    """Separate from build_lines_cache: doc.get_toc() doesn't need per-page
    text/layout parsing, so this is fast and can run independently of the
    (slow) lines-cache build.
    """
    BOOKMARKS_CACHE.mkdir(parents=True, exist_ok=True)
    items = _corpus_pdfs()
    print(f"{len(items)} filings to process")
    for i, (key, pdf_path) in enumerate(items, start=1):
        cache_path = BOOKMARKS_CACHE / f"{key}.json"
        if cache_path.exists() and not force:
            continue
        try:
            bookmarks = extract_bookmarks(pdf_path)
        except Exception:
            bookmarks = []
        cache_path.write_text(json.dumps(bookmarks, ensure_ascii=False), encoding="utf-8")
        if i % 100 == 0 or i == len(items):
            print(f"  [{i}/{len(items)}] cached")
    print("done")


def load_cached_bookmarks(key: str) -> list[tuple[int, str, int]]:
    cache_path = BOOKMARKS_CACHE / f"{key}.json"
    if not cache_path.exists():
        return []
    return json.loads(cache_path.read_text(encoding="utf-8"))


def evaluate(subset: str = "all", use_bookmarks: bool = True) -> dict:
    """Rerun the current locate_note_section against every cached filing and
    tabulate the diagnostic breakdown. `subset`: "all" | "dfp" | "itr".
    """
    counts = {"font_heading": 0, "regex_only": 0, "not_found": 0}
    total = 0
    per_key_diag = {}
    for cache_path in sorted(LINES_CACHE.glob("*.json")):
        key = cache_path.stem
        if subset == "dfp" and not key.startswith("dfp_"):
            continue
        if subset == "itr" and not key.startswith("itr_"):
            continue
        lines = load_cached_lines(key)
        bookmarks = load_cached_bookmarks(key) if use_bookmarks else None
        section = locate_note_section(lines, bookmarks=bookmarks)
        counts[section.diagnostic] += 1
        total += 1
        per_key_diag[key] = section.diagnostic

    print(f"subset={subset}  total={total}")
    for diag in ("font_heading", "regex_only", "not_found"):
        n = counts[diag]
        print(f"  {diag:14s} {n:4d}/{total}  ({n/total:.1%})")
    return {"counts": counts, "total": total, "per_key_diag": per_key_diag}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "eval"
    if cmd == "build":
        build_lines_cache()
    elif cmd == "build_bookmarks":
        build_bookmarks_cache()
    else:
        subset = sys.argv[2] if len(sys.argv) > 2 else "all"
        evaluate(subset)
