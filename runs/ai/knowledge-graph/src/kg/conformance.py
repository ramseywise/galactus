"""The build's `experiments.record.RunRecord`: what the shared registry keeps of a build.

`RunRecord.metrics` is `dict[str, float]`, so a `NotApplicable` metric cannot sit inside it.
A metric with no denominator is therefore left out of `metrics` and named, with its reason,
under `resolved_config["not_applicable_metrics"]`; it is never written as 0.0. The headline
is `band_rate`, but when band rate is not applicable the headline falls back to
`accepted_count` (a count, always defined) and `resolved_config["headline_note"]` says so.
"""

from __future__ import annotations

from pathlib import Path

from experiments.io import write_record
from experiments.provenance import capture_code_state
from experiments.record import DataIdentity, ExecutionConfig, NotApplicable, RunRecord
from kg.build import BuildReport

RUN_KIND = "kg-build"


def record_from_report(report: BuildReport, *, repo: Path | None = None) -> RunRecord:
    metrics: dict[str, float] = {
        "accepted_count": float(report.accepted),
        "not_run_count": float(report.pages_not_run),
        "judge_not_run_count": float(report.judge_not_run),
        "no_candidates_count": float(report.pages_no_candidates),
        "pages_total": float(report.pages_total),
        "candidates_proposed": float(report.candidates_proposed),
        "verdicts": float(report.verdicts),
    }
    na: dict[str, str] = {}
    for name, value in (
        ("gate_pass_rate", report.gate_pass_rate),
        ("band_rate", report.band_rate),
        ("cost_usd", report.cost_usd),
    ):
        if isinstance(value, NotApplicable):
            na[name] = value.reason
        else:
            metrics[name] = float(value)

    if "band_rate" in metrics:
        headline, note = "band_rate", "band_rate = review-tier share of judged verdicts"
    else:
        headline = "accepted_count"
        note = (
            f"band_rate not applicable ({na['band_rate']}); headline falls back to accepted_count"
        )

    return RunRecord(
        code=capture_code_state(repo),
        data=DataIdentity(
            frame_hash=report.profile_hash,
            n_rows=report.pages_total,
            n_cols=1,
            columns=("body",),
        ),
        execution=ExecutionConfig(
            seed=NotApplicable("model calls are not seeded"),
            resolved_config={
                "build_id": report.build_id,
                "domain": report.domain,
                "dry_run": report.dry_run,
                "status": report.status,
                "pack": report.pack_name,
                "pack_hash": report.pack_hash,
                "pack_approved": report.pack_approved,
                "estimate_usd": report.estimate_usd,
                "not_applicable_metrics": na,
                "headline_note": note,
                "promotable": report.promotable,
                "halted_reason": report.halted_reason or "",
            },
            folds=NotApplicable("a build has no train/test split"),
        ),
        metrics=metrics,
        headline_metric=headline,
        run_kind=RUN_KIND,
    )


def record_path(records_dir: Path, build_id: str) -> Path:
    return records_dir / f"{build_id}.json"


def write_conformance(report: BuildReport, records_dir: Path) -> Path:
    """Write `<records_dir>/<build_id>.json` via the registry's `write_record`."""
    return write_record(record_from_report(report), record_path(records_dir, report.build_id))
