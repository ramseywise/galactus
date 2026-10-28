from __future__ import annotations

from agents.rag_agent.confidence import ConfidenceSignal
from agents.rag_agent.schema import Source
from agents.rag_agent.settings import settings
from agents.rag_agent.state import State
from agents.rag_agent.vectorstore import get_vector_index


def retrieve_node(state: State) -> dict:
    results = get_vector_index().similarity_search(state["message"], k=settings.retrieval_top_k)
    sources = [Source(id=rid, title=title, score=score) for rid, title, _, score in results]
    context_snippets = [f"# {title}\n{text}" for _, title, text, _ in results]

    top_score = results[0][3] if results else None
    confidence = ConfidenceSignal(top_score=top_score).score(
        threshold=settings.confidence_threshold
    )

    return {"sources": sources, "context_snippets": context_snippets, "confidence": confidence}
