"""Heuristic, LLM-free graders for the golden QA set.

Two independent checks, both cheap enough to run on every commit:

- ``grade_retrieval``: did the article that actually answers the question show
  up (and at what rank) in the top-k results returned by ``core.pipelines.corpus.index.search``?
- ``grade_answer_overlap``: does the generated answer share enough vocabulary
  with the golden ``expected_answer`` to plausibly be addressing the same
  question? This is a coarse proxy for answer quality that needs no API key —
  it is not a substitute for an LLM-judge grader, just a free smoke check.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from core.pipelines.corpus.models import SearchResult

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Overlap ratios are computed over content words only; these are too common to
# carry signal about topical similarity.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "for",
        "from",
        "has",
        "have",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "over",
        "should",
        "that",
        "the",
        "to",
        "use",
        "using",
        "was",
        "were",
        "will",
        "with",
        "you",
        "your",
    }
)


class RetrievalGrade(BaseModel):
    query: str
    expected_id: str
    rank: int | None
    hit: bool
    top_k_ids: list[str]


class AnswerOverlapGrade(BaseModel):
    overlap_ratio: float
    matched_tokens: list[str]
    expected_tokens: list[str]


def grade_retrieval(query: str, expected_id: str, results: list[SearchResult]) -> RetrievalGrade:
    """Check whether ``expected_id`` appears in ``results`` and at what rank.

    ``results`` is assumed to already be ordered best-match-first (as returned
    by ``core.pipelines.corpus.index.search``), so rank is simply its 1-indexed position.
    """
    top_k_ids = [result.id for result in results]
    rank: int | None = None
    for position, result_id in enumerate(top_k_ids, start=1):
        if result_id == expected_id:
            rank = position
            break
    return RetrievalGrade(
        query=query,
        expected_id=expected_id,
        rank=rank,
        hit=rank is not None,
        top_k_ids=top_k_ids,
    )


def _content_tokens(text: str) -> set[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return {token for token in tokens if token not in _STOPWORDS}


def grade_answer_overlap(generated_answer: str, expected_answer: str) -> AnswerOverlapGrade:
    """Token-overlap ratio between a generated answer and the golden answer.

    ``overlap_ratio`` is ``|matched content tokens| / |expected content tokens|``
    — i.e. what fraction of the golden answer's key vocabulary shows up
    somewhere in the generated answer. 1.0 means every content word in the
    expected answer appears in the generated one; 0.0 means none do. An empty
    expected answer trivially scores 1.0 (nothing to miss).
    """
    expected_tokens = _content_tokens(expected_answer)
    generated_tokens = _content_tokens(generated_answer)
    if not expected_tokens:
        return AnswerOverlapGrade(overlap_ratio=1.0, matched_tokens=[], expected_tokens=[])
    matched = expected_tokens & generated_tokens
    return AnswerOverlapGrade(
        overlap_ratio=len(matched) / len(expected_tokens),
        matched_tokens=sorted(matched),
        expected_tokens=sorted(expected_tokens),
    )
