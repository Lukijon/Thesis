"""Acquire Risk Factors (Formulario de Referencia item 4.1, "Fatores de
Risco") -- the Brazilian near-equivalent of a US 10-K's Item 1A, and the
section Cohen-Malloy-Nguyen's own paper finds the strongest textual-change
effect in (see reports/return_predictability_exploration.md). This is a
genuinely new CVM filing type this project hasn't touched before (FRE, not
DFP/ITR), acquired the same way debt notes and the management report were:
fetch the real filing package from CVM's RAD system and pull the relevant
PDF out of it.

Unlike the debt note (needed a font-heuristic section-locator,
src/processing/locate_note_section.py, because the same heading text shows
up in tables of contents and cross-references) and the management report
(needed to check every attachment in the zip, src/acquisition/
cvm_management_report.py, because it isn't consistently named), Risk
Factors turns out to need neither: CVM's own FRE web form (ENET) already
collects item 4.1 as its own dedicated PDF upload, embedded in the filing
XML at a fixed, unambiguous tag path
(FatoresRisco -> DescricaoFatoresRisco -> ImagemObjetoArquivoPdf, base64-
encoded). Confirmed against two very different filers (a large bank,
Banco do Brasil ID_DOC=128529; a mid-cap company, Cogna ID_DOC=137698)
before trusting this as the general pattern, per this project's established
"verify against real data" discipline.

Three real quirks found and handled here:
  - The FRE filing XML's own declaration claims `encoding="utf-8"` but the
    actual bytes are Latin-1 (e.g. "\xe7\xe3" for "ca" as in "atualizacao")
    -- parsing with the declared encoding raises ET.ParseError. Fixed by
    rewriting the declaration before parsing.
  - Filings are versioned continuously through the year (a company can
    re-file FRE many times -- one filer had 19 versions in 2023 alone,
    mostly administrative updates), unlike DFP's one-shot annual filing.
    `latest_versions` picks the highest VERSAO per (CD_CVM, DT_REFER year)
    as the canonical snapshot for that year, on the reasoning that it's
    the most current/complete statement of that year's risk factors.
  - Same pre/post ~2021 format split already known from DFP
    (src/acquisition/cvm_notes.py's docstring): older filings have no
    "FREWEB" XML; instead there's an opaque `<CD_CVM><...>.fre` file that
    is itself a nested ZIP containing `AnexoDocumento.xml`, a flat list of
    `AnexoDocumento` elements tagged only by an internal CVM form-field
    code (`NumeroQuadroRelacionado`), not a descriptive name -- the exact
    same shape as DFP's legacy `AnexoDocumento` container. Unlike DFP
    (which falls back to "largest attachment" since there's no reliable
    signal), here the risk-factors PDF's own text is *not* distinguishable
    from the neighboring "Risco de Mercado" section's PDF by content alone
    -- both open with identical boilerplate ("O investimento nos valores
    mobiliarios ... envolve a exposicao a determinados riscos"), so
    content-sniffing would pick the wrong one. `NumeroQuadroRelacionado ==
    "805"` is used instead -- confirmed as item 4.1's stable CVM
    form-template code against two unrelated companies (Multiplan,
    ID_DOC=55717; Hypera, ID_DOC=55276) in different industries before
    trusting it as a general rule, not a coincidence.
"""
from __future__ import annotations

import base64
import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

from src.acquisition.cvm_notes import download_filing_zip
from src.utils.http import get_bytes

FRE_INDEX_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{year}.zip"


def load_fre_index(year: int, cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """One row per FRE filing submission (any version) whose reference date
    falls in `year` -- CVM's own per-year bundling, not something derived
    here."""
    raw = get_bytes(
        FRE_INDEX_URL.format(year=year),
        cache_dir / f"fre_cia_aberta_{year}.zip",
        force=force,
    )
    z = zipfile.ZipFile(io.BytesIO(raw))
    inner = f"fre_cia_aberta_{year}.csv"
    return pd.read_csv(io.BytesIO(z.read(inner)), sep=";", encoding="latin1")


def latest_versions(index_df: pd.DataFrame, cd_cvm_filter: set[int] | None = None) -> pd.DataFrame:
    """One row per (CD_CVM, DT_REFER) -- the highest-VERSAO filing, i.e. the
    most recently amended snapshot of that reference year's FRE."""
    df = index_df.copy()
    if cd_cvm_filter is not None:
        df = df[df["CD_CVM"].isin(cd_cvm_filter)]
    df = df.sort_values(["CD_CVM", "DT_REFER", "VERSAO"])
    return df.groupby(["CD_CVM", "DT_REFER"], as_index=False).tail(1)


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


def _parse_fixing_encoding(xml_bytes: bytes) -> ET.Element | None:
    fixed = xml_bytes.replace(b'encoding="utf-8"', b'encoding="ISO-8859-1"', 1)
    try:
        return ET.fromstring(fixed)
    except ET.ParseError:
        return None


def _decode_pdf_field(container, tag_name: str = "ImagemObjetoArquivoPdf") -> bytes | None:
    pdf_field = [c for c in container if _strip_ns(c.tag) == tag_name]
    if not pdf_field or not (pdf_field[0].text or "").strip():
        return None
    try:
        return base64.b64decode(pdf_field[0].text.strip())
    except Exception:
        return None


LEGACY_RISK_FACTORS_QUADRO = "805"


def _extract_modern(z: zipfile.ZipFile) -> bytes | None:
    # Filename convention isn't fully standardized: "001023FREWEB31-12-2023v3.xml"
    # and "017973FRE31-12-2023v16.xml" (no "WEB") both occur -- match "FRE"
    # generally rather than "FREWEB" specifically.
    xml_candidates = [n for n in z.namelist() if n.lower().endswith(".xml") and "fre" in n.lower()]
    if not xml_candidates:
        return None
    root = _parse_fixing_encoding(z.read(xml_candidates[0]))
    if root is None:
        return None
    fr_blocks = [el for el in root.iter() if _strip_ns(el.tag) == "FatoresRisco"]
    if not fr_blocks:
        return None
    desc = [c for c in fr_blocks[0] if _strip_ns(c.tag) == "DescricaoFatoresRisco"]
    if not desc:
        return None
    return _decode_pdf_field(desc[0])


def _extract_legacy(z: zipfile.ZipFile) -> bytes | None:
    fre_candidates = [n for n in z.namelist() if n.lower().endswith(".fre")]
    if not fre_candidates:
        return None
    try:
        inner_zip = zipfile.ZipFile(io.BytesIO(z.read(fre_candidates[0])))
        anexo_bytes = inner_zip.read("AnexoDocumento.xml")
    except (zipfile.BadZipFile, KeyError):
        return None
    root = _parse_fixing_encoding(anexo_bytes)
    if root is None:
        return None
    anexos = [el for el in root.iter() if _strip_ns(el.tag) == "AnexoDocumento"]
    for a in anexos:
        quadro = [c.text for c in a if _strip_ns(c.tag) == "NumeroQuadroRelacionado"]
        if quadro and quadro[0] == LEGACY_RISK_FACTORS_QUADRO:
            return _decode_pdf_field(a)
    return None


def extract_risk_factors_pdf(filing_zip_bytes: bytes) -> bytes | None:
    """Pull the item-4.1 PDF out of an FRE filing package, modern or legacy
    format. Returns None if the filing has no populated risk-factors PDF
    (left blank, or an unrecognized package structure) rather than raising
    -- callers log this as a miss, same convention as
    cvm_management_report.py's select_management_report."""
    z = zipfile.ZipFile(io.BytesIO(filing_zip_bytes))
    result = _extract_modern(z)
    if result is not None:
        return result
    return _extract_legacy(z)


def save_company_year_risk_factors(cd_cvm: int, year: int, id_doc, cache_dir: Path, out_root: Path) -> dict:
    """Mirrors cvm_management_report.save_company_year_management_report's
    return-dict shape for consistency with the rest of the project's
    acquisition logs.

    download_filing_zip's cache validation only checks that a response
    starts with "PK" (src/acquisition/cvm_notes.py's `_looks_like_zip`) --
    cheap, but it lets a response truncated mid-download (a real,
    confirmed failure mode against this endpoint for large filings) get
    cached and trusted. If the cached bytes fail to open as a zip at all,
    retry once with a forced re-download before giving up, rather than
    silently losing that company-year."""
    out_dir = out_root / str(cd_cvm) / str(year)
    out_path = out_dir / "fatores_risco.pdf"
    try:
        filing_zip = download_filing_zip(str(id_doc), cache_dir)
        try:
            zipfile.ZipFile(io.BytesIO(filing_zip))
        except zipfile.BadZipFile:
            filing_zip = download_filing_zip(str(id_doc), cache_dir, force=True)
        pdf_bytes = extract_risk_factors_pdf(filing_zip)
    except Exception as exc:
        return {"CD_CVM": cd_cvm, "ANO": year, "ID_DOC": id_doc, "found": False, "n_bytes": 0, "error": str(exc)}
    if pdf_bytes is None:
        return {"CD_CVM": cd_cvm, "ANO": year, "ID_DOC": id_doc, "found": False, "n_bytes": 0, "error": None}
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pdf_bytes)
    return {"CD_CVM": cd_cvm, "ANO": year, "ID_DOC": id_doc, "found": True, "n_bytes": len(pdf_bytes), "error": None}
