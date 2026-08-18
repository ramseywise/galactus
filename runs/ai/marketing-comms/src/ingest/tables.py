"""The table path: turn a grid back into row-scoped facts.

The case study names tables alongside text and images, and they are the one
input kind the sentence splitter actively destroys rather than merely handling
imperfectly. A PDF table has no sentence terminators, so `get_text()` emits it
as one cell per line:

    Corridor\\nVolume\\nOn-time\\nChicago-Dallas\\n184,000\\n96.2%\\n...

`_facts_from_page` glues that into a single run-on fact — every metric in the
table, stripped of the row and column that say what each number *measures*.
A model handed that soup can attribute 96.2% to any corridor in the grid and
still look grounded, because the digits really are in the source. Misattributed
metrics are precisely the "factually correct" failure this pipeline exists to
prevent, so tables get their own path.

**One fact per data row**, rendered against the header:

    Corridor Chicago-Dallas: Volume 184,000; On-time 96.2%.

The row is the unit because it is the smallest span in which a value keeps its
subject. Cell-level facts ("184,000") carry no subject at all; table-level facts
reproduce the original ambiguity.

## Staying verifiable

`verify_facts` drops any non-vision fact whose `source_span` does not read back
equal to its text, which a rewritten row can never satisfy. Table facts are
therefore verified on a different rule, declared by `origin="table"`: the span
covers the row's cells as they appear in the page text, and
`row_span_contains_cells` checks that **every** cell value is present in it.

The values checked are the full cells, carried on `Fact.cells` — not tokens
re-parsed from the rendered sentence, which for a multi-word cell would verify
only its last word. A table fact without `cells` fails verification outright:
nothing in this codebase produces one, so one that appears is fabricated.

That keeps the guarantee that matters — every number is traceable to the page —
while allowing the row to be phrased so the subject survives. It is a real
weakening of the exact-match rule, and it is scoped to this origin rather than
loosened for everyone.
"""

from __future__ import annotations

from models import Fact

MIN_TABLE_ROWS = 2
"""A header plus at least one data row. Below this there is no grid to rescue."""

MAX_CELL_CHARS = 120
"""Cells longer than this are prose in a bordered box, not tabular data.

Rendering a paragraph as `Header value: <paragraph>` produces a fact that is
worse than the sentence splitter's version, so such tables are left alone.
"""


def facts_from_table(
    rows: list[list[str | None]],
    page_text: str,
    page_number: int,
) -> list[Fact]:
    """Render a table's data rows as one fact each.

    `rows[0]` is the header. Returns an empty list when the grid is too small,
    holds prose rather than data, or cannot be located in `page_text` — every
    one of which is a reason to leave the text path's output in place rather
    than emit something unverifiable.
    """
    if len(rows) < MIN_TABLE_ROWS:
        return []

    header = [_clean(cell) for cell in rows[0]]
    if not any(header):
        return []

    facts: list[Fact] = []

    for row in rows[1:]:
        cells = [_clean(cell) for cell in row]
        if not any(cells):
            continue
        if any(len(cell) > MAX_CELL_CHARS for cell in cells):
            continue

        span = _row_span(cells, page_text, page_number)
        if span is None:
            continue

        facts.append(
            Fact(
                text=_render_row(header, cells),
                source_span=span,
                page=page_number,
                confidence=1.0,
                origin="table",
                cells=[cell for cell in cells if cell],
            )
        )

    return facts


def row_span_contains_cells(source: str, fact: Fact) -> bool:
    """Whether every cell value a table fact asserts appears in its source span.

    The verification rule for `origin="table"`, standing in for the exact-match
    check that a rewritten row cannot pass. The full cell values come from
    `fact.cells` — checking tokens parsed back out of the rendered sentence
    would verify only the last word of a multi-word cell, letting a span that
    drifted onto different content pass on a shared trailing token.

    Fails closed on a fact with no cells: every fact this package produces
    carries them, so their absence marks a fact nothing extracted.
    """
    if not fact.cells:
        return False
    return all(value in source for value in fact.cells)


def _render_row(header: list[str], cells: list[str]) -> str:
    """Render one row as a sentence that carries its own subject.

    The first column is the subject: in a data table it is the row label, and
    naming it up front is what stops the value from floating free of what it
    describes.
    """
    subject_header, subject = header[0], cells[0]
    lead = f"{subject_header} {subject}".strip() if subject_header else subject

    # strict=False on purpose: a ragged row is normal in extracted PDF tables, and
    # truncating to the shorter of the two beats raising on a real document.
    pairs = [
        f"{head} {value}".strip() if head else value
        for head, value in zip(header[1:], cells[1:], strict=False)
        if value
    ]

    if not pairs:
        return f"{lead}."
    return f"{lead}: {'; '.join(pairs)}."


def _row_span(cells: list[str], page_text: str, page_number: int) -> str | None:
    """Span covering this row's cells where they sit in the page text.

    Every occurrence of the first cell is tried as an anchor, and the tightest
    span that covers all cells in order wins. Anchoring on the first occurrence
    alone would let a subject that also appears in a caption or a paragraph
    above the table pull the span across unrelated text — an over-wide span
    that contains the cells but does not correspond to the row.

    Returns None if no anchor works — an unlocatable row is one this module
    declines to make a claim about.
    """
    non_empty = [cell for cell in cells if cell]
    if not non_empty:
        return None

    best: tuple[int, int] | None = None
    anchor = page_text.find(non_empty[0])

    while anchor != -1:
        cursor = anchor
        for cell in non_empty:
            found = page_text.find(cell, cursor)
            if found == -1:
                cursor = -1
                break
            cursor = found + len(cell)

        if cursor != -1 and (best is None or cursor - anchor < best[1] - best[0]):
            best = (anchor, cursor)

        anchor = page_text.find(non_empty[0], anchor + 1)

    if best is None:
        return None
    return f"p{page_number}:{best[0]}-{best[1]}"


def _clean(cell: str | None) -> str:
    """Normalize a cell: pymupdf yields None for empty cells and keeps newlines."""
    if cell is None:
        return ""
    return " ".join(cell.split())
