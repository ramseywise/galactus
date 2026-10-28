from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from agents.rag_agent.schema import Source


def _last(_current: object, update: object) -> object:
    """Reducer: last write wins (default TypedDict behavior made explicit)."""
    return update


class State(TypedDict):
    # Only `message` is present at graph entry; everything else is filled in as
    # the graph progresses (retrieve -> generate).
    message: str
    sources: NotRequired[Annotated[list[Source], _last]]
    context_snippets: NotRequired[Annotated[list[str], _last]]
    confidence: NotRequired[Annotated[float, _last]]
    answer: NotRequired[Annotated[str, _last]]
