"""Compare a run against declared targets and against the previous run.

The gap this closes: a metric reported on its own is uninterpretable. "PR-AUC
0.02" reads as a failure, or as a success, depending entirely on a prevalence
figure that is usually somewhere else on the page. And a run compared against
nothing cannot tell you whether the change you just made helped.

Two comparisons, deliberately separate:

- **Absolute targets** — a floor from a business requirement. The only floor that
  is never wrong is `average_precision_over_prevalence: 1.0`: a model scoring at
  prevalence is a model that has learned nothing, whatever the raw number is.
- **Baseline** — the previous run's numbers, from `baseline.json`. Regressions are
  judged against a tolerance rather than a strict `<`, because a 0.0002 movement
  is noise and reporting it as a regression trains people to ignore the gate.

Directionality is explicit in `targets.yaml` (`lower_is_better`). Assuming
higher-is-better for a Brier score silently inverts the gate, which is worse than
having no gate at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

TARGETS_FILE = Path(__file__).parent / "targets.yaml"

DEFAULT_LOWER_IS_BETTER = frozenset({"brier", "log_loss", "expected_cost"})


@dataclass(frozen=True)
class MetricVerdict:
    """One metric's outcome against one comparison."""

    metric: str
    value: float
    comparison: str
    """"target" or "baseline"."""
    reference: float | None
    passed: bool
    detail: str

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"[{mark}] {self.metric}: {self.detail}"


@dataclass
class RunVerdict:
    """Every verdict for one run, plus the overall pass/fail."""

    verdicts: list[MetricVerdict] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    """metric -> why it was not compared. A metric silently absent from a gate
    report looks like a pass."""

    @property
    def passed(self) -> bool:
        return all(v.passed for v in self.verdicts)

    @property
    def failures(self) -> list[MetricVerdict]:
        return [v for v in self.verdicts if not v.passed]

    def report(self) -> str:
        lines = [str(v) for v in self.verdicts]
        lines.extend(
            f"[SKIP] {metric}: {reason}" for metric, reason in sorted(self.skipped.items())
        )
        lines.append("")
        lines.append(f"overall: {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


def load_targets(path: Path = TARGETS_FILE) -> dict[str, Any]:
    """Read `targets.yaml`. Missing file yields empty targets rather than raising —
    a project that has not set targets yet should still be able to run."""
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _lower_is_better(targets: dict[str, Any]) -> frozenset[str]:
    declared = (targets.get("direction") or {}).get("lower_is_better") or []
    return frozenset(declared) | DEFAULT_LOWER_IS_BETTER


def check_absolute(
    metrics: dict[str, float],
    targets: dict[str, Any] | None = None,
    prevalence: float | None = None,
) -> RunVerdict:
    """Check metrics against the absolute floors in `targets.yaml`."""
    targets = targets if targets is not None else load_targets()
    absolute = targets.get("absolute") or {}
    lower_better = _lower_is_better(targets)
    verdict = RunVerdict()

    for name, floor in absolute.items():
        if name == "average_precision_over_prevalence":
            _check_over_prevalence(metrics, floor, prevalence, verdict)
            continue
        if name not in metrics:
            verdict.skipped[name] = "not reported by this run"
            continue
        value = metrics[name]
        passed = value <= floor if name in lower_better else value >= floor
        direction = "<=" if name in lower_better else ">="
        verdict.verdicts.append(
            MetricVerdict(
                metric=name,
                value=value,
                comparison="target",
                reference=float(floor),
                passed=passed,
                detail=f"{value:.4f} {direction} {floor} required",
            )
        )

    return verdict


def _check_over_prevalence(
    metrics: dict[str, float],
    ratio: float,
    prevalence: float | None,
    verdict: RunVerdict,
) -> None:
    """The one floor that is never wrong: beat chance.

    Skipped rather than passed when prevalence is unknown — a gate that cannot be
    evaluated must not report success.
    """
    if prevalence is None:
        verdict.skipped["average_precision_over_prevalence"] = (
            "prevalence not supplied; cannot tell this metric from chance"
        )
        return
    if "average_precision" not in metrics:
        verdict.skipped["average_precision_over_prevalence"] = "average_precision not reported"
        return
    if prevalence <= 0:
        verdict.skipped["average_precision_over_prevalence"] = f"prevalence is {prevalence}"
        return

    value = metrics["average_precision"]
    achieved = value / prevalence
    verdict.verdicts.append(
        MetricVerdict(
            metric="average_precision_over_prevalence",
            value=achieved,
            comparison="target",
            reference=float(ratio),
            passed=achieved >= ratio,
            detail=(
                f"PR-AUC {value:.4f} is {achieved:.2f}x prevalence {prevalence:.4f} "
                f"({ratio}x required — 1.0x is chance)"
            ),
        )
    )


def check_baseline(
    metrics: dict[str, float],
    baseline_path: Path,
    targets: dict[str, Any] | None = None,
) -> RunVerdict:
    """Compare against the previous run's `baseline.json`.

    A missing baseline is the first run: every metric is skipped with that stated,
    never passed. "No baseline" and "no regression" are different facts.
    """
    targets = targets if targets is not None else load_targets()
    baseline_config = targets.get("baseline") or {}
    tolerance = float(baseline_config.get("tolerance", 0.01))
    tracked = baseline_config.get("metrics") or sorted(metrics)
    lower_better = _lower_is_better(targets)
    verdict = RunVerdict()

    if not baseline_path.exists():
        for name in tracked:
            verdict.skipped[name] = f"no baseline at {baseline_path} — this is the first run"
        return verdict

    previous = json.loads(baseline_path.read_text()).get("metrics", {})

    for name in tracked:
        if name not in metrics:
            verdict.skipped[name] = "not reported by this run"
            continue
        if name not in previous:
            verdict.skipped[name] = "absent from the baseline"
            continue

        value, reference = metrics[name], float(previous[name])
        change = value - reference
        regressed = (change > tolerance) if name in lower_better else (change < -tolerance)
        if abs(change) <= tolerance:
            summary = f"{value:.4f} vs {reference:.4f} — unchanged within {tolerance}"
        else:
            summary = f"{value:.4f} vs {reference:.4f} ({change:+.4f})"

        verdict.verdicts.append(
            MetricVerdict(
                metric=name,
                value=value,
                comparison="baseline",
                reference=reference,
                passed=not regressed,
                detail=summary,
            )
        )

    return verdict


def write_baseline(
    metrics: dict[str, float],
    baseline_path: Path,
    model_name: str,
    prevalence: float | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Record this run as the baseline for the next one.

    Writes `prevalence` alongside the metrics because a stored metric without it
    cannot be re-interpreted later — the number alone does not say whether it beat
    chance.
    """
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "model": model_name,
        "metrics": {k: float(v) for k, v in metrics.items()},
    }
    if prevalence is not None:
        payload["prevalence"] = float(prevalence)
    if extra:
        payload.update(extra)
    baseline_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return baseline_path
