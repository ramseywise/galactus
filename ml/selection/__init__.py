"""Model selection — the registry of what can be fitted, per family and output."""

from __future__ import annotations

from ml.selection.registry import (
    RANDOM_STATE,
    ModelSpec,
    ReservedModelError,
    get_models,
    get_spec,
    get_specs,
    valid_pairs,
)

__all__ = [
    "RANDOM_STATE",
    "ModelSpec",
    "ReservedModelError",
    "get_models",
    "get_spec",
    "get_specs",
    "valid_pairs",
]
