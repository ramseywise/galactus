"""Where the two ingest paths converge, and where grounding is enforced.

`ingest_pdf` runs the text path always and the vision path only where the text
path came up short — a page with a table drawn in vector strokes yields little
or no text, and that emptiness is the signal to render it. Running vision on
every page would roughly triple ingest cost for pages whose text layer was
already perfect.

The grounding rule is a block, not a warning. "Factually correct" is a stated
requirement for this piece, and a fact whose span does not resolve back to the
source is exactly the failure that requirement is about. So `verify_facts`
drops unverifiable text facts rather than flagging them: nothing downstream has
to remember to check a flag, because an unverified fact never reaches the
prompt.

Vision facts are exempt from span verification — they have no offsets to verify
— and instead carry a lower confidence and a `p{n}:vision` span. They are
asserted, not proven, and the distinction survives into the prompt.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog

from ingest.tables import facts_from_table, row_span_contains_cells
from ingest.text import SPAN_RE, facts_from_pages, normalize_ws, resolve_span
from ingest.vision import render_pages
from model.gateway import LLM, LLMError
from models import Fact
from observability import OP_VISION, span

log = structlog.get_logger(__name__)

MIN_PAGE_TEXT_CHARS = 200
"""Below this a page's text layer is treated as insufficient.

A page of prose runs well over a thousand characters. A page that is mostly a
table or a chart yields a few stray labels. 200 separates them without
triggering on a legitimately sparse title page, which has little text but also
little content the vision path would recover.
"""

VISION_CONFIDENCE = 0.7
"""Confidence assigned to a fact the vision path asserted.

Below 1.0 because it cannot be checked against the source bytes. The number is
a marker of provenance, not a calibrated probability — it exists so a consumer
can rank verified facts above asserted ones.
"""

VISION_PROMPT = (
    "Extract every factual claim from this page as a JSON array of strings. "
    "Include figures, dates, names, and any data in tables — read tables "
    "row by row and state each row as a complete sentence. Do not interpret, "
    "summarize, or infer anything the page does not state. Return only the "
    "JSON array."
)

_VISION_SCHEMA = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "One factual claim per element, verbatim from the page.",
        }
    },
    "required": ["facts"],
    "additionalProperties": False,
}


async def ingest_pdf(
    pdf_path: str | Path,
    llm: LLM | None = None,
    *,
    force_vision: bool = False,
    model: str = "unknown",
) -> list[Fact]:
    """Extract verified facts from a PDF using both ingest paths.

    Args:
        pdf_path: The document to read.
        llm: Provider used for the vision path. When None the vision path is
            skipped entirely — ingest degrades to text-only rather than
            failing, which is what keeps the whole pipeline runnable without a
            credential.
        force_vision: Render every page, not just the text-sparse ones. For
            fixtures and evals where the vision path must be exercised.
        model: Model name recorded on vision spans. Passed in rather than read
            off the port, which is deliberately narrow enough not to expose it.

    Returns:
        Verified text facts followed by vision facts, in page order.
    """
    pages, table_facts = await asyncio.to_thread(_parse_path, pdf_path)
    return await _ingest(
        pdf_path, pages, llm, table_facts=table_facts, force_vision=force_vision, model=model
    )


async def ingest_pdf_bytes(
    data: bytes,
    llm: LLM | None = None,
    *,
    force_vision: bool = False,
    model: str = "unknown",
) -> list[Fact]:
    """Ingest a PDF held in memory.

    The API layer receives uploads as bytes and has nowhere to put them but a
    temp file; pymupdf can open a byte stream directly, so it does not have to.
    """
    pages, table_facts = await asyncio.to_thread(_parse_bytes, data)
    return await _ingest(
        data, pages, llm, table_facts=table_facts, force_vision=force_vision, model=model
    )


def verify_facts(facts: list[Fact], pages: list[str]) -> list[Fact]:
    """Drop text facts whose span does not resolve back to the source.

    The span is re-read from the page and compared to the fact text after
    whitespace normalization. Vision facts pass through untouched — they have
    no span to check.
    """
    verified: list[Fact] = []

    for fact in facts:
        if fact.origin == "vision":
            verified.append(fact)
            continue

        source = resolve_span(fact.source_span, pages)
        if source is None:
            continue

        if fact.origin == "table":
            # A table row is rephrased to keep its subject attached, so it can
            # never equal its own span. The full cell values it asserts still
            # have to be in there — see `tables.row_span_contains_cells`.
            if not row_span_contains_cells(normalize_ws(source), fact):
                continue
            verified.append(fact)
            continue

        if normalize_ws(source) != normalize_ws(fact.text):
            continue

        verified.append(fact)

    return verified


def pages_needing_vision(pages: list[str], *, force: bool = False) -> list[int]:
    """1-indexed pages whose text layer is too sparse to trust."""
    if force:
        return list(range(1, len(pages) + 1))
    return [n for n, text in enumerate(pages, start=1) if len(text.strip()) < MIN_PAGE_TEXT_CHARS]


async def extract_vision_facts(
    image: bytes, page_number: int, llm: LLM, *, model: str = "unknown"
) -> list[Fact]:
    """Ask the model to read one rendered page.

    The rendered PNG travels through the port's `images` channel — the whole
    point of this call is the page the text layer could not read, so the call
    is meaningless without it.

    A failed vision call returns no facts rather than propagating. The text
    path has already produced what it can, and losing a table is a worse
    outcome than losing the whole document.
    """
    try:
        with span(OP_VISION, model, stage="vision", page=page_number):
            result = await llm.complete_structured(VISION_PROMPT, _VISION_SCHEMA, images=[image])
    except LLMError:
        return []

    claims = result.get("facts") or []
    return [
        Fact(
            text=normalize_ws(str(claim)),
            source_span=f"p{page_number}:vision",
            page=page_number,
            confidence=VISION_CONFIDENCE,
            origin="vision",
        )
        for claim in claims
        if str(claim).strip()
    ]


def _parse_path(pdf_path: str | Path) -> tuple[list[str], list[Fact]]:
    """Open a PDF from disk and read pages + table facts. Sync — run off-loop."""
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        return _read_pages(doc)


def _parse_bytes(data: bytes) -> tuple[list[str], list[Fact]]:
    """Open an in-memory PDF and read pages + table facts. Sync — run off-loop."""
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return _read_pages(doc)


def _read_pages(doc: object) -> tuple[list[str], list[Fact]]:
    """Read page text and table facts in a single pass over an open document.

    Both entry points need the same two things from the same `pymupdf.Document`,
    and `find_tables` needs the live page object rather than its text, so the
    table path has to run while the document is open.

    A page whose tables are unreadable yields no table facts and keeps its text
    facts — `find_tables` is heuristic, and a malformed grid is a reason to fall
    back to the text path, not to fail the upload.
    """
    pages: list[str] = []
    table_facts: list[Fact] = []

    for page_number, page in enumerate(doc, start=1):
        page_text = page.get_text()
        pages.append(page_text)

        try:
            tables = page.find_tables().tables
        except Exception as exc:  # noqa: BLE001 - heuristic detector, any failure is recoverable
            log.warning("table_detect_failed", page=page_number, error=str(exc))
            continue

        for table_index, table in enumerate(tables):
            try:
                rows = table.extract()
            except Exception as exc:  # noqa: BLE001 - one bad grid must not fail the upload
                log.warning(
                    "table_extract_failed",
                    page=page_number,
                    table=table_index,
                    error=str(exc),
                )
                continue
            table_facts.extend(facts_from_table(rows, page_text, page_number))

    return pages, table_facts


def _drop_table_overlaps(text_facts: list[Fact], table_facts: list[Fact]) -> list[Fact]:
    """Drop text facts whose span overlaps a recovered table's span.

    The sentence splitter turns a grid into one run-on fact holding every value
    in the table with no row structure — exactly the misattribution the table
    path removes. But a page is not all grid: prose paragraphs sharing a page
    with a table carry claims of their own, and they stay. Only the text facts
    that overlap the region a table fact covers are superseded.
    """
    spans_by_page: dict[int, list[tuple[int, int]]] = {}
    for fact in table_facts:
        offsets = _span_offsets(fact.source_span)
        if offsets is not None and fact.page is not None:
            spans_by_page.setdefault(fact.page, []).append(offsets)

    kept: list[Fact] = []
    for fact in text_facts:
        offsets = _span_offsets(fact.source_span)
        table_spans = spans_by_page.get(fact.page or 0, [])
        overlaps = offsets is not None and any(
            offsets[0] < t_end and offsets[1] > t_start for t_start, t_end in table_spans
        )
        if not overlaps:
            kept.append(fact)

    return kept


def _span_offsets(source_span: str) -> tuple[int, int] | None:
    match = SPAN_RE.match(source_span)
    if match is None:
        return None
    return int(match.group(2)), int(match.group(3))


async def _ingest(
    pdf_source: str | Path | bytes,
    pages: list[str],
    llm: LLM | None,
    *,
    table_facts: list[Fact] | None = None,
    force_vision: bool,
    model: str = "unknown",
) -> list[Fact]:
    table_facts = table_facts or []

    text_facts = _drop_table_overlaps(facts_from_pages(pages), table_facts)
    facts = verify_facts(text_facts + table_facts, pages)

    if llm is None:
        return facts

    needed = pages_needing_vision(pages, force=force_vision)
    if not needed:
        return facts

    images = await asyncio.to_thread(render_pages, pdf_source, needed)
    batches = await asyncio.gather(
        *(
            extract_vision_facts(image, page_number, llm, model=model)
            for page_number, image in sorted(images.items())
        )
    )
    for batch in batches:
        facts.extend(batch)

    return facts
