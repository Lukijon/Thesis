"""Fetch a company's full DFP filing package from CVM's RAD system and pull
out the PDF attachment that contains the "notas explicativas" (explanatory
notes) -- either an isolated notes file or, when a company doesn't split
one out, the full financial-statements document the notes are embedded in.

The filing package is a ZIP containing a large XML
(`XmlDemonstracoesFinanceiras`) whose
`XmlDemonstracoesFinanceirasDadosDFPAnexoDocumento` elements each embed one
attached PDF as base64 (e.g. "Relatorio da Administracao", "Notas
Explicativas", "Quadro de Projecoes", or just "DFP 2023_Empresa.pdf").
Decoding these individually is more reliable than the single combined PDF
also present in the package, which in practice can be truncated by
intermediate proxies for large filers.

Attachment naming isn't standardized across companies, so selection is
tiered (see `select_source_attachments`):
  1. filename explicitly says "notas explicativas" (isolated notes file)
  2. filename says "demonstracoes financeiras" / "dfp" (full statements,
     notes included -- confirmed by inspection: e.g. Ambev names its whole
     package "DFP 2023_Ambev SA.pdf" with no separate notes file)
  3. fallback: the largest PDF attachment, which empirically is the full
     statements document (report/press-release/board-minutes attachments
     are consistently smaller)
The tier used is recorded in the output metadata for later QC.
"""
from __future__ import annotations

import base64
import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from src.utils.http import get_bytes

FILING_URL = "https://www.rad.cvm.gov.br/ENETCONSULTA/frmDownloadDocumento.aspx?CodigoInstituicao=1&NumeroSequencialDocumento={id_doc}"

ATTACHMENT_TAG = "XmlDemonstracoesFinanceirasDadosDFPAnexoDocumento"


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def looks_like_notes_attachment(filename: str) -> bool:
    normalized = _strip_accents(filename).lower()
    return "nota" in normalized and "explicativ" in normalized


def looks_like_statements_attachment(filename: str) -> bool:
    normalized = _strip_accents(filename).lower()
    if "demonstra" in normalized and "financeir" in normalized:
        return True
    if re.search(r"\bdfp\b", normalized) is not None:
        return True
    # "Minuta" (draft) is a common attachment name for the full statements
    # package when a company doesn't isolate a separately named notes file.
    return "minuta" in normalized


# Attachment types that are never the financial statements, used to keep the
# largest-attachment fallback from grabbing one of these instead (e.g. a
# Management Report is often bigger than a shorter "Minuta" statements draft).
NON_STATEMENT_KEYWORDS = [
    "relatorio da administracao",
    "administracao",
    "projec",
    "parecer",
    "care",
    "sustentabil",
    "comentarios",
    "ata de reuniao",
]


def looks_like_non_statement_attachment(filename: str) -> bool:
    normalized = _strip_accents(filename).lower()
    return any(kw in normalized for kw in NON_STATEMENT_KEYWORDS)


@dataclass
class FilingAttachment:
    filename: str
    pdf_bytes: bytes


def _looks_like_zip(data: bytes) -> bool:
    return data[:2] == b"PK"


def download_filing_zip(id_doc: str, cache_dir: Path, force: bool = False) -> bytes:
    url = FILING_URL.format(id_doc=id_doc)
    return get_bytes(
        url,
        cache_dir / f"{id_doc}.zip",
        force=force,
        timeout=180,
        validate=_looks_like_zip,
        min_interval=2.0,
        pace_key="rad_cvm_filing",
    )


LEGACY_ATTACHMENT_TAG = "AnexoDocumento"


def _parse_attachments(xml_bytes: bytes, tag: str, nested: bool) -> list[FilingAttachment]:
    root = ElementTree.fromstring(xml_bytes)
    attachments = []
    for node in root.iter(tag):
        # Modern format: NomeArquivoPdf/ImagemObjetoArquivoPdf are direct
        # children. Legacy format nests them one level deeper, under
        # <Documento>, so search recursively there instead.
        name_el = node.find(".//NomeArquivoPdf" if nested else "NomeArquivoPdf")
        data_el = node.find(".//ImagemObjetoArquivoPdf" if nested else "ImagemObjetoArquivoPdf")
        if name_el is None or data_el is None or not data_el.text:
            continue
        attachments.append(
            FilingAttachment(filename=name_el.text, pdf_bytes=base64.b64decode(data_el.text))
        )
    return attachments


def list_attachments(zip_bytes: bytes) -> list[FilingAttachment]:
    """Every PDF attachment embedded in the filing package, decoded.

    Filings from roughly 2021 onward carry a single top-level XML
    (`XmlDemonstracoesFinanceiras`) with the attachments inline. Older
    filings package them differently: a `.dfp` file that is itself a ZIP,
    containing `AnexoDocumento.xml` with the same idea but a different
    tag/nesting -- and legacy attachment names are opaque internal temp
    paths (e.g. "C:\\EMPRESASNET\\...\\00121604120000000000000000.pdf.pdf"),
    not descriptive names, so downstream selection falls back to picking
    the largest one rather than matching by filename.
    """
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        modern_candidates = [
            n
            for n in zf.namelist()
            if n.lower().endswith(".xml") and n not in ("FormularioCadastral.xml", "FormularioDemonstracaoFinanceiraDFP.xml")
        ]
        if modern_candidates:
            xml_name = max(modern_candidates, key=lambda n: zf.getinfo(n).file_size)
            return _parse_attachments(zf.read(xml_name), ATTACHMENT_TAG, nested=False)

        legacy_candidates = [n for n in zf.namelist() if n.lower().endswith(".dfp")]
        if legacy_candidates:
            with zipfile.ZipFile(BytesIO(zf.read(legacy_candidates[0]))) as inner_zf:
                if "AnexoDocumento.xml" in inner_zf.namelist():
                    return _parse_attachments(inner_zf.read("AnexoDocumento.xml"), LEGACY_ATTACHMENT_TAG, nested=True)

    raise FileNotFoundError("No recognized DFP attachment structure (neither modern nor legacy) found in filing package")


def select_source_attachments(attachments: list[FilingAttachment]) -> tuple[list[FilingAttachment], str]:
    """Pick the attachment(s) most likely to contain the debt note, per the
    tiered strategy described in the module docstring. Returns the matches
    plus which tier resolved them, for QC.
    """
    notes = [a for a in attachments if looks_like_notes_attachment(a.filename)]
    if notes:
        return notes, "notes_filename_match"

    statements = [a for a in attachments if looks_like_statements_attachment(a.filename)]
    if statements:
        return statements, "statements_filename_match"

    fallback_pool = [a for a in attachments if not looks_like_non_statement_attachment(a.filename)] or attachments
    if fallback_pool:
        return [max(fallback_pool, key=lambda a: len(a.pdf_bytes))], "largest_attachment_fallback"

    return [], "no_attachments"


def extract_notes_pdf(id_doc: str, cache_dir: Path, force: bool = False) -> tuple[list[FilingAttachment], str]:
    """Attachment(s) from this filing likely to contain the debt note, plus
    the selection tier used (see `select_source_attachments`).
    """
    zip_bytes = download_filing_zip(id_doc, cache_dir, force=force)
    return select_source_attachments(list_attachments(zip_bytes))


def save_company_year_notes(cd_cvm: str, ano: int, id_doc: str, cache_dir: Path, out_root: Path, force: bool = False) -> dict:
    """Download the filing, extract the attachment(s) likely to contain the
    debt note, and save them under ``out_root/{cd_cvm}/{ano}/``. Returns a
    metadata dict for logging.
    """
    # Callers commonly pass pandas/numpy row values (e.g. numpy.int64 for a
    # year); normalize to plain Python types so the metadata is JSON-safe.
    cd_cvm = str(cd_cvm)
    ano = int(ano)
    id_doc = str(id_doc)

    out_dir = out_root / cd_cvm / str(ano)
    matches, tier = extract_notes_pdf(id_doc, cache_dir, force=force)

    result = {
        "CD_CVM": cd_cvm,
        "ANO": ano,
        "ID_DOC": id_doc,
        "n_attachments_matched": len(matches),
        "match_tier": tier,
        "files": [],
    }

    if not matches:
        return result

    out_dir.mkdir(parents=True, exist_ok=True)
    for i, attachment in enumerate(matches):
        suffix = "" if i == 0 else f"_{i}"
        out_path = out_dir / f"notas_explicativas{suffix}.pdf"
        out_path.write_bytes(attachment.pdf_bytes)
        result["files"].append({"path": str(out_path), "original_filename": attachment.filename, "size_bytes": len(attachment.pdf_bytes)})

    (out_dir / "attachment_meta.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
