from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb

from core.pipelines.corpus.models import SearchResult

log = logging.getLogger(__name__)


def build_index(jsonl_path: Path, db_path: str) -> None:
    """Build a DuckDB full-text-search index from a preprocessed JSONL corpus.

    ``db_path`` may be a filesystem path or ``:memory:``.
    """
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
            "skipped %d malformed line(s) while building index from %s", skipped, jsonl_path
        )

    with duckdb.connect(db_path) as con:
        con.execute("INSTALL fts")
        con.execute("LOAD fts")
        con.execute("DROP TABLE IF EXISTS articles")
        con.execute(
            "CREATE TABLE articles (id VARCHAR, title VARCHAR, text VARCHAR, category VARCHAR)"
        )
        con.executemany(
            "INSERT INTO articles VALUES (?, ?, ?, ?)",
            [(row["id"], row["title"], row["text"], row["category"]) for row in rows],
        )
        con.execute("PRAGMA create_fts_index('articles', 'id', 'title', 'text', overwrite=1)")


def search(db_path: str, query: str, k: int = 5) -> list[SearchResult]:
    """BM25 search over the ``articles`` FTS index. Returns up to ``k`` results,
    best match first. Empty list if the index has no match for ``query``."""
    with duckdb.connect(db_path) as con:
        con.execute("INSTALL fts")
        con.execute("LOAD fts")
        rows = con.execute(
            """
            SELECT id, title, text, category, score
            FROM (
                SELECT id, title, text, category, fts_main_articles.match_bm25(id, ?) AS score
                FROM articles
            )
            WHERE score IS NOT NULL
            ORDER BY score DESC
            LIMIT ?
            """,
            [query, k],
        ).fetchall()
    return [
        SearchResult(id=row[0], title=row[1], text=row[2], category=row[3], score=row[4])
        for row in rows
    ]
