"""Render an InteractionReport as a self-contained HTML page.

One card per enabled metric (composed from the registry via the report's
summaries), pass/fail against the metric's targets.yaml key when set, or a
default bar otherwise. Plain string assembly — no template engine, so the
report works with the base dependency set.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from evals.graders.metrics_registry import METRICS
from evals.models import InteractionReport, MetricSummary

DEFAULT_PASS_BAR = 0.8

_CSS = """
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
  .meta { color: #666; font-size: 0.85rem; margin-bottom: 1.5rem; }
  .verdict { font-size: 1.8rem; font-weight: 700; margin-bottom: 1.5rem; }
  .verdict.pass { color: #16a34a; }
  .verdict.fail { color: #dc2626; }
  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }
  .card { border-radius: 8px; padding: 1rem; border: 1px solid #ddd; }
  .card.pass { border-color: #86efac; background: #f0fdf4; }
  .card.fail { border-color: #fca5a5; background: #fef2f2; }
  .card.na { border-color: #ddd; background: #fafafa; }
  .card .name { font-size: 0.8rem; font-weight: 600; color: #555; margin-bottom: 0.4rem; }
  .card .rate { font-size: 1.5rem; font-weight: 700; }
  .card .detail { font-size: 0.75rem; color: #888; margin-top: 0.2rem; }
  .card .desc { font-size: 0.75rem; color: #777; margin-top: 0.5rem; }
"""


def _effective_pass_rate(summary: MetricSummary) -> float | None:
    """Judge pass-rate when judges scored rows, heuristic pass-rate otherwise."""
    if summary.judge_pass_rate is not None:
        return summary.judge_pass_rate
    return summary.heuristic_pass_rate


def _metric_card(summary: MetricSummary, targets: dict[str, float]) -> str:
    definition = METRICS.get(summary.metric)
    bar = targets.get(definition.targets_key, DEFAULT_PASS_BAR) if definition else DEFAULT_PASS_BAR
    rate = _effective_pass_rate(summary)
    if rate is None:
        state, rate_text, detail = "na", "n/a", "no gradeable rows"
    else:
        state = "pass" if rate >= bar else "fail"
        rate_text = f"{rate * 100:.0f}%"
        source = "judge" if summary.judge_pass_rate is not None else "heuristic"
        detail = f"{source} pass-rate · bar {bar:.2f} · n={summary.n_judge or summary.n_heuristic}"
        if summary.judge_mean_score is not None:
            detail += f" · judge score {summary.judge_mean_score:.2f}"
    description = escape(definition.description) if definition else ""
    return (
        f'<div class="card {state}">'
        f'<div class="name">{escape(summary.metric)}</div>'
        f'<div class="rate">{rate_text}</div>'
        f'<div class="detail">{escape(detail)}</div>'
        f'<div class="desc">{description}</div>'
        f"</div>"
    )


def render_html(report: InteractionReport, targets: dict[str, float] | None = None) -> str:
    targets = targets or {}
    measured = [s for s in report.summaries if _effective_pass_rate(s) is not None]
    overall_pass = bool(measured) and all(
        rate >= targets.get(METRICS[s.metric].targets_key, DEFAULT_PASS_BAR)
        for s in measured
        if (rate := _effective_pass_rate(s)) is not None
    )
    verdict_class = "pass" if overall_pass else "fail"
    verdict_text = "PASS" if overall_pass else "FAIL"
    grading_mode = "heuristics + LLM judges" if report.judges_ran else "heuristics only"
    cards = "\n".join(_metric_card(summary, targets) for summary in report.summaries)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        "<title>Interaction eval report</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        "<h1>Interaction eval report</h1>\n"
        f'<div class="meta">Generated: {escape(report.generated_at)} · '
        f"{report.n_interactions} interactions · {grading_mode}"
        f"{' · PII redacted' if report.redaction_applied else ''}</div>\n"
        f'<div class="verdict {verdict_class}">{verdict_text}</div>\n'
        f'<div class="cards">\n{cards}\n</div>\n'
        "</body>\n</html>\n"
    )


def write_report(
    report: InteractionReport,
    output_path: Path,
    targets: dict[str, float] | None = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(report, targets), encoding="utf-8")
    return output_path
