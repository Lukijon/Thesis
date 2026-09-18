"""Isolate the "Relatório da Administração" (Management Report) from a
combined DFP filing document -- Brazil's closest regulatory equivalent to
the US MD&A, and per the literature review in
reports/return_predictability_exploration.md, the section where textual-
change-predicts-returns effects are found to concentrate (high managerial
discretion, unlike the audited, formulaic debt note).

Confirmed by direct inspection before building this (see that report): of
997 already-cached annual filings, only ~13% have the report as its own
named attachment; the other ~83% were matched via `largest_attachment_
fallback`/`statements_filename_match`, meaning the cached document is
likely the *combined* filing package, which may embed the report at its
start (confirmed on Embraer 2018: "EMBRAER S.A. / RELATÓRIO DA
ADMINISTRAÇÃO 2018 / MENSAGEM DO DIRETOR-PRESIDENTE...") -- this module
locates that embedded span using already-extracted lines, no re-parsing.

Simpler than locate_note_section.py's heuristic: the report is always the
*first* major narrative section in a combined filing (before the audited
statements), so this looks for the report's own heading, then the next
line that looks like the start of the audited financial statements.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.processing.pdf_text import Line

START_RE = re.compile(r"(?i)relat[óo]rio\s+d[ae]\s+administra[çc][ãa]o")
END_RE = re.compile(
    r"(?i)balan[çc]o\s+patrimonial|demonstra[çc][ãa]o\s+d[oe]\s+resultado|"
    r"demonstra[çc][õo]es\s+financeiras|notas\s+explicativas\s+[àa]s?\s+demonstra|"
    r"parecer\s+dos\s+auditores|relat[óo]rio\s+dos\s+auditores"
)
MAX_LINES_IF_NO_END = 600
MAX_SEARCH_WINDOW = 200  # the report heading itself must appear early -- a
# match deep in the document is far more likely a body-text cross-reference
# ("conforme mencionado no Relatório da Administração...") than the real
# section start.


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


@dataclass
class ManagementReportSection:
    text: str
    diagnostic: str  # "found" | "not_found"
    start_line: int | None
    end_line: int | None
    heading: str | None


def locate_management_report(lines: list[Line]) -> ManagementReportSection:
    if not lines:
        return ManagementReportSection(text="", diagnostic="not_found", start_line=None, end_line=None, heading=None)

    search_end = min(MAX_SEARCH_WINDOW, len(lines))
    start_idx = None
    for i in range(search_end):
        if START_RE.search(lines[i].text) and len(lines[i].text) < 100:
            start_idx = i
            break
    if start_idx is None:
        return ManagementReportSection(text="", diagnostic="not_found", start_line=None, end_line=None, heading=None)

    end_idx = len(lines)
    for i in range(start_idx + 1, min(start_idx + MAX_LINES_IF_NO_END, len(lines))):
        if END_RE.search(lines[i].text) and len(lines[i].text) < 100:
            end_idx = i
            break
    else:
        end_idx = min(start_idx + MAX_LINES_IF_NO_END, len(lines))

    section_lines = lines[start_idx:end_idx]
    return ManagementReportSection(
        text="\n".join(l.text for l in section_lines),
        diagnostic="found",
        start_line=start_idx,
        end_line=end_idx,
        heading=lines[start_idx].text,
    )
