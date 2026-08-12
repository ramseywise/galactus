"""Shared fixtures: the shipped template and a draft that satisfies it."""

from __future__ import annotations

import pytest
from layout.contract import load_template
from models import LayoutTemplate

_SIXTY_FIVE_WORDS = " ".join(["alpha"] * 65)


@pytest.fixture
def template() -> LayoutTemplate:
    return load_template("two_column_brief")


@pytest.fixture
def clean_draft() -> dict[str, str]:
    """A draft that satisfies `two_column_brief` on every constraint.

    Asserted valid by `test_clean_draft_has_no_violations`, so any other test
    can treat a violation it sees as caused by its own mutation.
    """
    return {
        "headline": "Two Firms One Shared Supply Chain",
        "subheadline": (
            "How coordinated logistics cut delivery times across both networks in under a year"
        ),
        "column_left": _SIXTY_FIVE_WORDS,
        "column_right": _SIXTY_FIVE_WORDS,
        "pull_quote": "We stopped optimising separately and started optimising together.",
        "cta": "Book a partnership review this quarter",
        "hero_image": "{{hero_image}}",
        "sender_logo": "{{sender_logo}}",
        "accent_color": "accent",
    }
