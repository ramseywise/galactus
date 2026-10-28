from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ContextBudgetSettings(BaseSettings):
    """Token-budget settings for context_budget/ — separate from each agent's
    own Settings class since budget tracking is cross-agent (any present agent
    wraps its calls with the same budget tracker). Same convention as
    observability/settings.py's ObservabilitySettings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Maximum context-window tokens before compaction fires.
    # Claude claude-haiku-4-5-20251001 / claude-sonnet-* window = 200 000;
    # set conservatively so there is headroom for the compaction summary itself.
    max_context_tokens: int = 180_000

    # Fraction of max_context_tokens at which the compaction trigger fires.
    # 0.8 → fire when used ≥ 80 % of the window.
    compaction_threshold: float = 0.8

    # Log per-category breakdowns (system / history / tools / scratch) at INFO.
    log_token_categories: bool = True


settings = ContextBudgetSettings()
