"""ITR (quarterly, "Informações Trimestrais") counterpart to
`cvm_dfp.py`/`cvm_notes.py` -- builds a company/quarter universe from CVM's
open-data ITR index and pulls the debt-note attachment out of each filing.

This is a pilot for testing whether quarterly note text catches a company's
deterioration sooner than the year-over-year annual (DFP) comparison does --
see the round-4 POC discussion. CVM publishes ITR filings for Q1/Q3 plus a
mid-year Q2 update every fiscal year (Q4 is covered by the annual DFP, not
ITR); the fiscal-year-end DT_REFER some companies also submit under ITR
(restatements/amendments) is filtered out below to keep one filing per
company per standard quarter.

Filing-package structure parallels DFP closely but isn't identical --
confirmed by inspection, not assumed:
  - Modern (~2021+) filings embed attachments in a top-level XML, same as
    DFP, but under a different tag: `XmlInformacoesTrimestraisFinanceiras
    DadosITRAnexoDocumento` instead of DFP's `...DadosDFPAnexoDocumento`.
    The cover-form file to exclude when picking the main XML is also named
    differently (`FormularioDemonstracaoFinanceiraITR.xml`).
  - Legacy (pre-2021) filings nest a `.itr` file (not `.dfp`) that is
    itself a ZIP containing `AnexoDocumento.xml` -- but that inner
    structure (tag names, nesting) is identical to DFP's legacy format.
  - Both eras also include a single standalone "combined" PDF directly in
    the outer zip (e.g. `125438_005410_23082026175634.pdf`), same as DFP --
    intentionally not used here, for the same truncation-risk reason
    documented in `cvm_notes.list_attachments`.
`cvm_notes.list_attachments` takes `modern_tag`/`modern_exclude`/
`legacy_extension` params specifically so this module can reuse it rather
than duplicating the parsing logic.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd

from src.acquisition.cvm_dfp import CVM_BASE, is_financial_sector, load_cadastral
from src.acquisition.cvm_notes import download_filing_zip, list_attachments, select_source_attachments
from src.utils.http import get_bytes

ITR_ATTACHMENT_TAG = "XmlInformacoesTrimestraisFinanceirasDadosITRAnexoDocumento"
ITR_MODERN_EXCLUDE = ("FormularioCadastral.xml", "FormularioDemonstracaoFinanceiraITR.xml")
ITR_LEGACY_EXTENSION = ".itr"

# The three standard interim quarter-ends. Fiscal year-end (12-31) and other
# odd DT_REFER values that show up in the raw index are restatements/
# amendments tied to the annual DFP, not real additional quarters.
STANDARD_QUARTER_ENDS = {(3, 31), (6, 30), (9, 30)}


def load_itr_index(year: int, cache_dir: Path, force: bool = False) -> pd.DataFrame:
    """Filing index for one calendar year: one row per company per ITR
    document received by CVM, same schema as `cvm_dfp.load_dfp_index`.
    """
    url = f"{CVM_BASE}/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
    raw = get_bytes(url, cache_dir / f"itr_cia_aberta_{year}.zip", force=force)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        with zf.open(f"itr_cia_aberta_{year}.csv") as f:
            df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str)
    return df


def build_quarterly_universe(
    years: list[int],
    cache_dir: Path,
    force: bool = False,
    cd_cvm_filter: set[int] | None = None,
) -> pd.DataFrame:
    """One row per non-financial company per standard fiscal quarter,
    keeping only the latest filed version (VERSAO) per (CD_CVM, DT_REFER).

    Mirrors `cvm_dfp.build_company_universe`; see that function for the
    non-financial-sector filtering rationale, shared via the same
    `cad_cia_aberta.csv` cadastral file.
    """
    cadastral = load_cadastral(cache_dir, force=force)
    cadastral = cadastral.assign(CD_CVM_INT=cadastral["CD_CVM"].astype(int))
    non_financial_codes = set(
        cadastral.loc[~cadastral["SETOR_ATIV"].apply(is_financial_sector), "CD_CVM_INT"]
    )
    if cd_cvm_filter is not None:
        non_financial_codes &= set(cd_cvm_filter)
    sector_by_code = cadastral.drop_duplicates("CD_CVM_INT").set_index("CD_CVM_INT")["SETOR_ATIV"]

    yearly_frames = []
    for year in years:
        index_df = load_itr_index(year, cache_dir, force=force)
        index_df = index_df[index_df["CATEG_DOC"] == "ITR"]
        index_df = index_df.assign(CD_CVM_INT=index_df["CD_CVM"].astype(int))
        index_df = index_df[index_df["CD_CVM_INT"].isin(non_financial_codes)]
        yearly_frames.append(index_df)

    combined = pd.concat(yearly_frames, ignore_index=True)
    combined["VERSAO"] = combined["VERSAO"].astype(int)

    dt_refer = pd.to_datetime(combined["DT_REFER"])
    is_standard_quarter = list(zip(dt_refer.dt.month, dt_refer.dt.day))
    combined = combined[[md in STANDARD_QUARTER_ENDS for md in is_standard_quarter]]

    combined = combined.sort_values("VERSAO").drop_duplicates(
        subset=["CD_CVM", "DT_REFER"], keep="last"
    )

    combined["SETOR_ATIV"] = combined["CD_CVM_INT"].map(sector_by_code)
    combined["QUARTER_LABEL"] = pd.to_datetime(combined["DT_REFER"]).dt.to_period("Q").astype(str)

    columns = [
        "CD_CVM",
        "CNPJ_CIA",
        "DENOM_CIA",
        "SETOR_ATIV",
        "DT_REFER",
        "QUARTER_LABEL",
        "VERSAO",
        "ID_DOC",
        "LINK_DOC",
    ]
    return combined[columns].sort_values(["DENOM_CIA", "DT_REFER"]).reset_index(drop=True)


def extract_notes_pdf(id_doc: str, cache_dir: Path, force: bool = False):
    """ITR counterpart to `cvm_notes.extract_notes_pdf` -- same download +
    selection logic, pointed at ITR's attachment tag/exclusions/extension.
    """
    zip_bytes = download_filing_zip(id_doc, cache_dir, force=force)
    attachments = list_attachments(
        zip_bytes,
        modern_tag=ITR_ATTACHMENT_TAG,
        modern_exclude=ITR_MODERN_EXCLUDE,
        legacy_extension=ITR_LEGACY_EXTENSION,
    )
    return select_source_attachments(attachments)


def save_company_quarter_notes(
    cd_cvm: str, quarter_label: str, id_doc: str, cache_dir: Path, out_root: Path, force: bool = False
) -> dict:
    """Download the filing, extract the attachment(s) likely to contain the
    debt note, and save them under ``out_root/{cd_cvm}/{quarter_label}/``
    (e.g. ``data/raw/itr/005410/2023Q1/``). Returns a metadata dict for
    logging -- same shape as `cvm_notes.save_company_year_notes`, keyed by
    quarter label instead of fiscal year since ITR has 3 filings/year.
    """
    cd_cvm = str(cd_cvm)
    quarter_label = str(quarter_label)
    id_doc = str(id_doc)

    out_dir = out_root / cd_cvm / quarter_label
    matches, tier = extract_notes_pdf(id_doc, cache_dir, force=force)

    result = {
        "CD_CVM": cd_cvm,
        "QUARTER_LABEL": quarter_label,
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
