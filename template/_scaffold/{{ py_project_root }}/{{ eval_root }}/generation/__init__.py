"""Generation-under-contract eval harness — a third eval kind alongside
graders/ (retrieval golden-QA) and interaction grading (heuristic/judges).

Where those two grade already-produced artifacts against a golden answer,
this harness drives a producer itself: generate -> validate -> repair -> N ->
fallback, and measures the process, not just the outcome. Four case-agnostic
regions live here — result types, metrics, reporting, and the dry-run
scripted-adapter machinery — extracted from a real case study
(``ai-marketing-comms/evals/run.py`` in the galactus repo) so a project that
needs this shape does not have to invent it from scratch.

See the eval root's ``CLAUDE.md`` for the full directory-layout rationale.
"""

from __future__ import annotations
