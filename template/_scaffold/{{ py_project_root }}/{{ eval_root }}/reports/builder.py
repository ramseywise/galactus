"""Assemble an InteractionReport from a graded interactions JSONL file.

Per-metric summaries come from the metric modules via the registry — the
report composes whatever metrics this project enabled, nothing hardcoded.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.graders.metrics_registry import METRICS
from evals.models import GraderResult, InteractionReport


def load_graded(path: Path) -> list[dict[str, Any]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def build_report(
    rows: list[dict[str, Any]],
    judges_ran: bool = False,
    redaction_applied: bool = False,
) -> InteractionReport:
    results = [
        GraderResult.model_validate(grade) for row in rows for grade in row.get("grades", [])
    ]
    return InteractionReport(
        generated_at=datetime.now(UTC).isoformat(),
        n_interactions=len(rows),
        judges_ran=judges_ran,
        redaction_applied=redaction_applied,
        summaries=[definition.summarize(results) for definition in METRICS.values()],
    )
