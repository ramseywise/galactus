"""The run record schema — code, data, execution, and outcome, kept as four
independent groups rather than one flat bag of fields.

Two decisions are load-bearing:

**Metrics are a flat `name -> value` map plus a declared `headline_metric`,
not a typed dataclass.** This registry is shared by ML (whose headline is
PR-AUC under imbalance) and AI evals (whose headline is a contract-pass
rate) — a typed metrics dataclass would force one consumer's vocabulary
onto the other. `headline_metric` must name a key that is actually present
in `metrics`, enforced below, which is what keeps a hardcoded assumption
like "the headline is always average_precision" from re-entering through
the back door.

**Optional fields take a value or an explicit `NotApplicable` sentinel,
never a bare `None`.** A scripted AI-eval adapter has no seed to record; a
classification run always does. Both are legitimate — but a `None` seed on
a classification run would mean something different (it should have been
recorded and wasn't) than a `None` seed on an eval run (there is nothing to
record). Collapsing both to `None` is precisely the bug this schema exists
to prevent: the WALKTHROUGH's `brier`/`getattr` failure was a missing
number and an uncomputed one looking identical in a report. See
`NotApplicable` below.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NotApplicable:
    """This field has no meaning for this run kind — distinct from 'not recorded'.

    A `RunRecord` field typed `X | NotApplicable` must always be one or the
    other; a bare `None` is never a valid value for such a field (enforced at
    the call sites that construct these groups, e.g. `provenance.py`, and at
    `RunRecord.__post_init__` for the fields declared there). The reason is
    the brier/getattr bug: a missing number and an inapplicable one must not
    look identical once written to disk.
    """

    reason: str


@dataclass(frozen=True)
class CodeState:
    """What code produced this run.

    `git_sha` and `versions` are both `NotApplicable`-able: a run outside
    version control has no SHA to record, and a scoring-relevant library
    that is not installed has no version to record. Both are recordable
    absences, not failures.
    """

    git_sha: str | NotApplicable
    dirty: bool
    versions: dict[str, str]


@dataclass(frozen=True)
class DataIdentity:
    """Which frame this run was scored on — the acceptance test's subject.

    `frame_hash` covers the frame *as fitted*, after every derivation drop —
    never the source file. A source-file hash is byte-identical across two
    runs whose derivation diverged, and would not answer "which frame was
    the baseline scored on" (see `fingerprint.py`). `columns` is ordered:
    reordering columns is itself a derivation change and must change the
    hash.
    """

    frame_hash: str
    n_rows: int
    n_cols: int
    columns: tuple[str, ...]
    source_hash: str | NotApplicable = field(
        default_factory=lambda: NotApplicable(
            "source-file hash was not supplied; frame_hash is the record of record"
        )
    )
    """An optional extra, never a substitute. Per F4: a hash of the source
    file would have been identical across the Step 15 runs and caught
    nothing, so `frame_hash` alone is what the acceptance test relies on."""


@dataclass(frozen=True)
class ExecutionConfig:
    """What produced the numbers, beyond the code and the data.

    `seed` and `folds` are optional-with-a-reason: the AI eval harness has
    no seed and no split concept (F7), so those runs pass a `NotApplicable`
    rather than a `None` that would read as "forgot to record it".
    `resolved_config` is the post-CLI-parse, post-default-merge values —
    not just the CLI args — because module-level constants that never
    appear on a command line are exactly what diverged in Step 15.
    """

    seed: int | NotApplicable
    resolved_config: dict[str, object]
    folds: str | NotApplicable
    """A description of the fold *plan* (e.g. `SplitPlan` projected to its
    serializable fields), never per-row fold indices — recording indices
    would be recording an identifier per row, which the aggregates-only
    constraint forbids."""

    def __post_init__(self) -> None:
        # Type hints are not enforced at runtime, and a bare `None` is the
        # exact failure this schema exists to rule out: it would silently
        # pass through and read as "not applicable" on reload. Reject it
        # explicitly rather than relying on the annotation alone.
        if self.seed is None:
            raise ValueError(
                "seed=None is not a valid value — pass a seed, or "
                "NotApplicable(reason=...) if this run kind has no seed "
                "concept. A bare None is indistinguishable from 'forgot to "
                "record it' once written to disk."
            )
        if self.folds is None:
            raise ValueError(
                "folds=None is not a valid value — pass a fold-plan "
                "description, or NotApplicable(reason=...) if this run kind "
                "has no split concept. A bare None is indistinguishable from "
                "'forgot to record it' once written to disk."
            )


@dataclass(frozen=True)
class RunRecord:
    """One run, fully described: enough to re-execute to the same numbers,
    or to name precisely which recorded input changed."""

    code: CodeState
    data: DataIdentity
    execution: ExecutionConfig
    metrics: dict[str, float]
    headline_metric: str
    run_kind: str
    """"classification" | "eval" | ... — which adapter produced this record."""

    def __post_init__(self) -> None:
        if self.headline_metric not in self.metrics:
            raise ValueError(
                f"headline_metric {self.headline_metric!r} is not in metrics "
                f"{sorted(self.metrics)} — a headline that names a metric the "
                "record does not carry is unrankable."
            )
