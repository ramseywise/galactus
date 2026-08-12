"""The text path: extract sentence-level facts with checkable offsets.

Sentences, not paragraphs or pages. A fact is what a collateral claim gets
attributed to, and a citation that points at a whole page is not a citation you
can verify — the grounding check in `facts.py` re-reads the source span and
compares it to the fact text, which only works if the span is tight.

`source_span` is `p{page}:{start}-{end}`, where the offsets index into that
page's extracted text. Page-local rather than document-global so that a span
stays valid if an unrelated page changes.
"""

from __future__ import annotations

import re
from pathlib import Path

from models import Fact

MIN_FACT_WORDS = 4
"""Below this a sentence is a heading, a label, or a page number.

Not a quality judgement — short fragments are real text, but they carry no
claim, and admitting them means the grounding stage spends its budget verifying
things like "Q3 Results" against the source.
"""

SPAN_RE = re.compile(r"^p(\d+):(\d+)-(\d+)$")
"""The `source_span` grammar. Parsed by `resolve_span` to check a citation."""

_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

_WHITESPACE_RE = re.compile(r"\s+")


def extract_text_facts(pdf_path: str | Path) -> list[Fact]:
    """Extract sentence-level facts from a PDF's embedded text layer.

    Returns an empty list for a scanned PDF with no text layer — that is the
    case the vision path exists to cover, not an error.
    """
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        pages = [page.get_text() for page in doc]

    return facts_from_pages(pages)


def facts_from_pages(pages: list[str]) -> list[Fact]:
    """Build facts from already-extracted page text.

    Split out from `extract_text_facts` so the sentence logic is testable
    without a PDF on disk.
    """
    facts: list[Fact] = []
    for page_number, page_text in enumerate(pages, start=1):
        facts.extend(_facts_from_page(page_text, page_number))
    return facts


def resolve_span(span: str, pages: list[str]) -> str | None:
    """Return the source text a span points at, or None if it does not resolve.

    The verification half of the citation contract: a fact claims an offset
    range, and this reads the range back out of the source. Used by the
    grounding check, which is why it returns None rather than raising — an
    unresolvable span is a fact to reject, not a crash.
    """
    match = SPAN_RE.match(span)
    if not match:
        return None

    page_number, start, end = (int(g) for g in match.groups())
    if not 1 <= page_number <= len(pages):
        return None

    page_text = pages[page_number - 1]
    if start < 0 or end > len(page_text) or start >= end:
        return None

    return page_text[start:end]


def _facts_from_page(page_text: str, page_number: int) -> list[Fact]:
    """Split one page into sentence facts, tracking offsets as we go."""
    facts: list[Fact] = []

    for start, end in _sentence_spans(page_text):
        raw = page_text[start:end]
        normalized = _normalize(raw)

        if len(normalized.split()) < MIN_FACT_WORDS:
            continue

        facts.append(
            Fact(
                text=normalized,
                source_span=f"p{page_number}:{start}-{end}",
                page=page_number,
                confidence=1.0,
                origin="text",
            )
        )

    return facts


def _sentence_spans(page_text: str) -> list[tuple[int, int]]:
    """Offsets of each sentence in the page text.

    Offsets are computed against the raw text, not the normalized text, so the
    span still resolves against what `resolve_span` will read back. Normalizing
    first would shift every offset after the first collapsed newline.
    """
    spans: list[tuple[int, int]] = []
    cursor = 0

    for piece in _SENTENCE_END_RE.split(page_text):
        if not piece:
            continue
        start = page_text.find(piece, cursor)
        if start == -1:
            continue
        end = start + len(piece)
        spans.append((start, end))
        cursor = end

    return spans


def _normalize(text: str) -> str:
    """Collapse the line breaks PDF extraction leaves mid-sentence.

    A sentence wrapped across two lines in the source arrives with a newline in
    the middle. Left alone it reaches the prompt as a broken line, and word
    counts still work but the model copies the break into the draft.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()
