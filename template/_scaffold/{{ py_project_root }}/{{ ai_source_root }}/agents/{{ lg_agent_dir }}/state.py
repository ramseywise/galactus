from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from .schema import Source


def _last(_current: object, update: object) -> object:
    """Reducer: last write wins (default TypedDict behavior made explicit)."""
    return update


class State(TypedDict):
    # Only `message` is present at graph entry (`_graph.invoke({"message": ...})`);
    # everything else is NotRequired because each node fills in its own slice as
    # the graph progresses (guardrail -> retrieve -> generate) rather than the
    # caller pre-populating the full state up front.
    message: str
    blocked: NotRequired[Annotated[bool, _last]]
    block_reason: NotRequired[Annotated[str, _last]]
    sources: NotRequired[Annotated[list[Source], _last]]
    context_snippets: NotRequired[Annotated[list[str], _last]]
    answer: NotRequired[Annotated[str, _last]]
    # Set by the verification loop on retry — nodes may surface this to the LLM
    # as additional context so subsequent attempts can improve on the prior response.
    verification_feedback: NotRequired[Annotated[str, _last]]
