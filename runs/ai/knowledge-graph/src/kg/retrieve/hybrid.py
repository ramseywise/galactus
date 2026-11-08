"""Hybrid `ask`: Librarian entry rows -> entity match in the store -> hops -> passages.

Statuses (fog FA-008): `entry_miss` (no entity the store knows), `no_hops` (known entity,
nothing reachable at the requested tiers), `degraded` (Librarian flagged DEGRADED; never
dropped, passages still returned), `ok`. Quotes are re-checked against the current
normalised body at serve time, so a quote edited out after the build comes back `stale`
(fog FA-007). Defaults never return a review-tier passage.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from kg.config import Settings
from kg.models import ACCEPT_ONLY, ALL_TIERS, Tier
from kg.profile.normalise import norm_surface, normalise
from kg.retrieve.librarian_baseline import Baseline, BaselineResult, Row
from kg.store import HARD_MAX_K, GraphStore, Passage

AskStatus = Literal["ok", "entry_miss", "no_hops", "degraded"]
INCLUDE_REVIEW: frozenset[Tier] = frozenset({"accept", "review"})
MAX_NGRAM = 4
MAX_CANDIDATES = 500
_WORD = re.compile(r"[\w][\w\-./+]*")


@dataclass(frozen=True)
class AskResult:
    status: AskStatus
    passages: tuple[Passage, ...]
    entities: tuple[str, ...] = ()
    """Entity surface forms the store recognised (normalised)."""
    degraded: tuple[str, ...] = ()
    graph_status: Literal["ok", "entry_miss", "no_hops"] = "ok"
    """What the graph side found, kept when `status` is `degraded`."""
    baseline: BaselineResult | None = field(default=None, compare=False)


def effective_k(settings: Settings, k: int) -> int:
    """Hop depth never exceeds `KG_MAX_HOPS` (nor the store's hard cap)."""
    return max(1, min(k, settings.max_hops, HARD_MAX_K))


def candidate_surfaces(rows: Iterable[Row]) -> set[str]:
    """Surface-form candidates from entry rows: titles, tags, path stems, title/summary n-grams."""
    out: list[str] = []
    for r in rows:
        out += [r.title, r.path.rsplit("/", 1)[-1].removesuffix(".md")]
        out += [t for t in re.split(r"[,\s]+", r.tags) if t]
        for text in (r.title, r.summary):
            words = _WORD.findall(text)
            for n in range(1, MAX_NGRAM + 1):
                out += [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
    seen: dict[str, str] = {}
    for s in out:
        seen.setdefault(norm_surface(s), s)
        if len(seen) >= MAX_CANDIDATES:
            break
    return {v for k, v in seen.items() if k}


def known_entities(store: GraphStore, surfaces: set[str], build_id: str | None) -> set[str]:
    """Which of `surfaces` the store has any triple for, at any tier (via public `hops`)."""
    if not surfaces:
        return set()
    wanted = {norm_surface(s) for s in surfaces}
    found: set[str] = set()
    for t in store.hops(surfaces, 1, ALL_TIERS, build_id=build_id):
        for name in (t.subject, t.object):
            if norm_surface(name) in wanted:
                found.add(norm_surface(name))
    return found


def _recheck(store: GraphStore, passages: list[Passage], corpus_root: Path | None) -> list[Passage]:
    """Re-run the substring check of each quote against the current normalised body."""
    if corpus_root is None:
        return passages
    quotes: dict[str, dict[tuple[str, str, str, str], str]] = {}
    bodies: dict[str, str | None] = {}
    out: list[Passage] = []
    for p in passages:
        if p.build_id not in quotes:
            quotes[p.build_id] = {
                (s.triple.subject, s.triple.relation, s.triple.object, s.triple.page_path): (
                    s.evidence.quote
                )
                for s in store.triples(p.build_id)
            }
        t = p.triple
        quote = quotes[p.build_id].get((t.subject, t.relation, t.object, t.page_path))
        if quote is None:
            out.append(p)
            continue
        if p.source_path not in bodies:
            f = corpus_root / p.source_path
            bodies[p.source_path] = (
                normalise(f.read_text(encoding="utf-8")) if f.is_file() else None
            )
        body = bodies[p.source_path]
        fresh = body is not None and quote in body
        out.append(p.model_copy(update={"freshness": "fresh" if fresh else "stale"}))
    return out


def ask(
    store: GraphStore,
    *,
    settings: Settings,
    query: str | None = None,
    entities: Iterable[str] | None = None,
    baseline: Baseline | None = None,
    k: int = 1,
    include_review: bool = False,
    build_id: str | None = None,
    limit: int = 5,
) -> AskResult:
    """Answer from the graph. Give `entities` directly (no Librarian) or a `query` plus an
    injected `baseline` whose entry rows seed the entity match."""
    surfaces: set[str] = set(entities or ())
    base: BaselineResult | None = None
    if query is not None:
        if baseline is None:
            raise ValueError("a query needs a baseline; pass entities= to skip Librarian")
        base = baseline(query, limit)
        surfaces |= candidate_surfaces(base.rows)
    if not surfaces:
        raise ValueError("ask needs entities or a query")
    degraded = base.degraded if base else ()

    known = known_entities(store, surfaces, build_id)
    tiers = INCLUDE_REVIEW if include_review else ACCEPT_ONLY
    passages: list[Passage] = []
    graph_status: Literal["ok", "entry_miss", "no_hops"]
    if not known:
        graph_status = "entry_miss"
    else:
        passages = store.passages(
            known, effective_k(settings, k), tiers, build_id=build_id, current_profile_hash=None
        )
        passages = _recheck(store, passages, settings.corpus_root)
        if not include_review:
            passages = [p for p in passages if p.tier == "accept"]
        graph_status = "ok" if passages else "no_hops"
    return AskResult(
        status="degraded" if degraded else graph_status,
        passages=tuple(passages),
        entities=tuple(sorted(known)),
        degraded=tuple(degraded),
        graph_status=graph_status,
        baseline=base,
    )
