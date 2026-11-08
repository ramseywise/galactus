"""Per-model token prices the pre-build estimate uses.

Source: the claude-api skill's model table (cached 2026-10-06), which mirrors
SOURCE_URL. Prices drift; re-check SOURCE_URL before a live build and update
SOURCE_DATE with the change. A model missing from PRICES is refused at estimate time
rather than priced at $0 (fog FA-010).
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCE_URL = "https://platform.claude.com/docs/en/about-claude/pricing"
SOURCE_DATE = "2026-10-06"


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float


PRICES: dict[str, ModelPrice] = {
    # Base rate for prompts up to 100K tokens; per-page prompts here are far below that.
    "claude-haiku-5-5": ModelPrice(input_per_mtok=0.10, output_per_mtok=0.50),
    "claude-sonnet-5-5": ModelPrice(input_per_mtok=2.00, output_per_mtok=10.00),
}
