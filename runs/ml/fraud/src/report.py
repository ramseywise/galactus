"""Report surface for the fraud proving run — the floor and the refusal are unmissable.

`ml.reporting.html.write_report` (AIT-67) has no concept of a prevalence floor or a
sufficiency refusal — it renders whatever `ModelRun.threshold` is, and on this frame that
is `None` for every model, which its own "Operating point" section already states plainly
("No costs were supplied, so no operating point was chosen."). That sentence is true but
under-informative: it reads like a caller forgot an argument, not like the toolkit
inspected the evidence and declined on purpose. This module is a poc-local wrapper — not a
change to AIT-67 (out of scope; the toolkit's report has no `SufficiencyVerdict` to render
because that concept does not exist upstream) — that calls `write_report` and then injects
two blocks via string post-processing: a refusal banner ahead of the model table, using
the toolkit's own `.verdict.null` style so it reads as the loudest element on the page, and
a floor annotation stating what a PR-AUC actually means on an imbalanced frame like this
one. Aggregates only, same discipline as `html.py`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

FLOOR_NOTE = (
    "PR-AUC's no-skill floor is the positive-class prevalence, here <strong>{prevalence:.4f}</strong> "
    "&mdash; not 0.5. A PR-AUC of {best_pr_auc:.4f} on this frame is {multiple:.1f}x chance, not "
    "'poor but working'. (For contrast, the lending poc's floor was 0.2056.)"
)

REFUSAL_BANNER = (
    "<div class='verdict null'><strong>No operating point is reported.</strong> "
    "The thinnest test fold holds {min_pos} positive case(s) ({n_pos} across the frame, "
    "{prevalence:.2%}). A cost-minimising threshold over that many events is arithmetic, "
    "not evidence. Discrimination metrics below are reported with their floor; "
    "precision, recall, and expected cost are withheld.</div>"
)


def _floor_note(summary: dict[str, Any]) -> str:
    prevalence = summary["prevalence_floor"]
    pr_aucs = [m["pr_auc"] for m in summary["models"] if m.get("pr_auc") is not None]
    best_pr_auc = max(pr_aucs) if pr_aucs else prevalence
    multiple = (best_pr_auc / prevalence) if prevalence else 0.0
    return FLOOR_NOTE.format(prevalence=prevalence, best_pr_auc=best_pr_auc, multiple=multiple)


def _refusal_banner(summary: dict[str, Any]) -> str:
    refusal = summary["refusal"]
    return REFUSAL_BANNER.format(
        min_pos=refusal["min_positives_in_fold"],
        n_pos=refusal["n_positives"],
        prevalence=summary["prevalence_floor"],
    )


class ReportAnchorError(RuntimeError):
    """An injection anchor was not found in the toolkit's report.

    Raised rather than skipped. Every injection below carries something the reader needs
    in order to read the numbers correctly — the refusal, the floor, the fairness note —
    so an injection that silently no-ops produces a report that looks complete and is not.
    That is the same failure this poc exists to refuse, one layer up: a confident-looking
    artefact with the caveat quietly missing.

    The anchors are `ml.reporting.html`'s markup, which is upstream, unpinned, and free to
    change. They *will* drift. This exception is what makes the drift loud; `test_report.py`
    pins each anchor against a real `write_report` document so the drift is caught in CI
    rather than in a report someone is already reading.
    """


def _replace_once(document: str, marker: str, replacement: str, *, what: str) -> str:
    """Literal single replacement that raises when the marker is absent."""
    if marker not in document:
        raise ReportAnchorError(
            f"cannot inject {what}: anchor {marker!r} is not in the report. "
            "ml.reporting.html's markup has changed — update the anchor in report.py."
        )
    return document.replace(marker, replacement, 1)


def _sub_once(document: str, pattern: str, replacement: str, *, what: str) -> str:
    """Single regex substitution that raises when the pattern does not match."""
    document, n = re.subn(pattern, replacement, document, count=1, flags=re.DOTALL)
    if n == 0:
        raise ReportAnchorError(
            f"cannot inject {what}: pattern {pattern!r} did not match the report. "
            "ml.reporting.html's markup has changed — update the anchor in report.py."
        )
    return document


def _inject_refusal_banner(document: str, summary: dict[str, Any]) -> str:
    """Place the refusal banner immediately before the model comparison table, so it is
    the first thing a reader sees after the section heading — ahead of any metric."""
    if summary["refusal"]["operating_point_reported"]:
        return document
    marker = "<h2>Model comparison</h2>"
    return _replace_once(
        document, marker, f"{marker}\n{_refusal_banner(summary)}", what="the refusal banner"
    )


def _inject_floor_note(document: str, summary: dict[str, Any]) -> str:
    """State the prevalence floor in the run-facts block and relabel the PR-AUC column
    header so the number can't be read as an absolute score."""
    floor = summary["prevalence_floor"]
    note = _floor_note(summary)

    # Run-facts block: append a floor fact to the <dl class="meta"> definition list.
    document = _sub_once(
        document,
        r'(<dl class="meta">.*?)(</dl>)',
        rf"\1<div><dt>PR-AUC floor</dt><dd>{floor:.4f} (positive-class prevalence)</dd></div>\2",
        what="the PR-AUC floor fact",
    )

    # PR-AUC column header: state what chance is, right in the header cell.
    document = _replace_once(
        document,
        "<th>PR-AUC</th>",
        f"<th>PR-AUC (floor {floor:.4f})</th>",
        what="the PR-AUC column header floor",
    )

    # Floor note as its own paragraph directly under the model comparison table. Anchored
    # from the heading so it lands under the *model* table and not some later one.
    document = _sub_once(
        document,
        r"(<h2>Model comparison</h2>.*?</tbody>\s*</table></div>)",
        rf"\1\n<p class='meta'>{note}</p>",
        what="the prevalence floor note",
    )
    return document


def _inject_fairness_notes(document: str, summary: dict[str, Any]) -> str:
    """Render the fairness notes (age, raw) as their own section, ahead of </body>."""
    notes = summary.get("fairness_notes") or []
    if not notes:
        return document
    items = "".join(f"<li>{note}</li>" for note in notes)
    section = f"<h2>Fairness notes</h2><ul>{items}</ul>"
    return _replace_once(
        document, "</body>", f"{section}\n</body>", what="the fairness notes section"
    )


def write_fraud_report(
    result: Any,
    summary: dict[str, Any],
    path: str | Path,
    *,
    title: str = "ml/fraud proving run",
) -> Path:
    """Write the toolkit's report, then inject the refusal banner, floor annotation, and
    fairness notes that AIT-67's generic report has no vocabulary for.

    `summary` is the same dict `run.py`'s `summarise()` produces — this function reads it
    rather than `result` for anything sufficiency-shaped, since `SufficiencyVerdict` is a
    poc-local concept the toolkit's `ModelRun` does not carry.
    """
    from ml.reporting.html import write_report

    out = write_report(result, path, title=title)
    document = out.read_text(encoding="utf-8")
    document = _inject_refusal_banner(document, summary)
    document = _inject_floor_note(document, summary)
    document = _inject_fairness_notes(document, summary)
    out.write_text(document, encoding="utf-8")
    return out
