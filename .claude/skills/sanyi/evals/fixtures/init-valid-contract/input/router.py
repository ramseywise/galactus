"""Main router — imports config and states but NOT guards."""

from config import MODEL_NAME, CONFIDENCE_THRESHOLD
from states import AgentState


def route_request(state: AgentState) -> str:
    """Route based on intent and confidence."""
    if state["confidence"] < CONFIDENCE_THRESHOLD:
        return "escalate"
    if state["intent"] in ("refund", "account_deletion"):
        return "escalate"
    return "respond"


def build_response(state: AgentState) -> str:
    """Build response using configured model."""
    # In production, this calls the LLM with MODEL_NAME
    return f"Using {MODEL_NAME} to respond to {state['intent']}"
