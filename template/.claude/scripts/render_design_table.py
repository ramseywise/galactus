"""Regenerate DESIGN.md's Key Decisions table from design.yaml.

The table between the ``design-table`` markers in DESIGN.md is a *view* of
design.yaml, not a source of truth. This script re-renders that view and
replaces ONLY the bytes between the two markers; every other byte of DESIGN.md
— the human-owned prose, the human-owned decision rows below the region — is
preserved exactly.

Run by copier's ``_migrations`` on every ``copier update``. Also safe to run by
hand after editing design.yaml. Idempotent: re-running with unchanged
design.yaml rewrites the identical bytes and reports no change.

Defensive by design — this touches a human-owned file, so every failure mode
(missing file, missing markers, unparseable yaml, markers out of order) warns
and exits 0 rather than modifying anything.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BEGIN = "<!-- BEGIN design-table (generated from design.yaml — do not edit by hand) -->"
END = "<!-- END design-table -->"

HEADER = "| Decision | Status | Choice | Rationale |\n|----------|--------|--------|-----------|\n"


def _get(data: dict[str, Any], path: str, fallback: Any = None) -> Any:
    """Read a dotted path out of nested dicts, returning fallback if absent."""
    node: Any = data
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return fallback
        node = node[key]
    return node


# design.yaml names frameworks by product (`langgraph`); the genesis-time table
# renders copier's answer name for the same choice (`lg_agent`). Map to the
# copier spelling so a `copier update` reproduces the genesis bytes rather than
# showing a spurious one-line diff on the first run.
_FRAMEWORK_LABELS = {"langgraph": "lg_agent", "adk": "adk_agent"}


def _backend_cell(enabled: bool, framework: Any) -> str:
    """Render one backend row's Choice cell."""
    if not enabled:
        return "no"
    name = str(framework or "none")
    if name == "none":
        return "yes — no agent loop"
    return f"yes — {_FRAMEWORK_LABELS.get(name, name)}"


def render_table(design: dict[str, Any], project_type: str) -> str:
    """Build the marker-region table body from a parsed design.yaml."""
    py_enabled = bool(_get(design, "backends.python.enabled", False))
    py_framework = _get(design, "backends.python.framework", "none")
    ts_enabled = bool(_get(design, "backends.typescript.enabled", False))
    ts_framework = _get(design, "backends.typescript.framework", "none")
    py_caps = _get(design, "backends.python.capabilities") or []
    web_enabled = bool(_get(design, "web.enabled", False))

    topology = "split_service" if (web_enabled and py_enabled) else "single"
    retrieval = (
        f"{_get(design, 'rag.backend', 'none')} / {_get(design, 'rag.vector_store', 'none')}"
        if "rag" in py_caps
        else "none"
    )
    interaction = _get(design, "evals.interaction") or []

    rows = [
        (
            "AI approach",
            project_type,
            "Set at scaffold time — revisit if the shape changes",
        ),
        (
            "Python backend",
            _backend_cell(py_enabled, py_framework),
            "From `design.yaml` `backends.python`",
        ),
        (
            "TypeScript backend",
            _backend_cell(ts_enabled, ts_framework),
            "From `design.yaml` `backends.typescript`",
        ),
        (
            "Frontend",
            f"nextjs ({topology})" if web_enabled else "none",
            "From `design.yaml` `web`",
        ),
        ("Retrieval", retrieval, "From `design.yaml` `rag`"),
        ("Cloud", str(_get(design, "cloud", "none")), "From `design.yaml` `cloud`"),
        (
            "Deployment target",
            str(_get(design, "deployment_target", "local")),
            "From `design.yaml` `deployment_target`",
        ),
        (
            "Data sensitivity",
            str(_get(design, "data_sensitivity", "internal")),
            "From `design.yaml` `data_sensitivity`",
        ),
        (
            "Interaction evals",
            ", ".join(str(m) for m in interaction) if interaction else "none",
            "From `design.yaml` `evals.interaction`",
        ),
    ]
    body = "".join(f"| {name} | Resolved | {choice} | {why} |\n" for name, choice, why in rows)
    return HEADER + body


def replace_region(text: str, table: str) -> str | None:
    """Swap the text between the markers. None if the region isn't well-formed."""
    start = text.find(BEGIN)
    end = text.find(END)
    if start == -1 or end == -1:
        logger.warning(
            "DESIGN.md has no design-table markers — leaving it untouched. "
            "To restore the generated table, re-add the BEGIN/END design-table "
            "comment pair around the Key Decisions table."
        )
        return None
    if end < start:
        logger.warning(
            "DESIGN.md's design-table END marker precedes its BEGIN marker — "
            "leaving it untouched. Fix the marker order by hand."
        )
        return None
    return text[: start + len(BEGIN)] + "\n" + table + text[end:]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[design-table] %(message)s")

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    design_path = root / "design.yaml"
    doc_path = root / "DESIGN.md"

    if not design_path.is_file() or not doc_path.is_file():
        # Pre-design.yaml project, or DESIGN.md deleted — nothing to sync.
        return 0

    try:
        import yaml
    except ImportError:
        logger.warning(
            "PyYAML unavailable — cannot regenerate the DESIGN.md decisions table. "
            "Install PyYAML and re-run: python scripts/render_design_table.py"
        )
        return 0

    try:
        design = yaml.safe_load(design_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning("design.yaml is not valid YAML (%s) — DESIGN.md left untouched.", exc)
        return 0
    if not isinstance(design, dict):
        logger.warning("design.yaml did not parse to a mapping — DESIGN.md left untouched.")
        return 0

    # Decisions only take effect once /gate-check marks discovery complete —
    # the same gate copier's question defaults use. Before that the table
    # reflects genesis seeds and must not be rewritten from placeholder values.
    if _get(design, "stages.discovery") != "complete":
        logger.info("discovery stage is not complete — DESIGN.md table left as seeded.")
        return 0

    original = doc_path.read_text(encoding="utf-8")
    project_type = _get(design, "project_type", "—")
    updated = replace_region(original, render_table(design, str(project_type)))
    if updated is None:
        return 0
    if updated == original:
        logger.info("DESIGN.md decisions table already matches design.yaml.")
        return 0

    doc_path.write_text(updated, encoding="utf-8")
    logger.info("regenerated DESIGN.md decisions table from design.yaml.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
