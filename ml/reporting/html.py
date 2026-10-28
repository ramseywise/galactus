"""`RunResult` → one self-contained HTML file.

The output has zero external references: the CSS is read off disk and inlined,
the charts are inline SVG, and there is no script tag at all. A report written
today opens identically on a machine with no network in five years, which is the
only durability guarantee worth making to a partner who will not have us around
to regenerate it.

The reporting layer reads `RunResult` and never reaches back into the estimators
for anything it cannot get defensively — feature importance is attempted and
omitted on failure rather than raising, because a report that refuses to render
because one model lacks `coef_` is worse than a report with one panel missing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

import numpy as np

from ml.evaluation.metrics import (
    ClassificationMetrics,
    ClusteringMetrics,
    RegressionMetrics,
)
from ml.reporting.charts import bar_svg, confusion_svg, curve_svg, reliability_svg
from ml.workflows.base import ModelResult, RunResult

logger = logging.getLogger(__name__)

STYLE_PATH = Path(__file__).with_name("style.css")

METRIC_LABELS = {
    "average_precision": "PR-AUC",
    "roc_auc": "ROC-AUC",
    "brier": "Brier",
    "f1": "F1",
    "balanced_accuracy": "Bal. acc.",
    "rmse": "RMSE",
    "mae": "MAE",
    "r2": "R²",
    "silhouette": "Silhouette",
    "davies_bouldin": "Davies-Bouldin",
    "n_clusters": "Clusters",
    "fit_seconds": "Fit (s)",
}


def write_report(result: RunResult, out_path: Path, *, title: str = "Model report") -> Path:
    """Render `result` to a single HTML file at `out_path` and return that path.

    Creates parent directories. Overwrites without asking — a report is derived
    output, regenerated every run, and treating it as precious would make the
    workflow annoying to iterate on.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(result, title=title), encoding="utf-8")
    return out_path


def render_report(result: RunResult, *, title: str = "Model report") -> str:
    """The full HTML document as a string. `write_report` is this plus a file write."""
    css = STYLE_PATH.read_text(encoding="utf-8")
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    sections = [
        _header(result, title=title, generated=generated),
        _metadata(result),
        _verdict(result),
        _comparison(result),
        _curves(result),
        _calibration(result),
        _threshold(result),
        _importance(result),
        _data_quality(result),
        _skipped(result),
    ]

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>\n{css}\n</style>\n"
        "</head>\n<body>\n<main>\n"
        + "\n".join(s for s in sections if s)
        + f"\n<footer>Generated {escape(generated)} · seed {result.seed} · "
        "every number here is out-of-fold unless stated otherwise.</footer>\n"
        "</main>\n</body>\n</html>\n"
    )


def _header(result: RunResult, *, title: str, generated: str) -> str:
    target = f"target <code>{escape(result.target)}</code>" if result.target else "unsupervised"
    return (
        f"<h1>{escape(title)}</h1>\n"
        f'<p class="subtitle">{escape(result.family)} · {escape(result.output)} · '
        f"{target} · {result.n_rows:,} rows × {result.n_features} features</p>"
    )


def _metadata(result: RunResult) -> str:
    plan = result.column_plan
    items: list[tuple[str, str]] = [
        ("Rows", f"{result.n_rows:,}"),
        ("Features", str(result.n_features)),
        ("Seed", str(result.seed)),
        ("Models fitted", str(len(result.models))),
        ("Numeric", str(len(plan.numeric))),
        ("Categorical", str(len(plan.categorical))),
    ]
    if result.split_plan is not None:
        items.append(("Split", f"{result.split_plan.kind} ×{result.split_plan.n_splits}"))
    if result.sampling and result.sampling != "none":
        items.append(("Sampling", result.sampling))
    if result.class_balance:
        minority = min(result.class_balance.values())
        total = sum(result.class_balance.values()) or 1
        items.append(("Minority", f"{minority / total:.1%}"))

    cells = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>" for label, value in items
    )
    out = f'<h2>Run</h2>\n<dl class="meta">{cells}</dl>'
    if result.split_plan is not None:
        out += f'\n<p class="note">{escape(result.split_plan.reason)}</p>'
    return out


def _verdict(result: RunResult) -> str:
    """The one paragraph a reader who reads nothing else should get right."""
    best = result.best
    if best is None:
        return '<p class="note bad">No model was fitted successfully.</p>'

    name, value = _headline(best)
    beats = result.beats_baseline()
    margin = result.baseline_margin
    if beats is None and margin is not None:
        # A comparison happened and landed inside the tie band. Distinct from the
        # other two `None` cases below, which mean there was no comparison at all
        # — a reader told "tie" and a reader told "no baseline" need to do
        # different things.
        base = result.baseline
        body = (
            f"<strong>{escape(best.name)}</strong> and the "
            f"<strong>{escape(base.name)}</strong> baseline are a tie at {escape(name)} "
            f"— a margin of {margin:+.4g}, inside the noise of the comparison. "
            "Prefer the baseline; the extra complexity bought nothing measurable."
        )
        css = "warn"
    elif beats is None and result.baseline is best:
        body = (
            f"<strong>{escape(best.name)}</strong> is the best model at "
            f"{escape(name)} {value:.4g} — and it <strong>is</strong> the baseline. "
            "Nothing more expensive earned its complexity here; ship the simple one."
        )
        css = "warn"
    elif beats is None:
        body = (
            f"<strong>{escape(best.name)}</strong> leads at {escape(name)} {value:.4g}. "
            "No baseline was fitted, so there is nothing to say about whether the "
            "complexity was worth it."
        )
        css = "warn"
    elif beats:
        base = result.baseline
        _, base_value = _headline(base) if base else (name, float("nan"))
        body = (
            f"<strong>{escape(best.name)}</strong> beats the "
            f"<strong>{escape(base.name)}</strong> baseline at {escape(name)}: "
            f"{value:.4g} vs {base_value:.4g}."
        )
        css = "good"
    else:
        body = (
            f"The baseline is not beaten — <strong>{escape(best.name)}</strong> leads the "
            "ranking but does not improve on it. Prefer the baseline."
        )
        css = "warn"
    return f'<h2>Verdict</h2>\n<p class="note {css}">{body}</p>'


def _comparison(result: RunResult) -> str:
    if not result.models:
        return ""
    frame = result.comparison_frame()
    columns = [c for c in frame.columns if c not in ("model", "baseline")]

    head = "".join(f"<th>{escape(METRIC_LABELS.get(c, c))}</th>" for c in columns)
    rows = []
    for i, model in enumerate(result.models):
        record = frame.iloc[i]
        tags = ""
        if i == 0:
            tags += '<span class="tag best">best</span>'
        if model.is_baseline:
            tags += '<span class="tag">baseline</span>'
        cells = "".join(f"<td>{_fmt(record[c])}</td>" for c in columns)
        klass = ' class="best"' if i == 0 else ""
        rows.append(f"<tr{klass}><td>{escape(model.name)}{tags}</td>{cells}</tr>")

    return (
        "<h2>Model comparison</h2>\n"
        '<div class="table-wrap"><table>\n'
        f"<thead><tr><th>Model</th>{head}</tr></thead>\n"
        f"<tbody>{''.join(rows)}</tbody>\n</table></div>"
    )


def _curves(result: RunResult) -> str:
    best = result.best
    if best is None or not best.curves:
        return ""
    cards = []
    for key, curve in best.curves.items():
        caption = curve.label
        if curve.baseline is not None:
            caption += f" · no-skill baseline {curve.baseline:.3g}"
        cards.append(
            f'<div class="card"><h3>{escape(key.replace("_", " ").upper())}</h3>'
            f"{curve_svg(curve)}<p>{escape(caption)}</p></div>"
        )

    confusion = _confusion_card(best)
    if confusion:
        cards.append(confusion)
    return f'<h2>Curves — {escape(best.name)}</h2>\n<div class="grid">{"".join(cards)}</div>'


def _confusion_card(model: ModelResult) -> str:
    metrics = model.metrics
    if not isinstance(metrics, ClassificationMetrics) or not metrics.confusion:
        return ""
    labels = list(metrics.per_class) or [str(i) for i in range(len(metrics.confusion))]
    return (
        '<div class="card"><h3>CONFUSION</h3>'
        f"{confusion_svg(metrics.confusion, labels)}"
        "<p>Rows are true labels; shading is scaled per row so the minority row "
        "stays readable.</p></div>"
    )


def _calibration(result: RunResult) -> str:
    models = [m for m in result.models if m.calibration is not None]
    if not models:
        return ""
    cards = []
    for model in models[:3]:
        report = model.calibration
        verdict = (
            "Calibration improved the Brier score."
            if report.improved
            else "Calibration did not improve the Brier score — the raw probabilities "
            "were already at least as good."
        )
        cards.append(
            f'<div class="card"><h3>{escape(model.name.upper())} · {escape(report.method)}</h3>'
            f"{reliability_svg(report.curve_before, report.curve_after)}"
            f"<p>Brier {report.brier_before:.4g} → {report.brier_after:.4g} · "
            f"ECE {report.expected_calibration_error_before:.3g} → "
            f"{report.expected_calibration_error_after:.3g}. {escape(verdict)}</p></div>"
        )
    return (
        "<h2>Calibration</h2>\n"
        '<p class="note">Dashed grey is the model before calibration; the solid line is '
        "after. The diagonal is perfect. Calibration matters whenever a probability is "
        "multiplied by a cost rather than merely ranked.</p>\n"
        f'<div class="grid">{"".join(cards)}</div>'
    )


def _threshold(result: RunResult) -> str:
    model = next((m for m in result.models if m.threshold is not None), None)
    if model is None:
        return ""
    t = model.threshold
    sweep = bar_svg(
        [f"{th:.2f}" for th, _ in t.sweep[:12]],
        [cost for _, cost in t.sweep[:12]],
        title="Expected cost by threshold",
    )
    items = [
        ("Chosen threshold", f"{t.threshold:.4g}"),
        ("Expected cost", f"{t.expected_cost:,.4g}"),
        ("Cost at 0.5", f"{t.cost_at_default:,.4g}"),
        ("Saved", f"{t.savings_vs_default:,.4g}"),
        ("Flagged", f"{t.n_flagged:,}"),
        ("Precision / recall", f"{t.precision:.3g} / {t.recall:.3g}"),
    ]
    cells = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>" for label, value in items
    )
    # The caveat renders straight from the result rather than being written here,
    # so a report cannot quietly omit it: an in-sample threshold makes the
    # precision/recall above optimistic and the reader has to be told.
    caveat = t.selection_caveat
    caveat_html = f'\n<p class="note warn">{escape(caveat)}</p>' if caveat else ""
    return (
        "<h2>Decision threshold</h2>\n"
        f'<p class="note">False positive costs {t.cost_fp:,.4g}, false negative costs '
        f"{t.cost_fn:,.4g} — a {t.cost_ratio:.3g}× ratio. 0.5 is only the right cutoff "
        "when the two errors cost the same, which they almost never do.</p>\n"
        f'<dl class="meta">{cells}</dl>{caveat_html}\n'
        f'<div class="grid"><div class="card"><h3>COST SWEEP</h3>{sweep}'
        "<p>Expected cost across candidate thresholds.</p></div></div>"
    )


def _importance(result: RunResult) -> str:
    best = result.best
    if best is None:
        return ""
    pairs = _feature_importance(best)
    if not pairs:
        return ""
    labels = [name for name, _ in pairs]
    values = [value for _, value in pairs]
    return (
        "<h2>Feature importance</h2>\n"
        f'<p class="note">Top {len(pairs)} features of <strong>{escape(best.name)}</strong>. '
        "These are the model's internal weights, not causal effects — a feature can rank "
        "high because it leaks the outcome.</p>\n"
        f'<div class="grid"><div class="card">'
        f"{bar_svg(labels, values, title='Feature importance')}</div></div>"
    )


def _feature_importance(model: ModelResult) -> list[tuple[str, float]]:
    """Best-effort importance extraction. Returns `[]` rather than raising.

    Every branch here is defensive because the estimator zoo disagrees: trees
    expose `feature_importances_`, linear models expose `coef_` with a leading
    class axis under multiclass, and several expose neither.
    """
    try:
        estimator = model.estimator.named_steps.get("model")
        preprocess = model.estimator.named_steps.get("preprocess")
        if estimator is None or preprocess is None:
            return []

        values = getattr(estimator, "feature_importances_", None)
        if values is None:
            coef = getattr(estimator, "coef_", None)
            if coef is None:
                return []
            coef = np.asarray(coef)
            values = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef)
        values = np.asarray(values, dtype=float).ravel()

        try:
            names = [str(n) for n in preprocess.get_feature_names_out()]
        except Exception:
            names = [f"f{i}" for i in range(len(values))]

        if len(names) != len(values):
            names = [f"f{i}" for i in range(len(values))]

        order = np.argsort(values)[::-1][:12]
        return [(names[i], float(values[i])) for i in order]
    except Exception as exc:
        logger.debug("feature importance unavailable for %s: %s", model.name, exc)
        return []


def _data_quality(result: RunResult) -> str:
    """Everything the column inference and the run noticed that a reader should check.

    This is the panel the leakage reporter writes into. It is deliberately shown
    even when empty-ish, because "we looked and found nothing" and "we never
    looked" are different claims.
    """
    plan = result.column_plan
    notes: list[str] = []

    if plan.unused:
        reasons = ", ".join(
            f"<code>{escape(c)}</code> ({escape(plan.reasons.get(c, 'unused'))})"
            for c in plan.unused[:8]
        )
        notes.append(f"{len(plan.unused)} column(s) dropped before fitting: {reasons}.")
    if plan.high_cardinality:
        cols = ", ".join(f"<code>{escape(c)}</code>" for c in plan.high_cardinality[:8])
        notes.append(
            f"High-cardinality categorical(s): {cols}. One-hot encoding these inflates "
            "the feature space; consider target encoding fitted <em>inside</em> the fold."
        )
    missing = {c: f for c, f in plan.missing_fraction.items() if f > 0.2}
    if missing:
        cols = ", ".join(
            f"<code>{escape(c)}</code> ({f:.0%})" for c, f in list(missing.items())[:8]
        )
        notes.append(f"Columns more than 20% missing: {cols}.")
    if result.split_plan is not None and result.split_plan.kind in ("stratified", "kfold"):
        notes.append(
            "No group or time structure was declared. If rows share an entity or arrive "
            "in time order, a random split scores the model on rows it effectively saw."
        )
    if result.class_balance:
        total = sum(result.class_balance.values()) or 1
        share = min(result.class_balance.values()) / total
        if share < 0.1:
            notes.append(
                f"Minority class is {share:.1%} of rows. Read PR-AUC, not ROC-AUC — "
                "ROC's false-positive rate is divided by the majority count, which makes "
                "it look flattering at exactly the prevalence where it is least useful."
            )

    if not notes:
        notes.append("Nothing flagged by column inference or the split plan.")

    items = "".join(f"<li>{n}</li>" for n in notes)
    return f'<h2>Data quality</h2>\n<ul class="plain">{items}</ul>'


def _skipped(result: RunResult) -> str:
    if not result.skipped:
        return ""
    items = "".join(
        f"<li><code>{escape(name)}</code> — {escape(reason)}</li>"
        for name, reason in result.skipped.items()
    )
    return (
        "<h2>Not run</h2>\n"
        '<p class="note">These models were skipped. A missing optional dependency is '
        "expected; anything else is worth reading.</p>\n"
        f'<ul class="plain">{items}</ul>'
    )


def _headline(model: ModelResult) -> tuple[str, float]:
    metrics = model.metrics
    if isinstance(metrics, ClassificationMetrics):
        name, value = metrics.headline(imbalanced=True)
        return (METRIC_LABELS.get(name, name), value if value is not None else metrics.f1)
    if isinstance(metrics, RegressionMetrics):
        return ("R²", metrics.r2)
    if isinstance(metrics, ClusteringMetrics):
        return (
            "Silhouette",
            metrics.silhouette if metrics.silhouette is not None else float("nan"),
        )
    return ("score", float("nan"))


def _fmt(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if isinstance(value, bool):
        return "yes" if value else ""
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.4g}"
    return escape(str(value))
