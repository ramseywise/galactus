from __future__ import annotations

from core.pipelines.corpus.index import search

TOP_N = 2


def test_search_returns_descaling_article_for_descale_query(indexed_db: str) -> None:
    results = search(indexed_db, "descale", k=5)

    assert len(results) > 0
    top_ids = [result.id for result in results[:TOP_N]]
    assert "descaling" in top_ids


def test_search_orders_results_best_match_first(indexed_db: str) -> None:
    results = search(indexed_db, "warranty descale limescale", k=5)

    assert len(results) > 1
    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)


def test_search_respects_k_limit(indexed_db: str) -> None:
    results = search(indexed_db, "machine", k=1)

    assert len(results) <= 1


def test_search_returns_empty_list_for_nonsense_query(indexed_db: str) -> None:
    results = search(indexed_db, "zzzqqqxxx_no_such_term_exists", k=5)

    assert results == []


def test_search_does_not_crash_on_empty_query(indexed_db: str) -> None:
    results = search(indexed_db, "", k=5)

    assert isinstance(results, list)


def test_search_water_filter_query_finds_water_filter_article(indexed_db: str) -> None:
    results = search(indexed_db, "water filter cartridge replace", k=5)

    assert len(results) > 0
    top_ids = [result.id for result in results[:TOP_N]]
    assert "water_filter" in top_ids
