from __future__ import annotations

import atexit
from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from .settings import settings


@lru_cache(maxsize=1)
def get_checkpointer() -> BaseCheckpointSaver:
    """InMemorySaver for local dev — data is lost on restart.

    Set LG_CHECKPOINTER=postgres + POSTGRES_DSN for production persistence — see
    .agents/skills/langgraph-persistence/SKILL.md for the tradeoffs. Keep the swap
    confined to this one factory function so nothing downstream needs to change.

    Cached (@lru_cache) since PostgresSaver's connection pool is meant to live for
    the process lifetime, not be recreated per call — same singleton shape as
    get_vector_index()/get_embeddings() elsewhere in this template.

    The from_conn_string() context manager is entered once and kept alive for the
    process lifetime (the pool must outlive this call). An atexit handler calls
    __exit__ on graceful shutdown so the connection pool drains cleanly. SIGKILL
    and hard crashes bypass atexit — those are the honestly-unfixable cases.
    PostgresSaver's async methods run the underlying sync psycopg calls via a
    thread-pool executor (not native async) — fine at this starter's scale; swap to
    AsyncPostgresSaver if checkpoint I/O becomes a throughput bottleneck.
    """
    if settings.lg_checkpointer == "memory":
        return InMemorySaver()
    if settings.lg_checkpointer == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver

        _cm = PostgresSaver.from_conn_string(settings.postgres_dsn)
        checkpointer = _cm.__enter__()
        atexit.register(_cm.__exit__, None, None, None)
        checkpointer.setup()
        return checkpointer
    raise NotImplementedError(
        f"Checkpointer '{settings.lg_checkpointer}' is not wired up yet — "
        "see .agents/skills/langgraph-persistence/SKILL.md and extend this factory."
    )
