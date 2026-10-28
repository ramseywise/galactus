"""The human-readable run report — the four numbers over the case table."""

from __future__ import annotations

from typing import Any

from .results import CaseResult


def summarize_table(rows: list[dict[str, Any]]) -> str:
    """Render a list of dicts as a compact markdown table.

    Adapted from `cap-genai.md`'s `shared_tools.py` (copied, not imported —
    that module executes registry decorators on import). See docs/cap-reuse.md.
    """
    if not rows:
        return "_no rows_"

    headers = list(rows[0])
    widths = {h: max(len(h), *(len(str(row.get(h, ""))) for row in rows)) for h in headers}

    def line(values: list[str]) -> str:
        return (
            "| "
            + " | ".join(v.ljust(widths[h]) for h, v in zip(headers, values, strict=True))
            + " |"
        )

    out = [
        line(headers),
        "|" + "|".join("-" * (widths[h] + 2) for h in headers) + "|",
    ]
    out += [line([str(row.get(h, "")) for h in headers]) for row in rows]
    return "\n".join(out)


def format_report(results: list[CaseResult], metrics: dict[str, Any]) -> str:
    """The human-readable run summary — the four numbers over the case table."""
    rows = [
        {
            "case_id": r.case_id,
            "difficulty": r.difficulty,
            "first_pass": "yes" if r.first_pass_valid else "no",
            "repairs": r.repair_attempts,
            "fallback": "yes" if r.used_fallback else "no",
            "grounded": "yes" if r.grounded else "no",
            "valid": "yes" if r.contract_valid else "NO",
            "calls": r.llm_calls,
        }
        for r in results
    ]

    convergence = metrics["repair_convergence"]
    lines = [
        summarize_table(rows),
        "",
        f"Cases:                {metrics['cases']}",
        f"Contract pass rate:   {metrics['contract_pass_rate']}%  (valid on first generation)",
        (
            f"Repair convergence:   {convergence if convergence is not None else 'n/a'}"
            "  (mean attempts, converged cases)"
        ),
        f"Fallback rate:        {metrics['fallback_rate']}%  (deterministic truncation)",
        f"Grounding rate:       {metrics['grounding_rate']}%  (traceable to a source text)",
        "",
        f"Contract valid after repair+fallback: {metrics['contract_valid_rate']}%",
        f"Total provider calls: {metrics['total_llm_calls']}",
    ]

    errored = [r for r in results if r.error]
    if errored:
        lines += ["", "Errors:"] + [f"  {r.case_id}: {r.error}" for r in errored]

    return "\n".join(lines)
