"""Retrieval node — also guard layer 2, the indirect-injection seam.

Retrieved documents are untrusted input that never passed through
`guardrail_node`: a poisoned corpus entry is not a user turn, so `check_input`
never sees it. `filter_content` runs here, at the point where retrieved text
first becomes prompt material, rather than in `generate_node` — filtering at
the source means any future consumer of `context_snippets` inherits it.

Snippets are filtered, not dropped: one injection line does not make the rest
of a document useless, and silently dropping passages looks like a retrieval
bug (see guardrails/README.md).
"""

from __future__ import annotations

from core.pipelines.corpus.index import search
from guardrails.guards import filter_content
from observability.spans import retrieve_span

from ..schema import Source
from ..settings import settings
from ..state import State


def retrieve_node(state: State) -> dict:
    with retrieve_span(
        query=state["message"],
        backend="duckdb-bm25",
        top_k=settings.retrieval_top_k,
    ):
        results = search(settings.vectordb_path, state["message"], k=settings.retrieval_top_k)
    sources = [Source(id=r.id, title=r.title, score=r.score) for r in results]
    # Guard layer 2 -- filter the title too, not just the body: a title is
    # concatenated into the same prompt string and is just as injectable.
    context_snippets = [
        filter_content(f"# {r.title}\n{r.text}", source="retrieval").text for r in results
    ]
    return {"sources": sources, "context_snippets": context_snippets}
