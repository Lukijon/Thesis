"""Per-line text extraction with layout metadata (font size, bold), needed
to distinguish real section headings from body-text mentions of the same
keywords -- plain text extraction alone can't tell a heading from a
paragraph that happens to mention "empréstimos e financiamentos".
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import fitz  # pymupdf


@dataclass
class Line:
    page: int
    text: str
    size: float
    bold: bool


def extract_lines(pdf_path: Path) -> list[Line]:
    """Every non-empty text line in the document, in reading order, with
    the max span font size and whether any span looks bold.
    """
    doc = fitz.open(pdf_path)
    lines: list[Line] = []
    for page_num, page in enumerate(doc):
        page_dict = page.get_text("dict")
        for block in page_dict["blocks"]:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                size = max(s["size"] for s in spans)
                bold = any("bold" in s["font"].lower() for s in spans)
                lines.append(Line(page=page_num, text=text, size=round(size, 1), bold=bold))
    return lines


def lines_to_dicts(lines: list[Line]) -> list[dict]:
    return [asdict(l) for l in lines]
