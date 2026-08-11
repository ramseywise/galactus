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


def _inject_refusal_banner(document: str, summary: dict[str, Any]) -> str:
    """Place the refusal banner immediately before the model comparison table, so it is
    the first thing a reader sees after the section heading — ahead of any metric."""
    if not summary["refusal"]["operating_point_reported"]:
        banner = _refusal_banner(summary)
        marker = "<h2>Model comparison</h2>"
        document = document.replace(marker, f"{marker}\n{banner}", 1)
    return document


def _inject_floor_note(document: str, summary: dict[str, Any]) -> str:
    """State the prevalence floor in the run-facts block and relabel the PR-AUC column
    header so the number can't be read as an absolute score."""
    floor = summary["prevalence_floor"]
    note = _floor_note(summary)

    # Run-facts block: append a floor fact row right after the class-balance row.
    document = re.sub(
        r"(<tr><th>class balance</th><td>[^<]*</td></tr>)",
        rf"\1<tr><th>PR-AUC floor</th><td>{floor:.4f} (positive-class prevalence)</td></tr>",
        document,
        count=1,
    )

    # PR-AUC column header: state what chance is, right in the header cell.
    document = document.replace(
        "<th>PR-AUC</th>",
        f"<th>PR-AUC (floor {floor:.4f})</th>",
        1,
    )

    # Floor note as its own paragraph directly under the model comparison table.
    document = re.sub(
        r"(<table><thead><tr><th>model</th><th>PR-AUC[^\n]*</tbody></table>)",
        rf"\1<p class='meta'>{note}</p>",
        document,
        count=1,
    )
    return document


def _inject_fairness_notes(document: str, summary: dict[str, Any]) -> str:
    """Render the fairness notes (age, raw) as their own section, ahead of </body>."""
    notes = summary.get("fairness_notes") or []
    if not notes:
        return document
    items = "".join(f"<li>{note}</li>" for note in notes)
    section = f"<h2>Fairness notes</h2><ul>{items}</ul>"
    return document.replace("</body></html>", f"{section}\n</body></html>", 1)


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
