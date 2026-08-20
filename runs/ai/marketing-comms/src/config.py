"""Environment-backed configuration.

The API key is read from the environment (optionally seeded from a gitignored
`.env`) and is never written to disk by this module. `Settings.load()` does not
require the key to be present — Steps 3-5 are entirely deterministic and run
without any provider credential. `require_api_key()` is the explicit gate for
the code paths that actually call a provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_REPAIRS = 3
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_PDF_PAGES = 40
DEFAULT_RATE_LIMIT_PER_MINUTE = 10
DEFAULT_MAX_CONCURRENT_JOBS = 4
DEFAULT_RETENTION_DAYS = 30


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings."""

    anthropic_api_key: str | None
    model: str
    max_repairs: int
    log_level: str
    db_path: str | None = None
    """SQLite file for the store. None keeps the in-memory default —
    fine for tests and throwaway demos, but uploads and results then die with
    the process, and multiple workers each get a private database."""
    api_key: str | None = None
    """Shared secret for the HTTP surface (`X-API-Key`). None leaves the API
    open — acceptable on localhost, never behind a public listener."""
    max_pdf_pages: int = DEFAULT_MAX_PDF_PAGES
    """Page cap on one ingested PDF. The vision path bills per rendered page,
    so an unbounded upload is an unbounded spend; over the cap the upload is
    rejected and ingest refuses, loudly in both places."""
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    """Generation requests one caller may make per minute. 0 disables."""
    max_concurrent_jobs: int = DEFAULT_MAX_CONCURRENT_JOBS
    """Generation jobs allowed to run at once; the rest wait as `queued`."""
    retention_days: int = DEFAULT_RETENTION_DAYS
    """Age at which finished jobs and uploaded PDFs are swept. 0 disables."""

    @classmethod
    def load(cls, *, use_dotenv: bool = True) -> Settings:
        """Read settings from the environment.

        Args:
            use_dotenv: If True, seed missing values from a `.env` file in the
                working directory or its parents. Existing environment
                variables always win.
        """
        if use_dotenv:
            load_dotenv(override=False)

        max_repairs = _int_env("GALACTUS_MAX_REPAIRS", DEFAULT_MAX_REPAIRS)
        if max_repairs < 0:
            raise ConfigError(f"GALACTUS_MAX_REPAIRS must be >= 0, got {max_repairs}")

        # Validated at load, not first use: an operator typo in a budget knob
        # should fail the deploy, not the one request that hits the edge.
        max_pdf_pages = _int_env("GALACTUS_MAX_PDF_PAGES", DEFAULT_MAX_PDF_PAGES)
        if max_pdf_pages < 1:
            raise ConfigError(f"GALACTUS_MAX_PDF_PAGES must be >= 1, got {max_pdf_pages}")

        rate_limit_per_minute = _int_env(
            "GALACTUS_RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE
        )
        if rate_limit_per_minute < 0:
            raise ConfigError(
                f"GALACTUS_RATE_LIMIT_PER_MINUTE must be >= 0, got {rate_limit_per_minute}"
            )

        max_concurrent_jobs = _int_env("GALACTUS_MAX_CONCURRENT_JOBS", DEFAULT_MAX_CONCURRENT_JOBS)
        if max_concurrent_jobs < 1:
            raise ConfigError(
                f"GALACTUS_MAX_CONCURRENT_JOBS must be >= 1, got {max_concurrent_jobs}"
            )

        retention_days = _int_env("GALACTUS_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)
        if retention_days < 0:
            raise ConfigError(f"GALACTUS_RETENTION_DAYS must be >= 0, got {retention_days}")

        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
            model=os.environ.get("GALACTUS_MODEL", DEFAULT_MODEL),
            max_repairs=max_repairs,
            log_level=os.environ.get("GALACTUS_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
            db_path=os.environ.get("GALACTUS_DB_PATH") or None,
            api_key=os.environ.get("GALACTUS_API_KEY") or None,
            max_pdf_pages=max_pdf_pages,
            rate_limit_per_minute=rate_limit_per_minute,
            max_concurrent_jobs=max_concurrent_jobs,
            retention_days=retention_days,
        )

    def require_api_key(self) -> str:
        """Return the API key, or raise if it is not configured.

        Called only by provider-backed code paths. Keeps the deterministic
        core (contract, validator, fallback) runnable with no credential.
        """
        if not self.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        return self.anthropic_api_key


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
