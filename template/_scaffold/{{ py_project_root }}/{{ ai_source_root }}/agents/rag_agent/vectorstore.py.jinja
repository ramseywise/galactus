"""Vector store backends for rag_agent, behind one factory (:func:`get_vector_index`).

Three backends, all returning the same ``(id, title, text, score)`` tuple shape
from ``similarity_search`` so callers (``nodes/retrieve.py``,
``evals/pipelines/run.py``) never import a specific backend directly — swapping
backends is a copier answer (``vector_backend``), not a code change. Adapted from
playground's ``rag/datastore/`` (memory/duckdb/opensearch behind one factory),
simplified to this template's plain-tuple interface instead of a full
``Retriever`` protocol + ``Chunk``/``ChunkMetadata`` schema.

- ``duckdb`` (default): single-file, durable, no external service — brute-force
  scan + sort, no ANN index. Fine at this starter's corpus sizes; swap backends
  before this matters at scale.
- ``memory``: in-process dict, zero setup. Optional JSON snapshot
  (``rag_vectordb_path``, reinterpreted as a ``.json`` path for this backend) for
  persistence across restarts — good for local dev/CI, lost if you don't snapshot.
- ``opensearch``: external cluster, ``knn_vector`` (Lucene HNSW), inner product on
  normalized embeddings (same scoring convention as the other two backends, so
  relevance scores are comparable across backends). Requires the optional
  ``opensearch-py`` dependency and a reachable cluster — not installed/needed
  unless ``vector_backend=opensearch``.
- ``postgres``: any managed Postgres with the ``pgvector`` extension (Supabase's
  Postgres supports this natively — ``CREATE EXTENSION vector`` once). Same
  inner-product scoring convention as ``opensearch``. Requires the optional
  ``psycopg``/``pgvector`` dependencies and a reachable database — not installed/
  needed unless ``vector_backend=postgres``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb

from agents.rag_agent.embeddings import get_embeddings
from agents.rag_agent.settings import settings


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class DuckDBVectorIndex:
    def __init__(self, database_path: str) -> None:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._embeddings = get_embeddings()
        self._con = duckdb.connect(str(path))
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id VARCHAR PRIMARY KEY,
                text VARCHAR,
                title VARCHAR,
                embedding FLOAT[]
            )
            """
        )

    def doc_count(self) -> int:
        row = self._con.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()
        return int(row[0]) if row else 0

    def upsert(self, records: list[tuple[str, str, str]]) -> None:
        """Each record is (id, title, text). Embeds and stores in one batch."""
        if not records:
            return
        vectors = self._embeddings.embed_documents([text for _, _, text in records])
        for (rid, title, text), vec in zip(records, vectors, strict=True):
            self._con.execute(
                "INSERT OR REPLACE INTO rag_chunks (id, text, title, embedding) "
                "VALUES (?, ?, ?, ?)",
                [rid, text, title, vec],
            )

    def similarity_search(self, query: str, k: int = 5) -> list[tuple[str, str, str, float]]:
        """Returns (id, title, text, score) tuples, best match first."""
        query_vec = self._embeddings.embed_query(query)
        rows = self._con.execute("SELECT id, title, text, embedding FROM rag_chunks").fetchall()
        if not rows:
            return []
        scored = [
            (rid, title, text, _dot(query_vec, list(emb) if emb is not None else []))
            for rid, title, text, emb in rows
        ]
        scored.sort(key=lambda r: r[3], reverse=True)
        return [(rid, title, text, score) for rid, title, text, score in scored[:k]]


class MemoryVectorIndex:
    """In-process dict — zero setup, nothing to run. Optional JSON snapshot for
    persistence across restarts (``snapshot_path``); without one, the index is
    lost when the process exits, same as any other in-memory structure."""

    def __init__(self, snapshot_path: str | None = None) -> None:
        self._embeddings = get_embeddings()
        # id -> (title, text, embedding)
        self._records: dict[str, tuple[str, str, list[float]]] = {}
        self._snapshot_path = Path(snapshot_path) if snapshot_path else None
        if self._snapshot_path and self._snapshot_path.exists():
            self._load_snapshot()

    def _load_snapshot(self) -> None:
        assert self._snapshot_path is not None
        data = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
        for row in data:
            self._records[row["id"]] = (row["title"], row["text"], row["embedding"])

    def _save_snapshot(self) -> None:
        if not self._snapshot_path:
            return
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {"id": rid, "title": title, "text": text, "embedding": emb}
            for rid, (title, text, emb) in self._records.items()
        ]
        self._snapshot_path.write_text(json.dumps(data), encoding="utf-8")

    def doc_count(self) -> int:
        return len(self._records)

    def upsert(self, records: list[tuple[str, str, str]]) -> None:
        """Each record is (id, title, text). Embeds and stores in one batch."""
        if not records:
            return
        vectors = self._embeddings.embed_documents([text for _, _, text in records])
        for (rid, title, text), vec in zip(records, vectors, strict=True):
            self._records[rid] = (title, text, vec)
        self._save_snapshot()

    def similarity_search(self, query: str, k: int = 5) -> list[tuple[str, str, str, float]]:
        """Returns (id, title, text, score) tuples, best match first."""
        if not self._records:
            return []
        query_vec = self._embeddings.embed_query(query)
        scored = [
            (rid, title, text, _dot(query_vec, emb))
            for rid, (title, text, emb) in self._records.items()
        ]
        scored.sort(key=lambda r: r[3], reverse=True)
        return scored[:k]


class OpenSearchVectorIndex:
    """External OpenSearch cluster — ``knn_vector`` (Lucene HNSW), inner product
    on normalized embeddings. Requires the optional ``opensearch-py`` dependency
    (lazy-imported here, so it's only required when this backend is actually
    used) and a reachable cluster — this class never gets instantiated unless
    ``vector_backend=opensearch``."""

    def __init__(
        self,
        hosts: str,
        index_name: str,
        user: str = "",
        password: str = "",
        use_ssl: bool = False,
        verify_certs: bool = True,
    ) -> None:
        from opensearchpy import OpenSearch

        parsed_hosts: list[dict[str, Any]] = []
        for part in hosts.split(","):
            host_port = part.strip()
            if not host_port:
                continue
            host, _, port = host_port.partition(":")
            parsed_hosts.append({"host": host, "port": int(port) if port else 9200})
        if not parsed_hosts:
            parsed_hosts = [{"host": "127.0.0.1", "port": 9200}]

        self._client = OpenSearch(
            hosts=parsed_hosts,
            http_auth=(user, password) if user and password else None,
            use_ssl=use_ssl,
            verify_certs=verify_certs,
            ssl_show_warn=False,
        )
        self._index = index_name
        self._embeddings = get_embeddings()
        self._dim: int | None = None

    def _ensure_index(self, embedding_dim: int) -> None:
        if self._dim == embedding_dim and self._client.indices.exists(index=self._index):
            return
        if not self._client.indices.exists(index=self._index):
            self._client.indices.create(
                index=self._index,
                body={
                    "settings": {"index": {"knn": True}},
                    "mappings": {
                        "properties": {
                            "title": {"type": "keyword"},
                            "text": {"type": "text"},
                            "embedding": {
                                "type": "knn_vector",
                                "dimension": embedding_dim,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "innerproduct",
                                    "engine": "lucene",
                                    "parameters": {"m": 16, "ef_construction": 100},
                                },
                            },
                        }
                    },
                },
            )
        self._dim = embedding_dim

    def doc_count(self) -> int:
        try:
            return int(self._client.count(index=self._index).get("count", 0))
        except Exception:
            return 0

    def upsert(self, records: list[tuple[str, str, str]]) -> None:
        """Each record is (id, title, text). Embeds and bulk-indexes."""
        if not records:
            return
        from opensearchpy.helpers import bulk

        vectors = self._embeddings.embed_documents([text for _, _, text in records])
        self._ensure_index(len(vectors[0]))
        actions = [
            {
                "_op_type": "index",
                "_index": self._index,
                "_id": rid,
                "_source": {"title": title, "text": text, "embedding": vec},
            }
            for (rid, title, text), vec in zip(records, vectors, strict=True)
        ]
        bulk(self._client, actions, refresh="wait_for")

    def similarity_search(self, query: str, k: int = 5) -> list[tuple[str, str, str, float]]:
        """Returns (id, title, text, score) tuples, best match first."""
        if self.doc_count() == 0:
            return []
        query_vec = self._embeddings.embed_query(query)
        res = self._client.search(
            index=self._index,
            body={"size": k, "query": {"knn": {"embedding": {"vector": query_vec, "k": k}}}},
        )
        return [
            (
                str(hit["_id"]),
                str(hit["_source"].get("title", "")),
                str(hit["_source"].get("text", "")),
                float(hit.get("_score", 0.0)),
            )
            for hit in res.get("hits", {}).get("hits", [])
        ]


class PostgresVectorIndex:
    """Postgres + ``pgvector`` — durable, works with any managed Postgres
    (Supabase's Postgres supports pgvector natively; enable it once with
    ``CREATE EXTENSION vector``). The table is created lazily on first
    ``upsert()`` once the embedding dimension is known (pgvector's ``vector(N)``
    column type needs a fixed dimension at creation time) — same lazy-schema
    approach as :class:`OpenSearchVectorIndex`'s ``_ensure_index``. Scores use
    negative inner product (pgvector's ``<#>`` operator) on normalized
    embeddings, matching the other backends' dot-product convention so
    relevance scores are comparable across backends. Table/column names are
    passed through ``psycopg.sql.Identifier`` rather than f-string-interpolated,
    even though ``table`` only ever comes from trusted settings, not
    request-time input — cheap to do correctly.
    """

    def __init__(self, dsn: str, table: str) -> None:
        import psycopg
        from pgvector.psycopg import register_vector

        self._table = table
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)
        self._embeddings = get_embeddings()
        self._dim: int | None = None

    def _ensure_table(self, embedding_dim: int) -> None:
        if self._dim == embedding_dim:
            return
        from psycopg import sql

        self._conn.execute(
            sql.SQL(
                "CREATE TABLE IF NOT EXISTS {table} ("
                "id TEXT PRIMARY KEY, title TEXT, text TEXT, embedding VECTOR({dim}))"
            ).format(table=sql.Identifier(self._table), dim=sql.Literal(embedding_dim))
        )
        self._dim = embedding_dim

    def doc_count(self) -> int:
        from psycopg import sql

        try:
            row = self._conn.execute(
                sql.SQL("SELECT COUNT(*) FROM {table}").format(table=sql.Identifier(self._table))
            ).fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def upsert(self, records: list[tuple[str, str, str]]) -> None:
        """Each record is (id, title, text). Embeds and upserts in one batch."""
        if not records:
            return
        from psycopg import sql

        vectors = self._embeddings.embed_documents([text for _, _, text in records])
        self._ensure_table(len(vectors[0]))
        query = sql.SQL(
            "INSERT INTO {table} (id, title, text, embedding) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET "
            "title = EXCLUDED.title, text = EXCLUDED.text, embedding = EXCLUDED.embedding"
        ).format(table=sql.Identifier(self._table))
        with self._conn.cursor() as cur:
            cur.executemany(
                query,
                [
                    (rid, title, text, vec)
                    for (rid, title, text), vec in zip(records, vectors, strict=True)
                ],
            )

    def similarity_search(self, query: str, k: int = 5) -> list[tuple[str, str, str, float]]:
        """Returns (id, title, text, score) tuples, best match first."""
        if self.doc_count() == 0:
            return []
        from psycopg import sql

        query_vec = self._embeddings.embed_query(query)
        rows = self._conn.execute(
            sql.SQL(
                "SELECT id, title, text, -(embedding <#> %s) AS score FROM {table} "
                "ORDER BY embedding <#> %s LIMIT %s"
            ).format(table=sql.Identifier(self._table)),
            (query_vec, query_vec, k),
        ).fetchall()
        return [(str(rid), str(title), str(text), float(score)) for rid, title, text, score in rows]


VectorIndex = DuckDBVectorIndex | MemoryVectorIndex | OpenSearchVectorIndex | PostgresVectorIndex


@lru_cache(maxsize=1)
def get_vector_index() -> VectorIndex:
    """Process-wide singleton, backend chosen by ``settings.vector_backend`` —
    application code (nodes/retrieve.py, evals/pipelines/run.py) calls this and
    never imports a specific backend class directly."""
    backend = settings.vector_backend
    if backend == "memory":
        return MemoryVectorIndex(settings.rag_vectordb_path)
    if backend == "opensearch":
        return OpenSearchVectorIndex(
            hosts=settings.opensearch_hosts,
            index_name=settings.opensearch_index,
            user=settings.opensearch_user,
            password=settings.opensearch_password,
            use_ssl=settings.opensearch_use_ssl,
            verify_certs=settings.opensearch_verify_certs,
        )
    if backend == "postgres":
        return PostgresVectorIndex(dsn=settings.postgres_dsn, table=settings.postgres_table)
    return DuckDBVectorIndex(settings.rag_vectordb_path)
