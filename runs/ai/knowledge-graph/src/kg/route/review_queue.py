"""Render the review band and apply a human decision file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from kg.models import Tier
from kg.store.protocol import GraphStore, StoredTriple

Decision = Literal["accept", "reject"]


def review_rows(store: GraphStore, build_id: str) -> list[StoredTriple]:
    return [st for st in store.triples(build_id) if st.tier == "review"]


def render_table(rows: list[StoredTriple]) -> str:
    """Plain-text table, one row per review-tier triple, lowest score first.

    The `key` column is what a decision file refers to: a JSON list
    [subject_norm, relation, object_norm, page_path].
    """
    if not rows:
        return "review queue empty"
    ordered = sorted(rows, key=lambda st: st.judgement.score)
    head = ("score", "seat", "subject", "relation", "object", "page", "quote")
    body = [
        (
            f"{st.judgement.score:.2f}",
            st.judgement.seat,
            st.triple.subject,
            st.triple.relation,
            st.triple.object,
            st.triple.page_path,
            st.evidence.quote.replace("\n", " ")[:60],
        )
        for st in ordered
    ]
    widths = [max(len(r[i]) for r in [head, *body]) for i in range(len(head))]
    lines = [
        "  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip()
        for r in [head, *body]
    ]
    return "\n".join(lines)


def load_decisions(path: Path) -> dict[tuple[str, ...], Decision]:
    """JSONL, one object per line: {"key": [s_norm, rel, o_norm, page], "decision": "accept"|"reject"}."""
    out: dict[tuple[str, ...], Decision] = {}
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        key, decision = obj.get("key"), obj.get("decision")
        if not isinstance(key, list) or len(key) != 4 or decision not in ("accept", "reject"):
            raise ValueError(f"{path}:{n}: expected {{key: [4 strings], decision: accept|reject}}")
        out[tuple(key)] = decision
    return out


def apply_decisions(store: GraphStore, build_id: str, decisions_path: Path) -> int:
    """Re-write each decided review-tier triple with its human tier; returns how many.

    Raises ValueError on a key that is not a review-tier row of this build, before any write.
    """
    decisions = load_decisions(decisions_path)
    queue = {st.triple.key: st for st in review_rows(store, build_id)}
    unknown = [k for k in decisions if k not in queue]
    if unknown:
        raise ValueError(f"decisions for keys not in the review queue: {unknown}")
    for key, decision in decisions.items():
        st = queue[key]
        tier: Tier = decision
        store.write_triple(build_id, st.triple, st.evidence, st.judgement, tier)
    return len(decisions)
