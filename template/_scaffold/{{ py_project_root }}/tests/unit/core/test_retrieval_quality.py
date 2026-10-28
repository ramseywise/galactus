from __future__ import annotations

import json
from pathlib import Path

from core.pipelines.corpus.index import search

# pytest runs from the project root — see the comment in test_ingestion.py.
GOLDEN_QA_PATH = Path("data/raw_corpus/golden_qa.jsonl")
TOP_K = 3
# BM25 is a real (imperfect) retriever, not an exact-match oracle — some golden
# questions phrase things quite differently from the source article text, so we
# assert on an aggregate hit-rate rather than requiring every single question to
# retrieve its labeled source article in the top-k.
MIN_HIT_RATE = 0.6


def _load_golden_qa() -> list[dict[str, str]]:
    lines = GOLDEN_QA_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]


def test_golden_qa_file_has_expected_shape() -> None:
    rows = _load_golden_qa()

    assert len(rows) == 10
    for row in rows:
        assert {"id", "question", "expected_answer", "source_article", "category"} <= row.keys()


def test_search_retrieves_labeled_source_article_for_most_golden_questions(
    indexed_db: str,
) -> None:
    rows = _load_golden_qa()

    hits = 0
    for row in rows:
        results = search(indexed_db, row["question"], k=TOP_K)
        top_ids = [result.id for result in results]
        if row["source_article"] in top_ids:
            hits += 1

    hit_rate = hits / len(rows)
    assert hit_rate >= MIN_HIT_RATE, f"hit_rate={hit_rate} ({hits}/{len(rows)})"
