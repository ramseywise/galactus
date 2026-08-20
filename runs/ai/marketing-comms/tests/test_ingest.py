"""Hybrid ingest: the text path, the vision path, and the grounding gate.

The vision path is exercised against a scripted fake rather than a live model —
same reason as the repair-loop tests. The fixture PDFs are real, though: the
text path runs against actual pymupdf extraction, because the offsets it
produces are the whole point and a mocked extractor would prove nothing.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from fakes import ScriptedLLM as FakeVisionLLM

from ingest.facts import (
    MIN_PAGE_TEXT_CHARS,
    VISION_CONFIDENCE,
    PageLimitError,
    _drop_table_overlaps,
    extract_vision_facts,
    ingest_pdf,
    ingest_pdf_bytes,
    pages_needing_vision,
    pdf_page_count,
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
    render_page_png,
    render_pages,
)
from models import Fact

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SENDER_PDF = FIXTURE_DIR / "sender.pdf"
RECEIVER_PDF = FIXTURE_DIR / "receiver.pdf"


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


def test_render_pages_covers_every_requested_page(fixture_pdf):
    with pymupdf.open(fixture_pdf) as doc:
        expected = list(range(1, doc.page_count + 1))

    images = render_pages(fixture_pdf, expected)

    assert sorted(images) == expected
    assert all(data.startswith(b"\x89PNG\r\n\x1a\n") for data in images.values())


def test_render_pages_skips_out_of_range_pages(fixture_pdf):
    images = render_pages(fixture_pdf, [1, 99])

    assert list(images) == [1]
    assert render_pages(fixture_pdf, [99]) == {}


def test_rendering_accepts_bytes_as_well_as_a_path(fixture_pdf):
    """The API holds uploads in memory, so the vision path never sees a path."""
    data = fixture_pdf.read_bytes()

    assert render_page_png(data, 1) == render_page_png(fixture_pdf, 1)
    assert render_pages(data, [1]) == render_pages(fixture_pdf, [1])


async def test_vision_ingest_from_bytes_reaches_the_table_page(fixture_pdf):
    """The path that failed in the API walk: bytes in, vision facts out."""
    llm = FakeVisionLLM(vision_facts=["Chicago-Dallas moved 184,000 shipments."])

    facts = await ingest_pdf_bytes(fixture_pdf.read_bytes(), llm)

    assert llm.calls == 1
    assert [f.source_span for f in facts if f.origin == "vision"] == ["p2:vision"]


async def test_vision_calls_attach_the_rendered_page(fixture_pdf):
    """The port regression: the model must receive the page it is asked to read."""
    llm = FakeVisionLLM()

    await ingest_pdf(fixture_pdf, llm)

    assert llm.calls == 1
    (images,) = llm.images
    assert len(images) == 1
    assert images[0].startswith(b"\x89PNG\r\n\x1a\n")
    assert images[0] == render_page_png(fixture_pdf, 2)


def test_encode_produces_bare_base64():
    encoded = encode_image_base64(b"\x89PNG\r\n\x1a\n")

    assert "data:" not in encoded
    assert "\n" not in encoded


# ---------------------------------------------------------------------------
# End-to-end ingest
# ---------------------------------------------------------------------------


async def test_vision_facts_are_extracted_from_the_table_page(fixture_pdf):
    llm = FakeVisionLLM(vision_facts=["Chicago-Dallas moved 184,000 shipments at 96.2 percent."])

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
    llm = FakeVisionLLM(vision_facts=["", "   "])

    facts = await ingest_pdf(fixture_pdf, llm)

    assert [f for f in facts if f.origin == "vision"] == []


async def test_ingest_from_bytes_matches_ingest_from_path(fixture_pdf):
    from_path = await ingest_pdf(fixture_pdf, llm=None)
    from_bytes = await ingest_pdf_bytes(fixture_pdf.read_bytes(), llm=None)

    assert from_bytes == from_path


async def test_extract_vision_facts_tags_the_page_it_was_given(fixture_pdf):
    llm = FakeVisionLLM(vision_facts=["A chart shows 42 percent growth."])
    image = render_page_png(fixture_pdf, 2)

    facts = await extract_vision_facts(image, 2, llm)

    assert [f.source_span for f in facts] == ["p2:vision"]
    assert facts[0].confidence == VISION_CONFIDENCE


def test_prose_sharing_a_page_with_a_table_is_kept():
    """Only the table's own region is superseded — the paragraph next to it stays."""
    prose = Fact(text="A paragraph claim.", source_span="p1:0-18", page=1, origin="text")
    run_on = Fact(text="Grid soup.", source_span="p1:40-80", page=1, origin="text")
    table = Fact(
        text="Corridor X: Volume 1.",
        source_span="p1:50-70",
        page=1,
        origin="table",
        cells=["X", "1"],
    )

    assert _drop_table_overlaps([prose, run_on], [table]) == [prose]


# ---------------------------------------------------------------------------
# Page cap
# ---------------------------------------------------------------------------


def _pdf_with_pages(count: int) -> bytes:
    doc = pymupdf.open()
    for number in range(count):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {number + 1}")
    return doc.tobytes()


async def test_ingest_rejects_a_pdf_over_the_page_cap():
    """Over the cap is a refusal, not a silent truncation — a brief grounded
    on the first N pages of a longer deck would misreport its grounding."""
    with pytest.raises(PageLimitError, match="3 pages"):
        await ingest_pdf_bytes(_pdf_with_pages(3), None, max_pages=2)


async def test_ingest_at_the_cap_proceeds():
    facts = await ingest_pdf_bytes(_pdf_with_pages(3), None, max_pages=3)

    assert isinstance(facts, list)  # sparse pages yield nothing, but it ran


def test_pdf_page_count_reads_the_document():
    assert pdf_page_count(_pdf_with_pages(2)) == 2


def test_pdf_page_count_raises_on_unreadable_bytes():
    with pytest.raises(Exception):  # noqa: B017 - pymupdf's error types are its own
        pdf_page_count(b"%PDF-1.4 not actually a pdf")
