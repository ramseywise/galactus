"""Safety guards — candidate Buyi. NOTE: this module is NOT imported anywhere."""

import re


def mask_pii(text: str) -> str:
    """Mask PII before logging or external calls."""
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text)
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", text)
    return text


def check_escalation_needed(confidence: float, intent: str) -> bool:
    """Determine if human escalation is needed."""
    if confidence < 0.5:
        return True
    if intent in ("refund", "account_deletion", "legal"):
        return True
    return False
