"""Settings load with nothing set; every external dependency refuses by name."""

from __future__ import annotations

from pathlib import Path

import pytest
from kg_fakes import ScriptedProposer, ScriptedSeat

from kg.config import ConfigError, Settings


def test_load_succeeds_with_no_env(clean_env: pytest.MonkeyPatch) -> None:
    s = Settings.load(use_dotenv=False)
    assert s.anthropic_api_key is None
    assert s.openrouter_api_key is None
    assert s.neo4j_uri is None
    assert s.proposer_model == "claude-haiku-5-5"
    assert s.judge_model == "claude-sonnet-5-5"
    assert s.build_ceiling_usd == 10.0
    assert s.band_ceiling_usd == 30.0
    assert s.band_rate_halt == 0.40
    assert s.max_hops == 2
    assert s.db_path is None
    assert s.corpus_root == Path("~/workspace/librarian/data/wiki").expanduser()
    assert s.librarian_root == Path("~/workspace/librarian").expanduser()


@pytest.mark.parametrize(
    ("method", "variable"),
    [
        ("require_anthropic_key", "ANTHROPIC_API_KEY"),
        ("require_openrouter_key", "OPENROUTER_API_KEY"),
        ("require_neo4j_uri", "NEO4J_URI"),
    ],
)
def test_each_gate_names_its_variable(
    clean_env: pytest.MonkeyPatch, method: str, variable: str
) -> None:
    s = Settings.load(use_dotenv=False)
    with pytest.raises(ConfigError, match=variable):
        getattr(s, method)()


def test_gates_return_values_when_set(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-a")
    clean_env.setenv("OPENROUTER_API_KEY", "sk-o")
    clean_env.setenv("NEO4J_URI", "bolt://localhost:7687")
    s = Settings.load(use_dotenv=False)
    assert s.require_anthropic_key() == "sk-a"
    assert s.require_openrouter_key() == "sk-o"
    assert s.require_neo4j_uri() == "bolt://localhost:7687"


def test_missing_paths_refuse_by_name(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clean_env.setenv("KG_CORPUS_ROOT", str(tmp_path / "nope"))
    clean_env.setenv("LIBRARIAN_ROOT", str(tmp_path / "also-nope"))
    s = Settings.load(use_dotenv=False)
    with pytest.raises(ConfigError, match="KG_CORPUS_ROOT"):
        s.require_corpus_root()
    with pytest.raises(ConfigError, match="LIBRARIAN_ROOT"):
        s.require_librarian_root()


def test_existing_paths_pass(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clean_env.setenv("KG_CORPUS_ROOT", str(tmp_path))
    clean_env.setenv("LIBRARIAN_ROOT", str(tmp_path))
    s = Settings.load(use_dotenv=False)
    assert s.require_corpus_root() == tmp_path
    assert s.require_librarian_root() == tmp_path


@pytest.mark.parametrize(
    ("name", "value", "match"),
    [
        ("KG_MAX_HOPS", "3", "KG_MAX_HOPS"),
        ("KG_MAX_HOPS", "0", "KG_MAX_HOPS"),
        ("KG_MAX_HOPS", "two", "integer"),
        ("KG_BAND_RATE_HALT", "1.5", "KG_BAND_RATE_HALT"),
        ("KG_BUILD_CEILING_USD", "-1", "must be > 0"),
        ("KG_BUILD_CEILING_USD", "50", "exceeds"),
        ("KG_BAND_CEILING_USD", "lots", "number"),
    ],
)
def test_bad_knobs_fail_at_load(
    clean_env: pytest.MonkeyPatch, name: str, value: str, match: str
) -> None:
    clean_env.setenv(name, value)
    with pytest.raises(ConfigError, match=match):
        Settings.load(use_dotenv=False)


def test_overrides_are_read(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clean_env.setenv("KG_PROPOSER_MODEL", "claude-haiku-x")
    clean_env.setenv("KG_JUDGE_MODEL", "claude-sonnet-x")
    clean_env.setenv("KG_MAX_HOPS", "1")
    clean_env.setenv("KG_DB_PATH", str(tmp_path / "kg.sqlite"))
    s = Settings.load(use_dotenv=False)
    assert (s.proposer_model, s.judge_model, s.max_hops) == ("claude-haiku-x", "claude-sonnet-x", 1)
    assert s.db_path == tmp_path / "kg.sqlite"


def test_fake_stubs_import() -> None:
    assert ScriptedProposer() is not None
    assert ScriptedSeat() is not None
