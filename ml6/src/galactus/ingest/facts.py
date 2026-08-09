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

from pathlib import Path

from galactus.ml6.src.galactus.ingest.text import facts_from_pages, resolve_span
from galactus.ml6.src.galactus.ingest.vision import image_to_message, render_page_png
from galactus.ml6.src.galactus.llm.port import LLM, LLMError
from galactus.ml6.src.galactus.models import Fact
from galactus.ml6.src.galactus.obs import OP_VISION, span

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
    pdf_path: str | Path, llm: LLM | None = None, *, force_vision: bool = False
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

    Returns:
        Verified text facts followed by vision facts, in page order.
    """
    import pymupdf

    with pymupdf.open(pdf_path) as doc:
        pages = [page.get_text() for page in doc]

    return await _ingest(pdf_path, pages, llm, force_vision=force_vision)


async def ingest_pdf_bytes(
    data: bytes, llm: LLM | None = None, *, force_vision: bool = False
) -> list[Fact]:
    """Ingest a PDF held in memory.

    The API layer receives uploads as bytes and has nowhere to put them but a
    temp file; pymupdf can open a byte stream directly, so it does not have to.
    """
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages = [page.get_text() for page in doc]

    return await _ingest(data, pages, llm, force_vision=force_vision)


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
        if _normalize(source) != _normalize(fact.text):
            continue

        verified.append(fact)

    return verified


def pages_needing_vision(pages: list[str], *, force: bool = False) -> list[int]:
    """1-indexed pages whose text layer is too sparse to trust."""
    if force:
        return list(range(1, len(pages) + 1))
    return [
        n
        for n, text in enumerate(pages, start=1)
        if len(text.strip()) < MIN_PAGE_TEXT_CHARS
    ]


async def extract_vision_facts(
    pdf_source: str | Path | bytes, page_number: int, llm: LLM
) -> list[Fact]:
    """Ask the model to read one rendered page.

    A failed vision call returns no facts rather than propagating. The text
    path has already produced what it can, and losing a table is a worse
    outcome than losing the whole document.
    """
    try:
        image = render_page_png(pdf_source, page_number)
    except (IndexError, ValueError):
        return []

    message = image_to_message(image, VISION_PROMPT)
    prompt = message["content"][-1]["text"]

    try:
        with span(OP_VISION, "unknown", stage="vision", page=page_number):
            result = await llm.complete_structured(prompt, _VISION_SCHEMA)
    except LLMError:
        return []

    claims = result.get("facts") or []
    return [
        Fact(
            text=_normalize(str(claim)),
            source_span=f"p{page_number}:vision",
            page=page_number,
            confidence=VISION_CONFIDENCE,
            origin="vision",
        )
        for claim in claims
        if str(claim).strip()
    ]


async def _ingest(
    pdf_source: str | Path | bytes,
    pages: list[str],
    llm: LLM | None,
    *,
    force_vision: bool,
) -> list[Fact]:
    facts = verify_facts(facts_from_pages(pages), pages)

    if llm is None:
        return facts

    for page_number in pages_needing_vision(pages, force=force_vision):
        facts.extend(await extract_vision_facts(pdf_source, page_number, llm))

    return facts


def _normalize(text: str) -> str:
    return " ".join(text.split())
