"""Shared fixtures for the knowledge-graph run.

Every `KG_*` and provider variable is cleared for each test so a developer's `.env` or
shell never changes what the suite sees; a test that wants a value sets it explicitly.
"""

from __future__ import annotations

import pytest

KG_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "NEO4J_URI",
    "KG_CORPUS_ROOT",
    "LIBRARIAN_ROOT",
    "KG_PROPOSER_MODEL",
    "KG_JUDGE_MODEL",
    "KG_BUILD_CEILING_USD",
    "KG_BAND_CEILING_USD",
    "KG_BAND_RATE_HALT",
    "KG_MAX_HOPS",
    "KG_DB_PATH",
    "KG_LIVE",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in KG_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch
