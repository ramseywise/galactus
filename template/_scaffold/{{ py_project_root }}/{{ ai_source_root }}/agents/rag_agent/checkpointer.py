from __future__ import annotations

import atexit
from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from agents.rag_agent.settings import settings


@lru_cache(maxsize=1)
def get_checkpointer() -> BaseCheckpointSaver:
    """InMemorySaver for local dev — see the LangGraph chat agent's checkpointer.py for the
    full rationale (identical pattern here: set RAG_CHECKPOINTER=postgres +
    POSTGRES_DSN for production, cached via @lru_cache since the connection pool
    is meant to live for the process lifetime).

    The from_conn_string() context manager is entered once and kept alive for the
    process lifetime. An atexit handler calls __exit__ on graceful shutdown so the
    connection pool drains cleanly. SIGKILL and hard crashes bypass atexit — those
    are the honestly-unfixable cases.
    """
    if settings.rag_checkpointer == "memory":
        return InMemorySaver()
    if settings.rag_checkpointer == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver

        _cm = PostgresSaver.from_conn_string(settings.postgres_dsn)
        checkpointer = _cm.__enter__()
        atexit.register(_cm.__exit__, None, None, None)
        checkpointer.setup()
        return checkpointer
    raise NotImplementedError(
        f"Checkpointer '{settings.rag_checkpointer}' is not wired up yet — "
        "see .agents/skills/langgraph-persistence/SKILL.md and extend this factory."
    )
