"""Tests for the table path.

The claim under test is narrow and worth stating: a value extracted from a
table stays attached to the row it came from, and a fact that drifts onto
another row does not survive verification. Everything else here defends the
boundaries where the path declines to act.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from galactus.ingest.facts import verify_facts
from galactus.ingest.tables import (
    MAX_CELL_CHARS,
    facts_from_table,
    row_span_contains_cells,
)
from models import Fact

FIXTURES = Path(__file__).parent / "fixtures"

CORRIDOR_PAGE = (
    "Lane performance by corridor\n"
    "Corridor\nVolume\nOn-time\n"
    "Chicago-Dallas\n184,000\n96.2%\n"
    "Newark-Atlanta\n141,500\n93.8%\n"
)

CORRIDOR_ROWS: list[list[str | None]] = [
    ["Corridor", "Volume", "On-time"],
    ["Chicago-Dallas", "184,000", "96.2%"],
    ["Newark-Atlanta", "141,500", "93.8%"],
]


def test_each_data_row_becomes_one_fact() -> None:
    facts = facts_from_table(CORRIDOR_ROWS, CORRIDOR_PAGE, 2)

    assert len(facts) == 2
    assert all(fact.origin == "table" for fact in facts)


def test_row_fact_keeps_its_subject_with_each_value() -> None:
    """The whole point: 96.2% is stated as Chicago-Dallas's on-time rate.

    The run-on text the sentence splitter produces contains the same digits but
    no way to tell which corridor they belong to.
    """
    facts = facts_from_table(CORRIDOR_ROWS, CORRIDOR_PAGE, 2)

    assert facts[0].text == "Corridor Chicago-Dallas: Volume 184,000; On-time 96.2%."


def test_row_facts_verify_against_the_page() -> None:
    facts = facts_from_table(CORRIDOR_ROWS, CORRIDOR_PAGE, 2)

    assert verify_facts(facts, ["", CORRIDOR_PAGE]) == facts


def test_a_row_fact_citing_another_rows_span_is_dropped() -> None:
    """The misattribution guard.

    A fact claiming Chicago-Dallas's numbers while pointing at the
    Newark-Atlanta span is the exact failure the row rule exists to catch: the
    digits are real and on the page, but not in the span cited.
    """
    honest, other = facts_from_table(CORRIDOR_ROWS, CORRIDOR_PAGE, 2)
    misattributed = honest.model_copy(update={"source_span": other.source_span})

    assert verify_facts([misattributed], ["", CORRIDOR_PAGE]) == []


def test_span_resolves_to_the_rows_own_cells() -> None:
    fact = facts_from_table(CORRIDOR_ROWS, CORRIDOR_PAGE, 2)[0]
    _, _, offsets = fact.source_span.partition(":")
    start, _, end = offsets.partition("-")
    source = CORRIDOR_PAGE[int(start) : int(end)]

    assert "Chicago-Dallas" in source
    assert "Newark-Atlanta" not in source


def test_header_only_table_yields_nothing() -> None:
    assert facts_from_table([["Corridor", "Volume"]], CORRIDOR_PAGE, 2) == []


def test_empty_table_yields_nothing() -> None:
    assert facts_from_table([], CORRIDOR_PAGE, 2) == []


def test_row_absent_from_the_page_is_dropped() -> None:
    """An unlocatable row gets no fact rather than an unverifiable one."""
    rows: list[list[str | None]] = [
        ["Corridor", "Volume", "On-time"],
        ["Phantom-Route", "1", "2%"],
    ]

    assert facts_from_table(rows, CORRIDOR_PAGE, 2) == []


def test_prose_cells_are_left_to_the_text_path() -> None:
    rows: list[list[str | None]] = [
        ["Topic", "Detail"],
        ["Summary", "x" * (MAX_CELL_CHARS + 1)],
    ]
    page = "Topic\nDetail\nSummary\n" + "x" * (MAX_CELL_CHARS + 1)

    assert facts_from_table(rows, page, 1) == []


def test_none_cells_are_tolerated() -> None:
    """pymupdf yields None for a blank cell; a partial row is still a fact."""
    rows: list[list[str | None]] = [
        ["Corridor", "Volume", "On-time"],
        ["Chicago-Dallas", None, "96.2%"],
    ]
    facts = facts_from_table(rows, CORRIDOR_PAGE, 2)

    assert len(facts) == 1
    assert facts[0].text == "Corridor Chicago-Dallas: On-time 96.2%."


def test_row_span_contains_cells_rejects_a_missing_value() -> None:
    source = "Chicago-Dallas 184,000 96.2%"

    assert row_span_contains_cells(source, "Corridor Chicago-Dallas: Volume 184,000.")
    assert not row_span_contains_cells(source, "Corridor Chicago-Dallas: Volume 999,999.")


def test_table_origin_does_not_bypass_span_resolution() -> None:
    """A table fact with an unresolvable span is still dropped.

    The relaxed rule changes *how* a table fact is checked, not *whether* it is.
    """
    fact = Fact(
        text="Corridor Chicago-Dallas: Volume 184,000.",
        source_span="p9:0-10",
        page=9,
        origin="table",
    )

    assert verify_facts([fact], ["", CORRIDOR_PAGE]) == []


@pytest.mark.parametrize("name", ["sender.pdf", "receiver.pdf"])
def test_fixture_tables_survive_the_full_ingest(name: str) -> None:
    """End-to-end: the shipped fixtures each carry a table that reaches facts."""
    from ingest.facts import ingest_pdf

    facts = asyncio.run(ingest_pdf(FIXTURES / name))
    table_facts = [fact for fact in facts if fact.origin == "table"]

    assert len(table_facts) == 3
    assert all(":" in fact.text for fact in table_facts)


def test_table_page_text_is_not_also_emitted_as_a_run_on_fact() -> None:
    """The regression this path exists to fix.

    Before the table path, page 2 of each fixture produced a single fact
    containing every cell in the grid with no row structure. It must not
    reappear alongside the structured rows.
    """
    from ingest.facts import ingest_pdf

    facts = asyncio.run(ingest_pdf(FIXTURES / "sender.pdf"))
    page_two_text_facts = [fact for fact in facts if fact.page == 2 and fact.origin == "text"]

    assert page_two_text_facts == []
