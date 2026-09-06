"""Acquires the "Relatório da Administração" (Management Report) for every
company-year already in the annual corpus -- Brazil's closest regulatory
equivalent to the US MD&A. See reports/return_predictability_exploration.md
for why this is worth acquiring (the cited return-predictability literature
finds its strongest effects in high-managerial-discretion text like MD&A,
not audited/formulaic footnotes) and
reports/management_report_acquisition.md for what was found running this.

Zero new downloads: every filing's zip is already cached locally (fetched
for the debt-note acquisition), so this only re-processes those cached
zips with a different attachment-selection target.

Unlike the debt-note pipeline, which keeps exactly one "best" attachment,
this checks *every* attachment in the filing (a company may file the
Management Report as its own attachment even when the statements/notes
pipeline picked a different one as "largest" or "notes-matching") --
confirmed necessary by direct inspection: filename-matching alone only
found the report in ~13% of a sample, but many filings that don't name it
explicitly still have it as a distinct attachment once every attachment is
actually opened and checked, not just the one already selected for other
purposes.

Selection order per filing:
  1. An attachment whose filename matches "relatório...administração".
  2. An attachment whose first page's text matches the same pattern (a
     dedicated attachment that just isn't obviously named -- confirmed
     happens in legacy-era filings with opaque temp-file names).
  3. Not found -- recorded as such, not silently skipped, so coverage
     gaps are visible rather than assumed away.

Usage:
    python -u -m src.acquisition.cvm_management_report
"""
from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import fitz  # pymupdf
import pandas as pd

from src.acquisition.cvm_notes import FilingAttachment, download_filing_zip, list_attachments, _strip_accents

warnings.filterwarnings("ignore")

CACHE_DIR = Path("data/raw/dfp/_cache")
OUT_ROOT = Path("data/raw/dfp_mgmt_report")

FILENAME_RE = re.compile(r"(?i)relat[oó]rio.{0,15}administra[cç][aã]o")
CONTENT_RE = re.compile(r"(?i)relat[óo]rio\s+d[ae]\s+administra[çc][ãa]o")


def _matches_filename(att: FilingAttachment) -> bool:
    return bool(FILENAME_RE.search(_strip_accents(att.filename)))


CONTENT_MATCH_MAX_PAGES = 15  # see docstring below for why this isn't just 1-2


def _first_page_matches(att: FilingAttachment) -> bool:
    """Checks the first CONTENT_MATCH_MAX_PAGES pages, not just the first
    two. Widened after a corpus-wide check of the ~326 "not_found"
    company-years found that ~11% of them do have a "Relatório da
    Administração" heading somewhere in an already-acquired attachment --
    just past a cover page, index, or a message-from-the-board section that
    pushes the real heading beyond page 2 (confirmed: hits cluster around
    page 3, with a longer tail out to page 8 for reports embedded inside a
    larger combined financial-statements bundle). No new download or
    matching logic needed, only a wider read of the same already-cached
    attachment.
    """
    try:
        doc = fitz.open(stream=att.pdf_bytes, filetype="pdf")
        text = "".join(p.get_text() for p in doc[:CONTENT_MATCH_MAX_PAGES])
        return bool(CONTENT_RE.search(text))
    except Exception:
        return False


def select_management_report(attachments: list[FilingAttachment]) -> tuple[FilingAttachment | None, str]:
    by_filename = [a for a in attachments if _matches_filename(a)]
    if by_filename:
        # prefer the smallest such match (a dedicated report is much
        # shorter than a combined package that also happens to mention it)
        return min(by_filename, key=lambda a: len(a.pdf_bytes)), "filename_match"

    for att in attachments:
        if _first_page_matches(att):
            return att, "content_match"

    return None, "not_found"


def save_company_year_management_report(cd_cvm: str, ano: int, id_doc: str, out_root: Path, force: bool = False) -> dict:
    cd_cvm = str(cd_cvm)
    ano = int(ano)
    id_doc = str(id_doc)

    out_dir = out_root / cd_cvm / str(ano)
    result = {"CD_CVM": cd_cvm, "ANO": ano, "ID_DOC": id_doc, "found": False, "tier": None, "files": []}

    zip_bytes = download_filing_zip(id_doc, CACHE_DIR, force=force)
    attachments = list_attachments(zip_bytes)
    match, tier = select_management_report(attachments)
    result["tier"] = tier
    if match is None:
        return result

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "relatorio_administracao.pdf"
    out_path.write_bytes(match.pdf_bytes)
    result["found"] = True
    result["files"].append({"path": str(out_path), "original_filename": match.filename, "size_bytes": len(match.pdf_bytes)})
    (out_dir / "attachment_meta.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main() -> None:
    log = pd.concat([
        pd.read_csv("data/interim/ibov_notes_download_log.csv"),
        pd.read_csv("data/interim/ibov_historical_notes_download_log.csv"),
    ], ignore_index=True)
    log = log[log["n_attachments_matched"] > 0].dropna(subset=["ID_DOC"])
    log["ID_DOC"] = log["ID_DOC"].astype(int)

    rows = []
    for i, row in enumerate(log.itertuples(index=False), start=1):
        try:
            result = save_company_year_management_report(row.CD_CVM, row.ANO, row.ID_DOC, OUT_ROOT)
        except Exception as exc:
            result = {"CD_CVM": str(row.CD_CVM), "ANO": int(row.ANO), "ID_DOC": str(row.ID_DOC), "found": False, "tier": "error", "files": [], "error": str(exc)}
        result["DENOM_CIA"] = row.DENOM_CIA
        rows.append(result)
        if i % 100 == 0 or i == len(log):
            found_so_far = sum(1 for r in rows if r["found"])
            print(f"[{i}/{len(log)}] {found_so_far} found so far")

    out_csv = Path("data/interim/management_report_acquisition_log.csv")
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    n_found = sum(1 for r in rows if r["found"])
    tier_counts = pd.Series([r["tier"] for r in rows]).value_counts()
    print(f"\n{n_found}/{len(rows)} ({n_found/len(rows):.1%}) management reports found")
    print(tier_counts.to_string())
    print(f"\nLog: {out_csv}")


if __name__ == "__main__":
    main()
