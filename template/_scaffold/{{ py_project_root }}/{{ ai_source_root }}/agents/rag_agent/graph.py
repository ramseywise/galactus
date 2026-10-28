from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.rag_agent.checkpointer import get_checkpointer
from agents.rag_agent.nodes.generate import generate_node
from agents.rag_agent.nodes.retrieve import retrieve_node
from agents.rag_agent.state import State


def build_graph():
    builder = (
        StateGraph(State)
        .add_node("retrieve", retrieve_node)
        .add_node("generate", generate_node)
        .add_edge(START, "retrieve")
        .add_edge("retrieve", "generate")
        .add_edge("generate", END)
    )
    return builder.compile(checkpointer=get_checkpointer())
