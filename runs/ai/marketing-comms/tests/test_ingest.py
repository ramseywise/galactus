"""Hybrid ingest: the text path, the vision path, and the grounding gate.

The vision path is exercised against a scripted fake rather than a live model —
same reason as the repair-loop tests. The fixture PDFs are real, though: the
text path runs against actual pymupdf extraction, because the offsets it
produces are the whole point and a mocked extractor would prove nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf
import pytest

from ingest.facts import (
    MIN_PAGE_TEXT_CHARS,
    VISION_CONFIDENCE,
    extract_vision_facts,
    ingest_pdf,
    ingest_pdf_bytes,
    pages_needing_vision,
    verify_facts,
)
from ingest.text import (
    MIN_FACT_WORDS,
    extract_text_facts,
    facts_from_pages,
    resolve_span,
)
from ingest.vision import (
    MAX_IMAGE_DIMENSION,
    encode_image_base64,
    image_to_message,
    page_images,
    render_page_png,
)
from model.gateway import LLMError
from models import Fact

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SENDER_PDF = FIXTURE_DIR / "sender.pdf"
RECEIVER_PDF = FIXTURE_DIR / "receiver.pdf"


class FakeVisionLLM:
    """Returns a scripted list of claims for every vision call."""

    def __init__(self, claims: list[str] | None = None, error: bool = False) -> None:
        self.claims = claims if claims is not None else ["A table row states 96.2 percent."]
        self.error = error
        self.calls = 0

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.error:
            raise LLMError("provider down")
        return {"facts": list(self.claims)}


def _pages(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]


@pytest.fixture(params=[SENDER_PDF, RECEIVER_PDF], ids=["sender", "receiver"])
def fixture_pdf(request) -> Path:
    return request.param


# ---------------------------------------------------------------------------
# Text path
# ---------------------------------------------------------------------------


def test_fixture_yields_at_least_five_facts(fixture_pdf):
    facts = extract_text_facts(fixture_pdf)

    assert len(facts) >= 5


def test_every_text_fact_carries_a_populated_span(fixture_pdf):
    for fact in extract_text_facts(fixture_pdf):
        assert fact.source_span
        assert fact.page is not None
        assert fact.origin == "text"


def test_every_span_resolves_back_to_its_own_text(fixture_pdf):
    """The citation contract: a span must read back as the fact it claims."""
    pages = _pages(fixture_pdf)

    for fact in extract_text_facts(fixture_pdf):
        source = resolve_span(fact.source_span, pages)
        assert source is not None
        assert " ".join(source.split()) == fact.text


def test_facts_are_normalized_to_single_spaces(fixture_pdf):
    for fact in extract_text_facts(fixture_pdf):
        assert "\n" not in fact.text
        assert "  " not in fact.text


def test_short_fragments_are_dropped():
    pages = ["Q3 Results. " + "The company shipped four hundred units last year."]

    facts = facts_from_pages(pages)

    assert all(len(f.text.split()) >= MIN_FACT_WORDS for f in facts)
    assert any("four hundred units" in f.text for f in facts)


def test_a_page_with_no_text_layer_yields_nothing():
    assert facts_from_pages(["", "   \n  "]) == []


def test_spans_are_page_local():
    pages = ["First page sentence here now.", "Second page sentence here now."]

    facts = facts_from_pages(pages)

    assert facts[0].source_span.startswith("p1:")
    assert facts[1].source_span.startswith("p2:")
    # Page 2's offsets restart, rather than continuing from page 1.
    assert facts[1].source_span.endswith(f"0-{len(pages[1])}")


@pytest.mark.parametrize(
    "span",
    ["", "garbage", "p0:0-5", "p9:0-5", "p1:5-2", "p1:0-9999", "p1:-1-5"],
)
def test_unresolvable_spans_return_none(span):
    assert resolve_span(span, ["Some page text."]) is None


# ---------------------------------------------------------------------------
# Grounding gate
# ---------------------------------------------------------------------------


def test_a_fact_whose_span_does_not_match_is_dropped():
    pages = ["The company shipped four hundred units last year."]
    fabricated = Fact(
        text="The company shipped nine million units last year.",
        source_span=f"p1:0-{len(pages[0])}",
        page=1,
        origin="text",
    )

    assert verify_facts([fabricated], pages) == []


def test_a_fact_with_an_unresolvable_span_is_dropped():
    pages = ["The company shipped four hundred units last year."]
    orphan = Fact(text="Anything at all here", source_span="p7:0-10", page=7, origin="text")

    assert verify_facts([orphan], pages) == []


def test_genuine_facts_survive_verification(fixture_pdf):
    pages = _pages(fixture_pdf)

    facts = facts_from_pages(pages)

    assert verify_facts(facts, pages) == facts


def test_vision_facts_bypass_span_verification():
    """They have no offsets to check — they are asserted, not proven."""
    vision = Fact(
        text="A claim read off a rendered page.",
        source_span="p2:vision",
        page=2,
        confidence=VISION_CONFIDENCE,
        origin="vision",
    )

    assert verify_facts([vision], ["unrelated page text"]) == [vision]


# ---------------------------------------------------------------------------
# Vision path selection
# ---------------------------------------------------------------------------


def test_the_table_page_is_selected_for_vision(fixture_pdf):
    """Page 2 is a vector table: enough characters to exist, too few to parse."""
    pages = _pages(fixture_pdf)

    assert len(pages[1].strip()) < MIN_PAGE_TEXT_CHARS
    assert pages_needing_vision(pages) == [2]


def test_dense_pages_are_not_sent_to_vision():
    assert pages_needing_vision(["x" * (MIN_PAGE_TEXT_CHARS + 1)]) == []


def test_force_selects_every_page():
    assert pages_needing_vision(["x" * 5000, "y" * 5000], force=True) == [1, 2]


# ---------------------------------------------------------------------------
# Vision rendering
# ---------------------------------------------------------------------------


def test_rendered_page_is_a_png(fixture_pdf):
    data = render_page_png(fixture_pdf, 1)

    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_respects_the_long_edge_ceiling(fixture_pdf):
    """Cost control: full resolution is ~3x the image tokens for no gain here."""
    data = render_page_png(fixture_pdf, 1)

    with pymupdf.open(stream=data, filetype="png") as rendered:
        page = rendered[0]
        assert max(page.rect.width, page.rect.height) <= MAX_IMAGE_DIMENSION


def test_render_rejects_an_out_of_range_page(fixture_pdf):
    with pytest.raises(IndexError):
        render_page_png(fixture_pdf, 99)


def test_page_images_covers_every_page(fixture_pdf):
    with pymupdf.open(fixture_pdf) as doc:
        expected = doc.page_count

    assert len(page_images(fixture_pdf)) == expected


def test_rendering_accepts_bytes_as_well_as_a_path(fixture_pdf):
    """The API holds uploads in memory, so the vision path never sees a path."""
    data = fixture_pdf.read_bytes()

    assert render_page_png(data, 1) == render_page_png(fixture_pdf, 1)
    assert len(page_images(data)) == len(page_images(fixture_pdf))


async def test_vision_ingest_from_bytes_reaches_the_table_page(fixture_pdf):
    """The path that failed in the API walk: bytes in, vision facts out."""
    llm = FakeVisionLLM(["Chicago-Dallas moved 184,000 shipments."])

    facts = await ingest_pdf_bytes(fixture_pdf.read_bytes(), llm)

    assert llm.calls == 1
    assert [f.source_span for f in facts if f.origin == "vision"] == ["p2:vision"]


def test_encode_produces_bare_base64():
    encoded = encode_image_base64(b"\x89PNG\r\n\x1a\n")

    assert "data:" not in encoded
    assert "\n" not in encoded


def test_message_carries_image_then_text():
    message = image_to_message(b"\x89PNG", "Read this page.")

    assert message["role"] == "user"
    image_block, text_block = message["content"]
    assert image_block["type"] == "image"
    assert image_block["source"]["media_type"] == "image/png"
    assert text_block["text"] == "Read this page."


# ---------------------------------------------------------------------------
# End-to-end ingest
# ---------------------------------------------------------------------------


async def test_vision_facts_are_extracted_from_the_table_page(fixture_pdf):
    llm = FakeVisionLLM(["Chicago-Dallas moved 184,000 shipments at 96.2 percent."])

    facts = await ingest_pdf(fixture_pdf, llm)

    vision_facts = [f for f in facts if f.origin == "vision"]
    assert llm.calls == 1
    assert len(vision_facts) == 1
    assert vision_facts[0].page == 2
    assert vision_facts[0].source_span == "p2:vision"
    assert vision_facts[0].confidence == VISION_CONFIDENCE


async def test_ingest_without_an_llm_degrades_to_text_only(fixture_pdf):
    """No provider means no vision facts — the offline paths still run.

    Text and tables are both local, so the assertion is that nothing *asserted*
    (vision) appears, not that every fact came from the sentence splitter.
    """
    facts = await ingest_pdf(fixture_pdf, llm=None)

    assert len(facts) >= 5
    assert not [f for f in facts if f.origin == "vision"]


async def test_a_failed_vision_call_does_not_lose_the_text_facts(fixture_pdf):
    llm = FakeVisionLLM(error=True)

    facts = await ingest_pdf(fixture_pdf, llm)

    assert llm.calls == 1
    assert len(facts) >= 5
    assert not [f for f in facts if f.origin == "vision"]


async def test_blank_vision_claims_are_discarded(fixture_pdf):
    llm = FakeVisionLLM(["", "   "])

    facts = await ingest_pdf(fixture_pdf, llm)

    assert [f for f in facts if f.origin == "vision"] == []


async def test_ingest_from_bytes_matches_ingest_from_path(fixture_pdf):
    from_path = await ingest_pdf(fixture_pdf, llm=None)
    from_bytes = await ingest_pdf_bytes(fixture_pdf.read_bytes(), llm=None)

    assert from_bytes == from_path


async def test_extract_vision_facts_on_a_missing_page_returns_nothing(fixture_pdf):
    llm = FakeVisionLLM()

    assert await extract_vision_facts(fixture_pdf, 99, llm) == []
    assert llm.calls == 0
