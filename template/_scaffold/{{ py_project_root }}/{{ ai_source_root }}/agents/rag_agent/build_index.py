"""Embeds the same preprocessed corpus core/pipelines/corpus/ingestion.py produces for lg_agent's
FTS index, and stores it in rag_agent's own vector store (backend chosen by
settings.vector_backend) — same source articles, two different retrieval
mechanisms side by side."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agents.rag_agent.vectorstore import get_vector_index

log = logging.getLogger(__name__)


def build_index(jsonl_path: Path) -> int:
    rows = []
    skipped = 0
    for lineno, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            skipped += 1
            log.warning("skipping malformed JSONL line %d in %s: %s", lineno, jsonl_path, exc)
    if skipped:
        log.warning(
            "skipped %d malformed line(s) while building index from %s",
            skipped,
            jsonl_path,
        )
    index = get_vector_index()
    index.upsert([(row["id"], row["title"], row["text"]) for row in rows])
    return len(rows)
