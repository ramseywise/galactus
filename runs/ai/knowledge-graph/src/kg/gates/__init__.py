"""The four pure gates every candidate passes before the judge sees it."""

from __future__ import annotations

from kg.contract import Pack
from kg.gates import attested, quote_verbatim, schema_conform
from kg.gates.dedupe import DedupeResult, dedupe
from kg.gates.quote_verbatim import MIN_QUOTE_CHARS
from kg.models import Candidate, GateReport


def run_gates(candidate: Candidate, body: str, pack: Pack, page_path: str) -> GateReport:
    """Run verbatim, attested and schema-conform on one candidate; every gate reports.

    Dedupe runs afterwards over the survivors of a page, via `dedupe`.
    """
    return GateReport(
        candidate=candidate,
        page_path=page_path,
        results={
            "verbatim": quote_verbatim.check(candidate, body),
            "attested": attested.check(candidate),
            "schema": schema_conform.check(candidate, pack),
        },
    )


__all__ = ["MIN_QUOTE_CHARS", "DedupeResult", "dedupe", "run_gates"]
