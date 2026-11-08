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


# -- Neo4j: skip countably, provide a store ------------------------------------------------

NEO4J_SKIP_REASON = "neo4j: NEO4J_URI not set"
"""Neo4j tests skip with this exact reason; the summary hook below counts on it, because the
`neo4j` marker would have to be registered in the root `pyproject.toml`."""

TEST_BUILD_PREFIX = "kgtest-"


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    skipped = terminalreporter.stats.get("skipped", [])
    n = sum(1 for rep in skipped if NEO4J_SKIP_REASON in str(rep.longrepr))
    if n:
        terminalreporter.write_line(f"{n} neo4j tests skipped ({NEO4J_SKIP_REASON})")


@pytest.fixture
def neo4j_store():
    """A live `Neo4jStore`, cleaned of test builds (prefix `kgtest-`) before and after.

    Refuses to run against a database holding any other build: default reads see every
    promoted build, so foreign data would change what the tests observe.
    """
    import os

    uri = os.environ.get("NEO4J_URI")
    if not uri:
        pytest.skip(NEO4J_SKIP_REASON)
    from kg.store.neo4j import Neo4jStore

    store = Neo4jStore(uri)

    def wipe() -> list[str]:
        with store._session() as s:
            ids = [r["id"] for r in s.run("MATCH (b:Build) RETURN b.build_id AS id")]
        mine = [i for i in ids if i.startswith(TEST_BUILD_PREFIX)]
        for i in mine:
            store.delete_build(i)
        return [i for i in ids if not i.startswith(TEST_BUILD_PREFIX)]

    foreign = wipe()
    if foreign:
        store.close()
        pytest.fail(f"NEO4J_URI database holds non-test builds {foreign}; use an empty database")
    yield store
    wipe()
    store.close()
