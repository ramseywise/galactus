"""`graph_to_passages()`: the seam from cap-kg.md:280, turning hop rows into passages.

Each passage is the evidence quote plus one sentence of the body that follows it, stamped
with tier, build, source path, hop and freshness. Freshness is tri-state and conservative:
only a build whose profile hash equals the current corpus profile is `fresh`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from kg.store.protocol import Freshness, Passage, StoredTriple

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)|\n\n")

BodyLookup = Callable[[str], str | None]
"""Current normalised body for a page path, or None when it cannot be read."""


@dataclass(frozen=True)
class HopRow:
    stored: StoredTriple
    hop: int
    build_profile_hash: str


def _sentence_after(body: str, end: int) -> str:
    """The rest of the quote's sentence plus the next sentence, from offset `end`."""
    cut = end
    ends_sentence = _SENTENCE_END.match(body, max(end - 1, 0)) is not None
    for _ in range(1 if ends_sentence else 2):
        m = _SENTENCE_END.search(body, cut)
        if m is None:
            return body[end:].rstrip()
        cut = m.end()
        if m.group() == "\n\n":
            break
    return body[end:cut].rstrip()


def _freshness(row: HopRow, current_profile_hash: str | None, body: str | None) -> Freshness:
    if current_profile_hash is not None and row.build_profile_hash == current_profile_hash:
        return "fresh"
    if body is not None and row.stored.evidence.quote not in body:
        return "stale"
    return "unverified"


def graph_to_passages(
    rows: Iterable[HopRow],
    *,
    current_profile_hash: str | None = None,
    body_lookup: BodyLookup | None = None,
) -> list[Passage]:
    out: list[Passage] = []
    for row in rows:
        ev = row.stored.evidence
        body = body_lookup(ev.page_path) if body_lookup else None
        freshness = _freshness(row, current_profile_hash, body)
        text = ev.quote
        if body is not None and freshness == "fresh":
            start, end = ev.span
            if body[start:end] == ev.quote:
                text = (ev.quote + _sentence_after(body, end)).strip()
        out.append(
            Passage(
                text=text,
                tier=row.stored.tier,
                build_id=row.stored.build_id,
                source_path=ev.page_path,
                hop=row.hop,
                freshness=freshness,
                triple=row.stored.triple,
            )
        )
    return out
