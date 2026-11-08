"""Environment-backed configuration for the knowledge-graph run.

`Settings.load()` succeeds with nothing set: the contract, census, gates, store and the
whole dry-run pipeline need no credential. Each external dependency has its own explicit
gate — `require_anthropic_key()`, `require_openrouter_key()`, `require_neo4j_uri()` — and
each names the missing variable, so an unavailable seat or store refuses by name rather
than degrading silently.

Paths (`KG_CORPUS_ROOT`, `LIBRARIAN_ROOT`) are resolved at load but their existence is
checked by `require_corpus_root()` / `require_librarian_root()`, not here: a test that
never touches the corpus must not fail because the Librarian checkout is absent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_CORPUS_ROOT = "~/workspace/librarian/data/wiki"
DEFAULT_LIBRARIAN_ROOT = "~/workspace/librarian"
DEFAULT_PROPOSER_MODEL = "claude-haiku-5-5"
DEFAULT_JUDGE_MODEL = "claude-sonnet-5-5"
DEFAULT_BUILD_CEILING_USD = 10.0
DEFAULT_BAND_CEILING_USD = 30.0
DEFAULT_BAND_RATE_HALT = 0.40
DEFAULT_MAX_HOPS = 2
HARD_MAX_HOPS = 2
"""Per-hop error compounds as p^n (research F6); `KG_MAX_HOPS` may lower the cap, not raise it."""


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings."""

    anthropic_api_key: str | None
    openrouter_api_key: str | None
    neo4j_uri: str | None
    corpus_root: Path
    librarian_root: Path
    proposer_model: str = DEFAULT_PROPOSER_MODEL
    judge_model: str = DEFAULT_JUDGE_MODEL
    build_ceiling_usd: float = DEFAULT_BUILD_CEILING_USD
    """Refusal before spend: one build's estimate above this is refused by name."""
    band_ceiling_usd: float = DEFAULT_BAND_CEILING_USD
    """Live spend cap across the whole BUILD band, both seats."""
    band_rate_halt: float = DEFAULT_BAND_RATE_HALT
    """Review-band share above which a build halts rather than queueing a wall of work."""
    max_hops: int = DEFAULT_MAX_HOPS
    db_path: Path | None = None
    """SQLite file for the graph store. None keeps it in memory — tests and dry runs only."""

    @classmethod
    def load(cls, *, use_dotenv: bool = True) -> Settings:
        """Read settings from the environment.

        Args:
            use_dotenv: If True, seed missing values from a `.env` file in the working
                directory or its parents. Existing environment variables always win.
        """
        if use_dotenv:
            load_dotenv(override=False)

        build_ceiling = _float_env("KG_BUILD_CEILING_USD", DEFAULT_BUILD_CEILING_USD)
        band_ceiling = _float_env("KG_BAND_CEILING_USD", DEFAULT_BAND_CEILING_USD)
        if build_ceiling <= 0 or band_ceiling <= 0:
            raise ConfigError("KG_BUILD_CEILING_USD and KG_BAND_CEILING_USD must be > 0")
        if build_ceiling > band_ceiling:
            raise ConfigError(
                f"KG_BUILD_CEILING_USD ({build_ceiling}) exceeds "
                f"KG_BAND_CEILING_USD ({band_ceiling})"
            )

        band_rate_halt = _float_env("KG_BAND_RATE_HALT", DEFAULT_BAND_RATE_HALT)
        if not 0 < band_rate_halt <= 1:
            raise ConfigError(f"KG_BAND_RATE_HALT must be in (0, 1], got {band_rate_halt}")

        max_hops = _int_env("KG_MAX_HOPS", DEFAULT_MAX_HOPS)
        if not 1 <= max_hops <= HARD_MAX_HOPS:
            raise ConfigError(f"KG_MAX_HOPS must be in [1, {HARD_MAX_HOPS}], got {max_hops}")

        db_raw = os.environ.get("KG_DB_PATH") or None
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY") or None,
            neo4j_uri=os.environ.get("NEO4J_URI") or None,
            corpus_root=_path_env("KG_CORPUS_ROOT", DEFAULT_CORPUS_ROOT),
            librarian_root=_path_env("LIBRARIAN_ROOT", DEFAULT_LIBRARIAN_ROOT),
            proposer_model=os.environ.get("KG_PROPOSER_MODEL") or DEFAULT_PROPOSER_MODEL,
            judge_model=os.environ.get("KG_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL,
            build_ceiling_usd=build_ceiling,
            band_ceiling_usd=band_ceiling,
            band_rate_halt=band_rate_halt,
            max_hops=max_hops,
            db_path=Path(db_raw).expanduser() if db_raw else None,
        )

    def require_anthropic_key(self) -> str:
        if not self.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is not set; the proposer and the Claude seat are unavailable"
            )
        return self.anthropic_api_key

    def require_openrouter_key(self) -> str:
        if not self.openrouter_api_key:
            raise ConfigError("OPENROUTER_API_KEY is not set; the Jev seat is unavailable")
        return self.openrouter_api_key

    def require_neo4j_uri(self) -> str:
        if not self.neo4j_uri:
            raise ConfigError("NEO4J_URI is not set; the Neo4j store is unavailable")
        return self.neo4j_uri

    def require_corpus_root(self) -> Path:
        if not self.corpus_root.is_dir():
            raise ConfigError(f"KG_CORPUS_ROOT does not exist: {self.corpus_root}")
        return self.corpus_root

    def require_librarian_root(self) -> Path:
        if not self.librarian_root.is_dir():
            raise ConfigError(f"LIBRARIAN_ROOT does not exist: {self.librarian_root}")
        return self.librarian_root


def _path_env(name: str, default: str) -> Path:
    return Path(os.environ.get(name) or default).expanduser()


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
