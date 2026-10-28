"""Pure aggregate metrics over per-query retrieval ranks.

A "rank" is the 1-indexed position of the expected/relevant document within the
top-k results returned for a query, or ``None`` if it did not appear at all.
"""

from __future__ import annotations


def hit_rate(ranks: list[int | None]) -> float:
    """Fraction of queries where the expected result appeared anywhere in top-k.

    >>> hit_rate([1, None, 3])
    0.6666666666666666
    >>> hit_rate([None, None])
    0.0
    >>> hit_rate([])
    0.0
    """
    if not ranks:
        return 0.0
    hits = sum(1 for rank in ranks if rank is not None)
    return hits / len(ranks)


def mean_reciprocal_rank(ranks: list[int | None]) -> float:
    """Mean of ``1/rank`` for hits (0 for misses), averaged over all queries.

    Ranks are 1-indexed: a hit at rank 1 contributes 1.0, a hit at rank 2
    contributes 0.5, a miss (``None``) contributes 0.0.

    >>> mean_reciprocal_rank([1, 2, None])
    0.5
    >>> mean_reciprocal_rank([None, None])
    0.0
    >>> mean_reciprocal_rank([])
    0.0
    """
    if not ranks:
        return 0.0
    reciprocal_ranks = [1.0 / rank if rank is not None else 0.0 for rank in ranks]
    return sum(reciprocal_ranks) / len(ranks)
