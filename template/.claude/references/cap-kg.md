# cap-kg — Templates for knowledge-graph-builder subagent

## File: {OUTPUT_DIR}/kg_client.py

```python
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

from {AGENT_NAME}.graph_schema import safe_identifier

logger = logging.getLogger(__name__)

_BACKEND_ENV = "KG_BACKEND"  # "neo4j" (default) or "neptune"


# ---------------------------------------------------------------------------
# KGClient
# ---------------------------------------------------------------------------


class KGClient:
    """Knowledge graph client backed by Neo4j or AWS Neptune.

    Backend is selected via KG_BACKEND env var (default: neo4j).

    Neo4j config (env vars):
        NEO4J_URI       — bolt://localhost:7687
        NEO4J_USER      — neo4j
        NEO4J_PASSWORD  —

    Neptune config:
        NEPTUNE_ENDPOINT — wss://your-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com:8182/gremlin
        AWS_REGION       — eu-west-1
    """

    def __init__(self) -> None:
        self._backend = os.environ.get(_BACKEND_ENV, "neo4j").lower()
        self._driver: Any = None
        self._connect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        if self._backend == "neo4j":
            self._connect_neo4j()
        elif self._backend == "neptune":
            self._connect_neptune()
        else:
            raise ValueError(f"Unknown KG backend: {self._backend!r}")

    def _connect_neo4j(self) -> None:
        try:
            from neo4j import GraphDatabase  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("neo4j is required. Run: pip install neo4j") from exc

        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Connected to Neo4j at %s", uri)

    def _connect_neptune(self) -> None:
        """Neptune via boto3 (HTTP REST endpoint) — stub for Gremlin or SPARQL."""
        import boto3  # noqa: PLC0415

        region = os.environ.get("AWS_REGION", "eu-west-1")
        self._driver = boto3.client("neptunedata", region_name=region)
        logger.info("Connected to Neptune (%s)", region)

    def close(self) -> None:
        if self._driver and self._backend == "neo4j":
            self._driver.close()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dicts.

        Note: Neptune does not support Cypher natively. For Neptune, pass openCypher
        or use .query_neptune() with SPARQL.
        """
        params = params or {}

        if self._backend == "neo4j":
            return self._neo4j_query(cypher, params)
        elif self._backend == "neptune":
            return self._neptune_query(cypher, params)
        else:
            raise ValueError(f"Unsupported backend: {self._backend!r}")

    def _neo4j_query(self, cypher: str, params: dict) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def _neptune_query(self, cypher: str, params: dict) -> list[dict]:
        """Neptune openCypher query via REST."""
        try:
            response = self._driver.execute_open_cypher_query(
                openCypherQuery=cypher,
                parameters=str(params),
            )
            return response.get("results", [])
        except Exception as exc:  # noqa: BLE001
            logger.error("Neptune query failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def find_related(
        self,
        entity: str,
        depth: int = 2,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Find entities related to the given entity name up to `depth` hops.

        Returns a list of dicts with keys: id, type, name, relation, weight.
        """
        # depth is a path-length literal and cannot be parameterized; limit can
        # be, but both are coerced to int so a caller-supplied string can never
        # reach the query text.
        depth = int(depth)
        if not 1 <= depth <= 5:
            raise ValueError(f"depth must be between 1 and 5, got {depth}")

        cypher = (
            f"MATCH path = (start {{name: $entity}})-[r*1..{depth}]-(related) "
            f"RETURN related.id AS id, labels(related)[0] AS type, "
            f"related.name AS name, type(r[-1]) AS relation, "
            f"COALESCE(r[-1].weight, 1.0) AS weight "
            f"LIMIT $limit"
        )
        try:
            return self.query(cypher, {"entity": entity, "limit": int(limit)})
        except Exception as exc:  # noqa: BLE001
            logger.error("find_related failed for %r: %s", entity, exc)
            return []

    def upsert_entity(self, entity: dict[str, Any]) -> None:
        """Create or update an entity node.

        entity must have keys: id, type, and optionally properties dict.
        """
        entity_id = entity["id"]
        entity_type = safe_identifier(entity.get("type", "Entity"), "entity type")
        properties = entity.get("properties", {})
        embedding = entity.get("embedding")

        props = {**properties, "id": entity_id}
        if embedding is not None:
            props["embedding"] = list(embedding) if hasattr(embedding, "tolist") else embedding

        # Property names are caller-supplied dict keys and land in query text —
        # validate each one, not just the label.
        set_clause = ", ".join(
            f"n.{safe_identifier(k, 'property name')} = ${k}" for k in props
        )
        cypher = (
            f"MERGE (n:{entity_type} {{id: $id}}) "
            f"SET {set_clause}"
        )
        try:
            self.query(cypher, props)
        except Exception as exc:  # noqa: BLE001
            logger.error("upsert_entity failed for id=%r: %s", entity_id, exc)
```

## File: {OUTPUT_DIR}/graph_schema.py

```python
from __future__ import annotations

import re
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

# Cypher cannot parameterize labels, relationship types, or property names —
# they are query structure, not values, so $params is unavailable for them.
# Anything caller-supplied that reaches those positions must therefore be
# validated against an allowlist pattern instead.
#
# Lives here rather than in kg_client so both this module and the client can
# use it without the schema layer importing from the client layer.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def safe_identifier(value: str, kind: str) -> str:
    """Return `value` if it is a bare Cypher identifier, else raise.

    Rejects the backtick-and-comment escapes that turn an interpolated label
    or property name into arbitrary query text.
    """
    if not isinstance(value, str) or not _IDENTIFIER_RE.match(value):
        raise ValueError(
            f"Unsafe {kind}: {value!r}. Must match [A-Za-z_][A-Za-z0-9_]* — "
            "labels, relationship types and property names are interpolated "
            "into Cypher and cannot be parameterized."
        )
    return value


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """A node in the knowledge graph."""

    id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None

    def to_kg_dict(self) -> dict[str, Any]:
        """Serialise for KGClient.upsert_entity()."""
        return {
            "id": self.id,
            "type": self.type,
            "properties": self.properties,
            "embedding": self.embedding,
        }


class Relation(BaseModel):
    """A directed edge between two entities."""

    source_id: str
    target_id: str
    type: str
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_cypher_merge(self) -> tuple[str, dict[str, Any]]:
        """Return a (cypher, params) tuple for creating this relation."""
        cypher = (
            "MATCH (a {id: $source_id}), (b {id: $target_id}) "
            f"MERGE (a)-[r:{safe_identifier(self.type, 'relation type')}]->(b) "
            "SET r.weight = $weight"
        )
        params = {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "weight": self.weight,
        }
        return cypher, params


# ---------------------------------------------------------------------------
# Graph context → RAG passage conversion
# ---------------------------------------------------------------------------


def graph_to_passages(entities: list[Entity]) -> list[dict[str, Any]]:
    """Convert a list of graph entities to RAG passage format.

    This bridges the KG retrieval path into the CRAG/RAG pipeline,
    so graph context can be processed identically to KB passages.

    Returns:
        List of dicts compatible with PassageItem.from_bedrock():
            {"content": {"text": ...}, "location": {"webLocation": {"url": ...}}, "score": ...}
    """
    passages: list[dict[str, Any]] = []

    for entity in entities:
        # Build a human-readable text representation of the entity
        prop_lines = "\n".join(
            f"  {k}: {v}"
            for k, v in entity.properties.items()
            if not k.startswith("_") and v is not None
        )
        text = f"[{entity.type}] {entity.id}\n{prop_lines}".strip()

        # Use entity ID as a pseudo-URL so grounding checks can track provenance
        url = f"kg://{entity.type.lower()}/{entity.id}"

        # Compute score from embedding norm as a rough confidence proxy
        score = 0.75  # default
        if entity.embedding:
            arr = np.array(entity.embedding)
            norm = float(np.linalg.norm(arr))
            score = min(1.0, norm / 10.0) if norm > 0 else 0.5

        passages.append(
            {
                "content": {"text": text},
                "location": {"webLocation": {"url": url}},
                "score": score,
                "metadata": {"entity_type": entity.type, "entity_id": entity.id},
            }
        )

    return passages
```
