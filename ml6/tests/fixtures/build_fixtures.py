"""Generate the fixture PDFs the ingest tests read.

Checked in as a script, not run at test time. The PDFs are binary fixtures that
should stay byte-stable across runs — regenerating them on every test session
would make an ingest regression look like a fixture change. Re-run by hand when
the fixtures need to change:

    uv run python tests/fixtures/build_fixtures.py

Page 2 of each document is the point of the exercise: a table drawn as vector
strokes and positioned cell text, which is what a real design-tool export looks
like. Its extracted text layer is deliberately sparse enough to trip
`MIN_PAGE_TEXT_CHARS`, so `pages_needing_vision` selects it.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

FIXTURE_DIR = Path(__file__).parent

_BODY_FONT = "helv"
_MARGIN = 72.0
_LINE_HEIGHT = 16.0

SENDER_PROSE = [
    "Meridian Freight operates 41 distribution centres across North America.",
    "The company moved 2.4 million shipments in the 2025 fiscal year.",
    "Meridian reduced average dwell time to 11 hours in the third quarter.",
    "Its fleet runs 1,850 tractors and 6,200 trailers under direct control.",
    "The firm has held an on-time delivery rate above 94 percent since 2023.",
    "Meridian employs 12,400 people, of whom 8,900 are drivers or dock staff.",
]

RECEIVER_PROSE = [
    "Calder Retail Group runs 512 stores in 31 states and two provinces.",
    "The group processed 88 million customer orders during the last year.",
    "Calder committed to same-day fulfilment in 24 metropolitan markets.",
    "Its distribution network currently spans six regional warehouses.",
    "The retailer reported inventory turns of 7.1 across all categories.",
    "Calder opened 38 new locations while closing 11 underperforming sites.",
]

SENDER_TABLE = {
    "title": "Lane performance by corridor",
    "headers": ["Corridor", "Volume", "On-time"],
    "rows": [
        ["Chicago-Dallas", "184,000", "96.2%"],
        ["Newark-Atlanta", "141,500", "93.8%"],
        ["Seattle-Denver", "98,300", "95.1%"],
    ],
}

RECEIVER_TABLE = {
    "title": "Fulfilment cost per order",
    "headers": ["Region", "Orders", "Cost"],
    "rows": [
        ["Northeast", "22.4M", "$4.18"],
        ["Southeast", "19.1M", "$3.92"],
        ["West", "26.8M", "$4.51"],
    ],
}


def build_pdf(path: Path, title: str, prose: list[str], table: dict) -> None:
    """Write a two-page PDF: a prose page and a vector-table page."""
    doc = pymupdf.open()

    page = doc.new_page()
    _draw_prose(page, title, prose)

    page = doc.new_page()
    _draw_table(page, table)

    doc.save(path)
    doc.close()


def _draw_prose(page: pymupdf.Page, title: str, prose: list[str]) -> None:
    page.insert_text((_MARGIN, _MARGIN), title, fontname=_BODY_FONT, fontsize=18)

    y = _MARGIN + 40
    for line in prose:
        page.insert_text((_MARGIN, y), line, fontname=_BODY_FONT, fontsize=11)
        y += _LINE_HEIGHT


def _draw_table(page: pymupdf.Page, table: dict) -> None:
    """Draw a table as strokes plus positioned cell text.

    The cells are individually positioned, so `get_text()` returns them in
    stroke order with no row structure and no sentence punctuation — enough
    characters to exist, not enough to parse into facts. That is precisely the
    case the vision path covers.
    """
    page.insert_text(
        (_MARGIN, _MARGIN), table["title"], fontname=_BODY_FONT, fontsize=14
    )

    col_x = [_MARGIN, _MARGIN + 160, _MARGIN + 280]
    row_y = _MARGIN + 40
    row_height = 26.0

    for index, header in enumerate(table["headers"]):
        page.insert_text(
            (col_x[index], row_y), header, fontname=_BODY_FONT, fontsize=10
        )

    for row_index, row in enumerate(table["rows"], start=1):
        y = row_y + row_index * row_height
        for col_index, cell in enumerate(row):
            page.insert_text(
                (col_x[col_index], y), cell, fontname=_BODY_FONT, fontsize=10
            )

    _draw_rules(page, col_x, row_y, row_height, len(table["rows"]))


def _draw_rules(
    page: pymupdf.Page,
    col_x: list[float],
    row_y: float,
    row_height: float,
    row_count: int,
) -> None:
    right = col_x[-1] + 120
    for index in range(row_count + 2):
        y = row_y + index * row_height - 12
        page.draw_line((col_x[0] - 6, y), (right, y))

    bottom = row_y + (row_count + 1) * row_height - 12
    for x in [*col_x, right]:
        page.draw_line((x - 6, row_y - 12), (x - 6, bottom))


def main() -> None:
    build_pdf(
        FIXTURE_DIR / "sender.pdf",
        "Meridian Freight — Company Overview",
        SENDER_PROSE,
        SENDER_TABLE,
    )
    build_pdf(
        FIXTURE_DIR / "receiver.pdf",
        "Calder Retail Group — Company Overview",
        RECEIVER_PROSE,
        RECEIVER_TABLE,
    )
    print(f"wrote sender.pdf and receiver.pdf to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
