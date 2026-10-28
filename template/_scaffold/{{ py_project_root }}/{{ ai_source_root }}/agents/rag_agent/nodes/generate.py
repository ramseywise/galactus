from __future__ import annotations

from agents.rag_agent.model.gateway import generate
from agents.rag_agent.state import State

_SYSTEM_PROMPT = """You are a support assistant answering questions using ONLY the \
provided context articles. If the context doesn't contain the answer, say so plainly \
instead of guessing. Be concise.

Context:
{context}
"""


def generate_node(state: State) -> dict:
    context_snippets = state.get("context_snippets", [])
    context = "\n\n---\n\n".join(context_snippets) or "(no matching articles found)"
    answer = generate(
        system_prompt=_SYSTEM_PROMPT.format(context=context),
        user_message=state["message"],
    )
    return {"answer": answer}
