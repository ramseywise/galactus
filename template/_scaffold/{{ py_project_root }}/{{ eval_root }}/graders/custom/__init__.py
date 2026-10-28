"""Registry for project-specific eval graders.

The built-in heuristic metrics (hit_rate, mean_reciprocal_rank,
mean_answer_overlap) are retrieval-shaped. Most real projects have one primary
metric that is not — action-item extraction accuracy, classification F1,
whatever the DESIGN.md Evaluation table names. Register it here and it becomes
gateable in targets.yaml with zero changes to the runner.

Write a module in this package:

    from evals.graders.custom import register

    @register("action_item_accuracy")
    def score(golden_row: dict, generated: str | None) -> float | None:
        # Return a 0.0-1.0 score for one golden row, or None to skip the row
        # (e.g. when it needs a generated answer that wasn't produced).
        ...

Modules in this package are imported automatically by the eval runner; each
grader's per-row scores are averaged into ``HeuristicReport.custom_scores``
under its registered name, which targets.yaml can then gate on
(``make eval-gate``).
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Mapping

CustomGrader = Callable[[dict, "str | None"], "float | None"]

_REGISTRY: dict[str, CustomGrader] = {}


def register(name: str) -> Callable[[CustomGrader], CustomGrader]:
    def _wrap(fn: CustomGrader) -> CustomGrader:
        _REGISTRY[name] = fn
        return fn

    return _wrap


def all_graders() -> Mapping[str, CustomGrader]:
    """Import every module in this package (so @register decorators run), then
    return the registry."""
    for mod in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{mod.name}")
    return dict(_REGISTRY)
