"""Step 16 — the run report.

A single self-contained HTML file summarising one classification run: the model
comparison, what calibration did, and the chosen operating point.

**Aggregates only.** Nothing here writes a row, an index, or an identifier — a
report on real data is a document that gets emailed, and the moment it carries a
record it inherits every handling constraint the dataset has. Metrics, counts,
and column *names* are the whole vocabulary.

The report states its own validation strategy and flags a null result rather
than presenting the best model as a win regardless. A comparison table that
always reads like a success teaches the reader nothing.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

_STYLE = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       margin: 2rem auto; max-width: 60rem; color: #1a1a1a; line-height: 1.5; }
h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #ddd;
     padding-bottom: 0.25rem; }
table { border-collapse: collapse; width: 100%; margin-top: 0.75rem; }
th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee;
         font-variant-numeric: tabular-nums; }
th { background: #fafafa; font-weight: 600; }
tr.baseline td { background: #fcfcf5; }
tr.best td { font-weight: 600; }
.verdict { padding: 0.75rem 1rem; border-radius: 4px; margin-top: 0.75rem; }
.verdict.win { background: #eef7ee; border-left: 4px solid #4a7; }
.verdict.null { background: #fdf6e8; border-left: 4px solid #da4; }
.meta { color: #666; font-size: 0.9rem; }
code { background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 3px; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _num(value: Any, places: int = 4) -> str:
    """Format a number, distinguishing 'not computed' from zero."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{places}f}"
    except (TypeError, ValueError):
        return _esc(value)


def _model_table(result: Any) -> str:
    best = result.best
    rows = []
    for model in result.models:
        classes = []
        if model.is_baseline:
            classes.append("baseline")
        if best is not None and model is best:
            classes.append("best")
        attr = f' class="{" ".join(classes)}"' if classes else ""

        label = _esc(model.name)
        if model.is_baseline:
            label += " <span class='meta'>(baseline)</span>"

        rows.append(
            f"<tr{attr}><td>{label}</td>"
            f"<td>{_num(getattr(model.metrics, 'average_precision', None))}</td>"
            f"<td>{_num(getattr(model.metrics, 'roc_auc', None))}</td>"
            f"<td>{_num(getattr(model.metrics, 'brier', None))}</td>"
            f"<td>{_num(model.fit_seconds, 1)}</td></tr>"
        )

    return (
        "<table><thead><tr><th>model</th><th>PR-AUC</th><th>ROC-AUC</th>"
        "<th>Brier</th><th>fit (s)</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _verdict(result: Any) -> str:
    baseline, best = result.baseline, result.best
    if best is None:
        return "<div class='verdict null'>No model produced a score.</div>"
    if baseline is None:
        return (
            "<div class='verdict null'>No baseline ran, so there is no floor to "
            "compare against — the leading model is unranked, not validated.</div>"
        )

    if best is baseline:
        return (
            "<div class='verdict null'>Only the baseline ran, so there is nothing "
            "to compare it against. A single-model run is a measurement, not a "
            "comparison — add a candidate before reading this as a result.</div>"
        )

    margin = None
    if best.headline is not None and baseline.headline is not None:
        margin = best.headline - baseline.headline

    if result.beats_baseline:
        return (
            f"<div class='verdict win'><strong>{_esc(best.name)}</strong> beats the "
            f"logistic baseline by {_num(margin)} PR-AUC.</div>"
        )
    return (
        "<div class='verdict null'><strong>Null result:</strong> nothing beats the "
        f"baseline. Best margin is {_num(margin)} PR-AUC, inside the noise band. "
        "That is a finding about feature quality, not a failed run — and the "
        "baseline is the cheaper, more explainable model.</div>"
    )


def _calibration_table(result: Any) -> str:
    rows = []
    for model in result.models:
        cal = model.calibration
        if cal is None:
            continue
        before = getattr(cal, "brier_before", None)
        after = getattr(cal, "brier_after", None)
        improved = getattr(cal, "improved", None)
        verdict = "improved" if improved else "no improvement"
        rows.append(
            f"<tr><td>{_esc(model.name)}</td>"
            f"<td>{_esc(getattr(cal, 'method', '—'))}</td>"
            f"<td>{_num(before)}</td><td>{_num(after)}</td>"
            f"<td>{_num(getattr(cal, 'expected_calibration_error_before', None))}</td>"
            f"<td>{_num(getattr(cal, 'expected_calibration_error_after', None))}</td>"
            f"<td>{verdict}</td></tr>"
        )

    if not rows:
        return "<p class='meta'>Calibration was not run.</p>"

    return (
        "<p class='meta'>Calibration is not guaranteed to help. Where the Brier "
        "score got worse, that is shown rather than hidden.</p>"
        "<table><thead><tr><th>model</th><th>method</th><th>Brier before</th>"
        "<th>Brier after</th><th>ECE before</th><th>ECE after</th><th>verdict</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _threshold_table(result: Any) -> str:
    rows = []
    for model in result.models:
        thr = model.threshold
        if thr is None:
            continue
        rows.append(
            f"<tr><td>{_esc(model.name)}</td>"
            f"<td>{_num(getattr(thr, 'threshold', None), 3)}</td>"
            f"<td>{_num(getattr(thr, 'precision', None), 3)}</td>"
            f"<td>{_num(getattr(thr, 'recall', None), 3)}</td>"
            f"<td>{_esc(getattr(thr, 'n_flagged', '—'))}</td>"
            f"<td>{_num(getattr(thr, 'expected_cost', None), 1)}</td>"
            f"<td>{_num(getattr(thr, 'cost_at_default', None), 1)}</td>"
            f"<td>{_num(getattr(thr, 'savings_vs_default', None), 1)}</td></tr>"
        )

    if not rows:
        return "<p class='meta'>No costs were supplied, so no operating point was chosen.</p>"

    return (
        "<p class='meta'>Thresholds are chosen on out-of-fold probabilities and "
        "minimise expected cost. <code>cost at 0.5</code> is what the default "
        "convention would have cost — the difference is the argument for having "
        "chosen at all.</p>"
        "<table><thead><tr><th>model</th><th>threshold</th><th>precision</th>"
        "<th>recall</th><th>flagged</th><th>expected cost</th><th>cost at 0.5</th>"
        "<th>saving</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _run_facts(result: Any) -> str:
    plan = result.split_plan
    balance = ", ".join(
        f"{_esc(k)}: {v:.2%}" for k, v in sorted(result.class_balance.items(), key=str)
    )
    facts = [
        ("rows", f"{result.n_rows:,}"),
        ("features", f"{result.n_features:,}"),
        ("target", _esc(result.target)),
        ("class balance", balance),
        ("sampling", _esc(result.sampling)),
        (
            "validation",
            f"{_esc(plan.kind)} ({plan.n_splits} folds)" if plan else "—",
        ),
    ]
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in facts)
    body = f"<table><tbody>{rows}</tbody></table>"

    if result.skipped:
        skipped = "".join(
            f"<li><code>{_esc(name)}</code> — {_esc(reason)}</li>"
            for name, reason in result.skipped.items()
        )
        body += (
            "<p class='meta'>Models that did not run (recorded rather than "
            f"silently omitted):</p><ul>{skipped}</ul>"
        )
    return body


def write_report(result: Any, path: str | Path, *, title: str = "Classification run") -> Path:
    """Write the run report to `path` and return it.

    Parent directories are created — the caller's chosen location is treated as
    the instruction it is, rather than failing on a missing folder.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{_esc(title)}</title><style>{_STYLE}</style></head>
<body>
<h1>{_esc(title)}</h1>
<p class="meta">Aggregates only — this report contains no rows, indices, or identifiers.</p>

<h2>Run</h2>
{_run_facts(result)}

<h2>Model comparison</h2>
{_model_table(result)}
{_verdict(result)}

<h2>Calibration</h2>
{_calibration_table(result)}

<h2>Operating point</h2>
{_threshold_table(result)}
</body></html>
"""
    out.write_text(document, encoding="utf-8")
    return out
