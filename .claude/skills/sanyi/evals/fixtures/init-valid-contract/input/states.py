"""State schemas — should be Jianyi with entropy budget."""

from typing import TypedDict


class AgentState(TypedDict):
    user_id: str
    session_id: str
    messages: list[dict]
    context: str
    intent: str
    confidence: float
    tool_calls: list[dict]
    response: str
