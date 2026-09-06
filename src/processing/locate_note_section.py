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

# Brazilian filers often title a combined "net debt" note very long, e.g.
# Vale 2020: "Empréstimos, financiamentos, arrendamentos, caixa e
# equivalentes de caixa e aplicações financeiras de curto prazo" (~120
# chars) -- too strict a cutoff here excludes the real heading entirely,
# leaving only a shorter lettered subsection to be found instead.
MAX_HEADING_LEN = 160
SIZE_MARGIN = 1.0  # a heading must be at least this much larger than body text
KEYWORD_STEMS = ("emprestimo", "financiamento", "debenture")
CONNECTOR_WORDS = {"e", "de", "do", "dos", "da", "das", "em", "no", "na", "nos", "nas", "a", "o", "os", "as", "nota"}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _debt_keyword_score(text: str) -> int:
    normalized = _strip_accents(text).lower()
    return sum(kw in normalized for kw in KEYWORD_STEMS)


LETTERED_SUBSECTION_RE = re.compile(r"^\(?[a-z]\)\s")


def _heading_impurity(text: str) -> int:
    """Count of words that aren't the note's own keywords, digits, or common
    connectors -- low for a real title, high for a sentence that happens to
    mention the keywords in passing.

    A leading lettered-subsection marker ("(o) Empréstimos e
    financiamentos") is penalized explicitly: single-letter connector words
    ("o" = "the", "a" = "the"/"to") collide with exactly the letters used
    for subsection markers, so without this a marker like "(o)" scores as
    pure as a real numbered title -- seen for real on Ambev, where "(o)"
    (an accounting-policy subsection) tied a genuine "15. EMPRÉSTIMOS E
    FINANCIAMENTOS" on both size and impurity and won on document order.
    """
    normalized = _strip_accents(text).lower()
    words = re.findall(r"[a-z]+", normalized)
    impurity = sum(
        1
        for w in words
        if w not in CONNECTOR_WORDS and not any(w.startswith(s) or s.startswith(w) for s in KEYWORD_STEMS)
    )
    if LETTERED_SUBSECTION_RE.match(normalized):
        impurity += 2
    return impurity


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


# Some filers (found via corpus-wide diagnostic breakdown: Gerdau, Sid
# Nacional and others show 0% font_heading across every year checked) never
# elevate note-heading font size above body text at all -- the heading is
# distinguished from body text only by being bold *and* either ALL-CAPS
# ("NOTA 13 - EMPRÉSTIMOS E FINANCIAMENTOS", same 9.9pt as body) or a
# numbered prefix ("18. Empréstimos e financiamentos", Marfrig, same 12pt as
# body). Confirmed by direct inspection of these filers' actual line data
# before adding this, not guessed at. A same-size heading still needs to be
# bold and keyword-bearing like any other candidate -- this only widens
# *which* same-size lines are eligible, it doesn't relax the other checks
# (debt-keyword score, impurity tie-break) that keep false positives down.
NUMBERED_PREFIX_RE = re.compile(r"^\(?\d{1,3}\)?[.\-–—]\s")

# Toggle for isolated before/after measurement of this specific fix against
# the corpus (see eval_note_locator.py) -- always True in normal use.
ENABLE_SAME_SIZE_HEADING = True


def _signal_strength(line: Line, body_size: float) -> int:
    """0 for a candidate backed by a specific structural signal (elevated
    size, ALL-CAPS, or a numbered prefix); 1 for a candidate that only
    qualifies via the bare-purity same-size fallback below (bold, zero
    impurity, no case or number signal at all). Used purely as a tie-break
    layer ahead of size/impurity/document-order: a bolded, unnumbered,
    non-caps mention of "Empréstimos e financiamentos" can legitimately
    appear earlier in the document as a subsection of the accounting-
    policies note (describing how loans are measured, not the real note
    with balances) -- structurally indistinguishable from the real heading
    on size and impurity alone, but the real heading almost always carries
    a numbered prefix or ALL-CAPS styling that the policy-note mention
    doesn't, so preferring tier-0 candidates on a tie keeps the fallback
    purity rule from letting an earlier accounting-policy mention beat the
    genuine, later, more strongly-signaled heading. Confirmed against a
    real regression case (company 011312, 2017) before adding this.
    """
    if line.size >= body_size + SIZE_MARGIN:
        return 0
    if line.text.isupper() or NUMBERED_PREFIX_RE.match(line.text.strip()):
        return 0
    return 1


def _has_note_number_anchor(lines: list[Line], idx: int) -> bool:
    """True when `lines[idx]` is immediately preceded by a bare top-level
    note number on its own line, at the same bold/size style (e.g. company
    012793: bold "23" directly above bold "Empréstimos e financiamentos").
    This is the same anchor `locate_note_section` itself uses to switch on
    the precise number-tracking boundary search, so a candidate that has it
    is materially more trustworthy than one that doesn't -- confirmed
    against a real case (012793, 2015): the same zero-impurity phrase
    appears twice, once inside the accounting-policies note (no anchor) and
    once as the real, numbered note with actual balance data (anchored);
    without this check the two are indistinguishable ties and the earlier,
    wrong one wins on document order alone.
    """
    if idx == 0:
        return False
    prev = lines[idx - 1]
    return bool(prev.bold and prev.size == lines[idx].size and _bare_note_number(prev.text) is not None)


def _is_wrapped_continuation(lines: list[Line], idx: int) -> bool:
    """True when `lines[idx]` is plausibly one word of a longer phrase that
    landed on its own PDF line (an unusual but real layout quirk: company
    018627's filings put each word of a justified/spaced bold paragraph on
    its own line -- "d) Os" / "empréstimos," / "financiamentos," /
    "debêntures" / "e" / "arrendamento" / "mercantil", one word per line).
    Without this check, the bare-purity same-size rule below can pick
    "debêntures" alone as a heading candidate, since a single keyword word
    has zero impurity -- but it's a sentence fragment, not a title.

    The signal is the *preceding* line: if it's bold and the same size (the
    same visual run) and ends in a comma, this line is a continuation of an
    enumeration, not a fresh heading start. This does not reject a genuine
    heading preceded by its own bare note number on its own line (e.g.
    Braskem: bold "17" immediately before bold "Debêntures", both size 11)
    -- a bare number doesn't end in a comma, so it doesn't trip this check.
    """
    if idx == 0:
        return False
    prev = lines[idx - 1]
    return prev.bold and prev.size == lines[idx].size and prev.text.rstrip().endswith(",")


def _is_heading_shaped(line: Line, body_size: float, boilerplate: set[str]) -> bool:
    base = (
        len(line.text) < MAX_HEADING_LEN
        and _looks_substantive(line.text)
        and line.text.strip().lower() not in boilerplate
    )
    if not base:
        return False
    size_elevated = line.size >= body_size + SIZE_MARGIN
    if line.bold and size_elevated:
        return True
    if not ENABLE_SAME_SIZE_HEADING:
        return False
    is_upper = line.text.isupper()
    has_number_prefix = bool(NUMBERED_PREFIX_RE.match(line.text.strip()))
    if line.bold and (is_upper or has_number_prefix):
        return True
    # Found empirically (companies 020770, 024260): some filers style
    # headings as ALL-CAPS + numbered with no bold at all -- e.g. "11.
    # EMPRÉSTIMOS E FINANCIAMENTOS", not bold, same size as body text.
    # Not bold on its own is too weak a signal (way too much body text
    # qualifies), so this only fires when BOTH caps and numbering agree.
    if (not line.bold) and is_upper and has_number_prefix:
        return True
    # Found empirically (companies 004820/Braskem, 012793, 014443, 014761,
    # 017450 and others, round-6 corpus-wide diagnostic): some filers style
    # the heading in titlecase, bold, same size as body, with no numbering
    # at all ("Debêntures", "Empréstimos e financiamentos") or with a
    # decimal-style subsection number the simple NUMBERED_PREFIX_RE doesn't
    # match ("3.11 Empréstimos e financiamentos", "4.6 Emissão de
    # debêntures"). Neither caps nor a recognizable number prefix is
    # available here, so the safety net is *purity*: a bold line containing
    # only the debt keywords and connector words (zero impurity) is
    # trustworthy, because every observed false-positive candidate of this
    # shape is a cash-flow-statement/debt-movement-table caption that
    # always carries an extra leading verb/noun and therefore fails purity
    # ("Recebimento de empréstimos e financiamentos", "Pagamentos de...",
    # "Amortização de... - Principal", "Encargos sobre... captados").
    # Digits aren't counted as impurity (the word-extraction regex ignores
    # them), so this also transparently covers the decimal-numbered case
    # without a separate numbering pattern.
    # A genuine heading also never opens with a lowercase letter (found
    # empirically: company 018627's "debêntures" and company 024295's "e
    # Debêntures)" are both bold, zero-impurity, one-word-per-PDF-line
    # fragments of a wrapped table header/sentence -- "financiamentos,
    # debêntures" or "Capitais (CRI's e Debêntures)" split across separate
    # Line objects -- and both happen to start with a lowercase connector
    # or keyword-lowercase fragment precisely because they're mid-phrase,
    # not a title start). _is_wrapped_continuation below catches some of
    # these via the preceding line; this catches the rest directly and more
    # generally, since a real title is never lowercase-initial in Portuguese.
    starts_lowercase = bool(re.match(r"^[a-zà-ü]", line.text.strip()))
    if line.bold and not starts_lowercase and _heading_impurity(line.text) == 0:
        return True
    return False


def _has_qualifying_keywords(text: str) -> bool:
    """"Debênture" alone is an unambiguous heading signal -- unlike
    "empréstimo"/"financiamento" alone, which also show up in unrelated
    headings (e.g. "Fluxo de caixa de atividades de financiamento", a cash-
    flow-statement line; "Empréstimos a Empregados", employee loans). Found
    empirically: company 022187 titles its note plainly "Debêntures" with no
    "Empréstimos e Financiamentos" heading anywhere, so the normal 2-stem
    requirement never matched it at all.
    """
    normalized = _strip_accents(text).lower()
    stems_present = {s for s in KEYWORD_STEMS if s in normalized}
    if "debenture" in stems_present:
        return True
    return len(stems_present) >= 2


def _is_debt_heading_candidate(line: Line, body_size: float, boilerplate: set[str]) -> bool:
    return _is_heading_shaped(line, body_size, boilerplate) and _has_qualifying_keywords(line.text)


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


TOC_RUN_GAP = 6  # max lines between consecutive bare-number entries to count as the same run
TOC_MIN_RUN_LENGTH = 3  # entries needed before a run counts as a TOC, not a real number+continuation


def _toc_region_lines(lines: list[Line]) -> set[int]:
    """Indices belonging to a dense run of bare top-level numbers -- i.e. a
    table-of-contents listing (every note number + title, back-to-back),
    not real section headings. A real note body never has another bare
    top-level number within a handful of lines of the previous one; a TOC
    lists every note in immediate succession. Seen for real on Ambev 2024,
    whose page-1 index ("16" / "EMPRÉSTIMOS E FINANCIAMENTOS" / "17" / ...)
    otherwise looks identical in style to the real heading deep in the
    document.
    """
    number_positions = [i for i, l in enumerate(lines) if l.bold and _bare_note_number(l.text) is not None]
    toc_indices: set[int] = set()
    i = 0
    while i < len(number_positions):
        run = [number_positions[i]]
        j = i + 1
        while j < len(number_positions) and number_positions[j] - run[-1] <= TOC_RUN_GAP:
            run.append(number_positions[j])
            j += 1
        if len(run) >= TOC_MIN_RUN_LENGTH:
            for idx in run:
                toc_indices.add(idx)
                if idx + 1 < len(lines):
                    toc_indices.add(idx + 1)  # the title line right after each number
        i = j
    return toc_indices


def _bookmark_section(lines: list[Line], bookmarks: list[tuple[int, str, int]]) -> "NoteSection | None":
    """If the PDF has a native outline/bookmark entry mentioning debt
    keywords, use it directly: far more precise than inferring boundaries
    from font styling, since it's an explicit navigational entry the filer's
    own software generated. The section runs from that entry's page to the
    next bookmark entry at any level (empirically ~5% of currently-
    unreliable filings have any outline at all, so this is a small but
    strictly additive win, checked before falling back to font/regex).
    """
    candidates = [
        i for i, (_, title, page) in enumerate(bookmarks) if page and page > 0 and _debt_keyword_score(title) >= 1
    ]
    if not candidates:
        return None
    idx = candidates[0]
    _, title, page = bookmarks[idx]
    start_page = page - 1  # get_toc() pages are 1-indexed; Line.page is 0-indexed
    end_page = None
    for _, _, p in bookmarks[idx + 1 :]:
        if p and p - 1 > start_page:
            end_page = p - 1
            break
    section_lines = [l for l in lines if l.page >= start_page and (end_page is None or l.page < end_page)]
    if not section_lines:
        return None
    return NoteSection(
        text="\n".join(l.text for l in section_lines),
        diagnostic="font_heading",  # as precisely bounded as the font-heading tier, if not more so
        start_line=None,
        end_line=None,
        heading=title,
    )


@dataclass
class NoteSection:
    text: str
    diagnostic: str  # "font_heading" | "regex_only" | "not_found"
    start_line: int | None
    end_line: int | None
    heading: str | None


FALLBACK_MAX_LINES = 500  # cap for the no-formatting fallback, which has no structural end signal
WEAK_SIGNAL_MAX_LINES = 3200  # cap for a weak-signal start with no note-number anchor; see its use site


def _next_heading_boundary(
    lines: list[Line],
    from_idx: int,
    heading_size: float,
    note_number: int | None,
    body_size: float,
    boilerplate: set[str],
    toc_region: set[int],
) -> int:
    """Index of the next section boundary after `from_idx`, or len(lines)."""
    for i in range(from_idx, len(lines)):
        if i in toc_region:
            continue
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


def locate_note_section(lines: list[Line], bookmarks: list[tuple[int, str, int]] | None = None) -> NoteSection:
    if not lines:
        return NoteSection(text="", diagnostic="not_found", start_line=None, end_line=None, heading=None)

    if bookmarks:
        bookmark_result = _bookmark_section(lines, bookmarks)
        if bookmark_result is not None:
            return bookmark_result

    body_size = _body_size(lines)
    boilerplate = _repeated_lines(lines)
    toc_region = _toc_region_lines(lines)
    visual_candidates = [
        i
        for i, l in enumerate(lines)
        if i not in toc_region
        and _is_debt_heading_candidate(l, body_size, boilerplate)
        # Only the weak (bare-purity, no case/number signal) candidates need
        # the wrapped-continuation check -- a candidate backed by a real
        # structural signal (elevated size, caps, or numbering) is already
        # trustworthy regardless of what precedes it.
        and not (_signal_strength(l, body_size) == 1 and _is_wrapped_continuation(lines, i))
    ]

    if visual_candidates:
        # _signal_strength comes first, ahead of size: a candidate backed by
        # a real structural signal (elevated size, caps, or numbering) must
        # always beat a bare-purity same-size candidate, regardless of which
        # one has the larger font. Found empirically (company 017671): a
        # decimal-numbered *subsection* ("21.3 Empréstimos e financiamentos",
        # breaking a combined note into parts) can be styled at an even
        # larger size than its own parent note's numbered heading ("21.
        # EMPRÉSTIMOS E FINANCIAMENTOS, DEBÊNTURES, ARRENDAMENTOS...") --
        # sorting by size first let the subsection win, which starts the
        # section deep inside the real note and breaks the end-of-note
        # boundary search entirely (observed: a 142,000-character capture
        # instead of a few thousand, because the boundary search no longer
        # has the parent note's own number to search for).
        # Next, a candidate anchored by a preceding bare note number beats
        # one without: found empirically (company 012793) that the exact
        # same zero-impurity phrase can appear twice -- once inside the
        # accounting-policies note (no anchor), once as the real, numbered
        # note with actual balance data (anchored) -- an otherwise perfect
        # tie that document order alone would resolve in favor of the
        # wrong, earlier one.
        # Within the same tier, size is still primary (a distinctly larger
        # font reliably marks the top-level note among same-tier candidates)
        # and impurity only breaks a same-size tie. Prioritizing impurity
        # over size was wrong for the same reason before: it penalized
        # legitimate compound titles like Vale's "Empréstimos,
        # financiamentos e caixa e equivalentes de caixa" (a combined
        # net-debt note) for mentioning "caixa", handing the match to an
        # unrelated smaller-font subsection instead.
        start_idx = min(
            visual_candidates,
            key=lambda i: (
                _signal_strength(lines[i], body_size),
                0 if _has_note_number_anchor(lines, i) else 1,
                -lines[i].size,
                _heading_impurity(lines[i].text),
            ),
        )
        diagnostic = "font_heading"
        heading_size = lines[start_idx].size

        title_idx = start_idx
        heading_signal_strength = _signal_strength(lines[title_idx], body_size)
        note_number = None
        if start_idx > 0 and start_idx - 1 not in toc_region and lines[start_idx - 1].size == heading_size and lines[start_idx - 1].bold:
            note_number = _bare_note_number(lines[start_idx - 1].text)
        if note_number is not None:
            start_idx -= 1  # include the number line itself in the section

        # A long compound title (common for Brazilian "net debt" notes, e.g.
        # "Empréstimos, financiamentos, arrendamentos, caixa e equivalentes
        # de caixa e aplicações financeiras de curto prazo") can wrap onto a
        # second PDF line at the identical size/bold styling. Without
        # absorbing that continuation, the boundary search below mistakes
        # it for the start of an unrelated next section, since taken alone
        # it has no debt keywords of its own.
        end_idx = title_idx + 1
        while end_idx < len(lines) and lines[end_idx].bold and lines[end_idx].size == heading_size and len(lines[end_idx].text) < 60:
            end_idx += 1

        # Some filers split the debt disclosure into adjacent notes (e.g.
        # Usiminas: note 20 "Empréstimos e financiamentos", note 21
        # "Debêntures" immediately after). The thesis scope is the combined
        # debt content regardless of how a filer chose to split it, so keep
        # extending through boundaries that are themselves debt-related.
        for _ in range(MAX_CONTINUATION_NOTES):
            end_idx = _next_heading_boundary(lines, end_idx, heading_size, note_number, body_size, boilerplate, toc_region)
            if end_idx >= len(lines):
                break
            # In bare-number style the boundary line is just "21" -- the
            # actual title (e.g. "Debêntures") is the line right after it.
            title_idx = end_idx + 1 if (note_number is not None and end_idx + 1 < len(lines)) else end_idx
            if _debt_keyword_score(lines[title_idx].text) == 0:
                break
            end_idx += 1  # step past this continuation heading, keep searching for the real end

        # Safety net for the combination of two weak signals: no bare note
        # number to anchor the boundary search on (note_number is None) AND
        # the heading itself has no case/number signal either (see
        # _signal_strength) -- only then does _next_heading_boundary fall
        # back to its least precise check ("next same-size line with zero
        # debt keywords"), which can occasionally be an accounting-policy
        # note mentioning the same phrase (e.g. "Os empréstimos e
        # financiamentos são reconhecidos inicialmente pelo valor justo...")
        # rather than the real note. When that happens, the boundary search
        # has nothing reliable to stop at and can run for thousands of lines
        # through unrelated accounting-policy topics (confirmed on companies
        # 012793 and 014443: 90,000-210,000-character captures, vs. a few
        # thousand for a real note). A heading with a bare note number, or
        # with its own case/number signal, never needs this cap: either
        # anchors the boundary search precisely, which is exactly why
        # runaway captures were never observed for those. WEAK_SIGNAL_MAX_LINES
        # is set above the longest confirmed-genuine weak-signal note found
        # in this corpus (2,928 lines, company 021091) with headroom, not an
        # arbitrary round number.
        if note_number is None and heading_signal_strength == 1:
            end_idx = min(end_idx, start_idx + WEAK_SIGNAL_MAX_LINES)
    else:
        # No bold/sized heading found at all (e.g. no font metadata survived
        # extraction, or the note simply isn't styled distinctly) -- best
        # guess is the last short keyword mention, since earlier ones tend
        # to be table-of-contents/cross-references. No structural signal
        # for where the section ends, so cap it at a fixed window.
        weak_candidates = [i for i, l in enumerate(lines) if len(l.text) < MAX_HEADING_LEN and _has_qualifying_keywords(l.text)]
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
