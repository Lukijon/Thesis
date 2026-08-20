"""Isolate the debt note ("empréstimos, financiamentos e debêntures") from
the full text of a DFP filing.

Validated against real filings during POC development: the actual note
heading is reliably distinguishable from table-of-contents entries and body
mentions of the same phrase by font size + bold -- e.g. WEG 2020 uses size
12/bold for note headings vs. 8-10 for body text; CEMIG 2016 (a legacy-era
filing) uses size 13/bold vs. 7-12 for body text and cross-references. The
heading itself follows a numbered-section pattern ("16 EMPRÉSTIMOS E
FINANCIAMENTOS", "20. EMPRÉSTIMOS E FINANCIAMENTOS E DEBÊNTURES").

Strategy: compute each document's body-text font size (the mode across all
lines), then find lines that are (a) short, (b) bold, (c) sized clearly
above body text, and (d) mention at least two of {empréstimos,
financiamentos, debêntures}. Bold+elevated-size alone isn't a unique
signal -- some filers reuse the same style for sub-captions ("a) Vencimento
dos empréstimos...") or table row labels, so among candidates the one
picked is the "purest" title (fewest non-keyword/non-connector words, e.g.
"16 EMPRÉSTIMOS E FINANCIAMENTOS" or plain "Empréstimos e financiamentos"),
tie-broken by larger font size. A numbered prefix ("16 EMPRÉSTIMOS...",
"20. EMPRÉSTIMOS...") is common but *not* required -- e.g. Usiminas titles
the note plainly with no leading number, same bold/elevated-size signature
otherwise. The section end is the next heading-shaped line that does *not*
itself mention any debt keyword (a sub-caption like "a) Vencimento dos
empréstimos..." still belongs to the same note; the note genuinely ends at
the next *unrelated* heading, e.g. "17 PROVISÕES PARA CONTINGÊNCIAS").

Falls back to a same-keyword-match-without-bold/size signal when no visual
heading is found (e.g. a flattened/rasterized-then-OCR'd PDF with no font
info) -- flagged with a different diagnostic tag so the caller can tell
the two apart.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from src.processing.pdf_text import Line

MAX_HEADING_LEN = 100
SIZE_MARGIN = 1.0  # a heading must be at least this much larger than body text
KEYWORD_STEMS = ("emprestimo", "financiamento", "debenture")
CONNECTOR_WORDS = {"e", "de", "do", "dos", "da", "das", "em", "no", "na", "nos", "nas", "a", "o", "os", "as", "nota"}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _debt_keyword_score(text: str) -> int:
    normalized = _strip_accents(text).lower()
    return sum(kw in normalized for kw in KEYWORD_STEMS)


def _heading_impurity(text: str) -> int:
    """Count of words that aren't the note's own keywords, digits, or common
    connectors -- low for a real title, high for a sentence that happens to
    mention the keywords in passing.
    """
    normalized = _strip_accents(text).lower()
    words = re.findall(r"[a-z]+", normalized)
    return sum(
        1
        for w in words
        if w not in CONNECTOR_WORDS and not any(w.startswith(s) or s.startswith(w) for s in KEYWORD_STEMS)
    )


def _body_size(lines: list[Line]) -> float:
    return Counter(l.size for l in lines).most_common(1)[0][0]


MIN_HEADING_LETTERS = 4  # excludes bare sub-numbering like "20.1", "(a)", "(i)", table cells like "31/12/20"
BOILERPLATE_PAGE_SPREAD = 0.2  # a line seen on this fraction of *all* pages is a running header/footer


def _looks_substantive(text: str) -> bool:
    return len(re.findall(r"[A-Za-zÀ-Üà-ü]", text)) >= MIN_HEADING_LETTERS


def _repeated_lines(lines: list[Line]) -> set[str]:
    """Normalized text of lines spread across a large fraction of *all*
    pages in the document -- running headers/footers (company name, "NOTAS
    EXPLICATIVAS...", page furniture). Deliberately page-spread-based
    rather than raw-count-based: a note's own title can legitimately repeat
    several times as a running sub-header across *its own* multi-page span
    (seen on Usiminas) without being document-wide boilerplate.
    """
    if not lines:
        return set()
    total_pages = len({l.page for l in lines}) or 1
    pages_by_text: dict[str, set[int]] = {}
    for l in lines:
        pages_by_text.setdefault(l.text.strip().lower(), set()).add(l.page)
    threshold = max(4, int(total_pages * BOILERPLATE_PAGE_SPREAD))
    return {text for text, pages in pages_by_text.items() if len(pages) >= threshold}


def _is_heading_shaped(line: Line, body_size: float, boilerplate: set[str]) -> bool:
    return (
        len(line.text) < MAX_HEADING_LEN
        and line.bold
        and line.size >= body_size + SIZE_MARGIN
        and _looks_substantive(line.text)
        and line.text.strip().lower() not in boilerplate
    )


def _is_debt_heading_candidate(line: Line, body_size: float, boilerplate: set[str]) -> bool:
    return _is_heading_shaped(line, body_size, boilerplate) and _debt_keyword_score(line.text) >= 2


BARE_NUMBER_RE = re.compile(r"^\(?(\d{1,3})\)?\.?$")


def _bare_note_number(text: str) -> int | None:
    """Some filers (e.g. Usiminas) put the note number on its own line,
    separate from the title, and reuse the same bold/size styling for
    subsection labels and table captions throughout the note -- which
    defeats the "same size, no debt keyword" end-of-note heuristic (a
    subsection can innocently match it). Where a bare top-level number
    precedes the heading, the much more precise signal is the next bare
    top-level number at the same style, since subsections are numbered
    "20.1", "(a)", "(i)" -- never a bare top-level integer.
    """
    m = BARE_NUMBER_RE.match(text.strip())
    return int(m.group(1)) if m else None


@dataclass
class NoteSection:
    text: str
    diagnostic: str  # "font_heading" | "regex_only" | "not_found"
    start_line: int | None
    end_line: int | None
    heading: str | None


FALLBACK_MAX_LINES = 500  # cap for the no-formatting fallback, which has no structural end signal


def _next_heading_boundary(
    lines: list[Line], from_idx: int, heading_size: float, note_number: int | None, body_size: float, boilerplate: set[str]
) -> int:
    """Index of the next section boundary after `from_idx`, or len(lines)."""
    for i in range(from_idx, len(lines)):
        l = lines[i]
        if note_number is not None:
            # Precise signal: the next bare top-level number at the same
            # style. Subsections are numbered "20.1", "(a)", "(i)" -- never
            # a second bare top-level integer -- so this isn't fooled by
            # same-styled subsection/table captions the way a generic
            # "no debt keyword" check can be.
            n = _bare_note_number(l.text)
            if n is not None and n != note_number and l.size == heading_size and l.bold:
                return i
        else:
            # A same-tier subsection within the note (e.g. "Garantias") can
            # lack debt keywords and still use a slightly smaller bold size
            # than the note's own heading -- require matching the heading's
            # specific size, not just "elevated over body", to only stop at
            # a genuine next-note boundary.
            if _is_heading_shaped(l, body_size, boilerplate) and l.size >= heading_size and _debt_keyword_score(l.text) == 0:
                return i
    return len(lines)


MAX_CONTINUATION_NOTES = 3  # cap on how many adjacent debt-related notes to merge


def locate_note_section(lines: list[Line]) -> NoteSection:
    if not lines:
        return NoteSection(text="", diagnostic="not_found", start_line=None, end_line=None, heading=None)

    body_size = _body_size(lines)
    boilerplate = _repeated_lines(lines)
    visual_candidates = [i for i, l in enumerate(lines) if _is_debt_heading_candidate(l, body_size, boilerplate)]

    if visual_candidates:
        start_idx = min(visual_candidates, key=lambda i: (_heading_impurity(lines[i].text), -lines[i].size))
        diagnostic = "font_heading"
        heading_size = lines[start_idx].size

        note_number = None
        if start_idx > 0 and lines[start_idx - 1].size == heading_size and lines[start_idx - 1].bold:
            note_number = _bare_note_number(lines[start_idx - 1].text)
        if note_number is not None:
            start_idx -= 1  # include the number line itself in the section

        # Some filers split the debt disclosure into adjacent notes (e.g.
        # Usiminas: note 20 "Empréstimos e financiamentos", note 21
        # "Debêntures" immediately after). The thesis scope is the combined
        # debt content regardless of how a filer chose to split it, so keep
        # extending through boundaries that are themselves debt-related.
        end_idx = start_idx + 1
        for _ in range(MAX_CONTINUATION_NOTES):
            end_idx = _next_heading_boundary(lines, end_idx, heading_size, note_number, body_size, boilerplate)
            if end_idx >= len(lines):
                break
            # In bare-number style the boundary line is just "21" -- the
            # actual title (e.g. "Debêntures") is the line right after it.
            title_idx = end_idx + 1 if (note_number is not None and end_idx + 1 < len(lines)) else end_idx
            if _debt_keyword_score(lines[title_idx].text) == 0:
                break
            end_idx += 1  # step past this continuation heading, keep searching for the real end
    else:
        # No bold/sized heading found at all (e.g. no font metadata survived
        # extraction, or the note simply isn't styled distinctly) -- best
        # guess is the last short keyword mention, since earlier ones tend
        # to be table-of-contents/cross-references. No structural signal
        # for where the section ends, so cap it at a fixed window.
        weak_candidates = [i for i, l in enumerate(lines) if len(l.text) < MAX_HEADING_LEN and _debt_keyword_score(l.text) >= 2]
        if not weak_candidates:
            return NoteSection(text="", diagnostic="not_found", start_line=None, end_line=None, heading=None)
        start_idx = weak_candidates[-1]
        diagnostic = "regex_only"
        end_idx = min(start_idx + FALLBACK_MAX_LINES, len(lines))

    # Page-break running headers/footers (e.g. "WEG S.A." repeated at the
    # top of every page) can fall inside the section's own page range;
    # strip them from the text, but keep the heading line itself even if it
    # happens to repeat (e.g. Usiminas' own note title as a running
    # sub-header across its pages).
    section_lines = [l for l in lines[start_idx:end_idx] if l.text.strip().lower() not in boilerplate or l is lines[start_idx]]
    return NoteSection(
        text="\n".join(l.text for l in section_lines),
        diagnostic=diagnostic,
        start_line=start_idx,
        end_line=end_idx,
        heading=lines[start_idx].text,
    )
