"""Typed contracts at every stage boundary — the seams that make per-stage
testing possible.

A stage function whose signature is `(DataFrame) -> DataFrame` has no contract
and cannot be tested at its boundary; it can only be tested as part of whatever
pipeline calls it. That is how a stage-layered tree collapses back into one
monolithic script. Each model here is produced by one stage and consumed by
another (see `~/.claude/refs/naming.md` §3), so the boundary is checkable
without running the stages either side of it.

Two type choices carry a lesson rather than a preference:

- `ColumnPlan.excluded` is `dict[str, str]` (column -> reason), never a bare
  list. A column dropped without a recorded reason is a silent drop, which is
  the failure a proving run surfaced; the type makes it unrepresentable.
- `RunConfig.parked` carries each unresolved question *with its trigger*, so an
  unknown cost ratio or horizon travels with the config into every report that
  cites it instead of living only in a markdown doc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Family = Literal["classification", "clustering", "prediction"]
Output = Literal["binary", "multiclass", "unsupervised", "continuous"]
SplitKind = Literal["stratified_kfold", "group_kfold", "time_series", "holdout"]


class _Base(BaseModel):
    """Frozen and extra-forbidding: a stage contract that silently accepts an
    unknown key is not a contract. `frozen` also means a downstream stage cannot
    mutate an upstream stage's output in place."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ── ingest/ ──────────────────────────────────────────────────────────────────


class ColumnContract(_Base):
    """One column's declared expectation, checked at ingest."""

    name: str
    dtype: str
    """Pandas dtype string the column must be coercible to (e.g. "float64")."""
    nullable: bool = True
    max_null_fraction: float = Field(default=1.0, ge=0.0, le=1.0)
    """Ingest fails when the observed null fraction exceeds this."""


class DataContract(_Base):
    """Produced by `ingest/`, consumed by `transform/`. The declared shape of the
    frame — checked, not assumed."""

    columns: tuple[ColumnContract, ...]
    target: str | None = None
    min_rows: int = Field(default=1, ge=0)
    """Row-count gate: fewer rows than this is a broken extract, not a small one."""

    @model_validator(mode="after")
    def _target_is_declared(self) -> DataContract:
        if self.target is not None and self.target not in {c.name for c in self.columns}:
            raise ValueError(
                f"target {self.target!r} is not among the declared columns "
                f"{sorted(c.name for c in self.columns)}"
            )
        return self


# ── transform/ ───────────────────────────────────────────────────────────────


class ColumnPlan(_Base):
    """Produced by `transform/`, consumed by `training/`. Which columns are
    features, of what kind, and — for anything dropped — why."""

    numeric: tuple[str, ...] = ()
    categorical: tuple[str, ...] = ()
    ordinal: tuple[str, ...] = ()
    high_cardinality: tuple[str, ...] = ()
    excluded: dict[str, str] = Field(default_factory=dict)
    """column -> reason. A bare list would let a silent drop through."""

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self.numeric + self.categorical + self.ordinal + self.high_cardinality

    @model_validator(mode="after")
    def _no_column_in_two_buckets(self) -> ColumnPlan:
        names = list(self.feature_names)
        duplicated = sorted({n for n in names if names.count(n) > 1})
        if duplicated:
            raise ValueError(f"column(s) {duplicated} appear in more than one bucket")
        overlap = sorted(set(names) & set(self.excluded))
        if overlap:
            raise ValueError(f"column(s) {overlap} are both a feature and excluded")
        return self


# ── features/ ────────────────────────────────────────────────────────────────


class FeatureSpec(_Base):
    """Produced by `features/`, consumed by `training/`. One derived feature and
    the columns it is built from."""

    name: str
    source_columns: tuple[str, ...]
    kind: str
    """How it is derived — "ratio", "aggregate", "interaction", "lag", ..."""
    fitted_in_fold: bool = True
    """False only for a stateless transform (no learned parameter). Anything with
    a learned parameter must be fitted per fold — see naming.md §3 rule 3."""


# ── evaluation/ ──────────────────────────────────────────────────────────────


class SplitSpec(_Base):
    """Produced by `evaluation/`, consumed by `training/`. The split plan and the
    reason for it — a split choice without a reason cannot be reviewed."""

    kind: SplitKind
    reason: str
    n_splits: int = Field(default=5, ge=2)
    group_col: str | None = None
    time_col: str | None = None
    shuffle: bool = True

    @model_validator(mode="after")
    def _kind_has_its_column(self) -> SplitSpec:
        if self.kind == "group_kfold" and not self.group_col:
            raise ValueError("kind='group_kfold' requires group_col")
        if self.kind == "time_series" and not self.time_col:
            raise ValueError("kind='time_series' requires time_col")
        return self


class MetricValue(_Base):
    """One metric, with the spread across folds — not just the mean. A mean alone
    hides a model that is excellent on four folds and broken on the fifth."""

    name: str
    mean: float
    std: float = Field(default=0.0, ge=0.0)
    per_fold: tuple[float, ...] = ()
    in_sample: bool = False
    """True marks a value measured on the rows it was fitted on — the caller
    should not have to know to add that caveat."""


# ── the interview (/ml-select) ───────────────────────────────────────────────


class ParkedQuestion(_Base):
    """An unresolved question that travels with the config, plus the event that
    should un-park it. A parked question with no trigger is just a note."""

    question: str
    trigger: str
    parked_on: str | None = None


class RunConfig(_Base):
    """Produced by the interview, consumed by `training/`. The run's identity:
    what is being modelled, on what, with which candidates."""

    family: Family
    output: Output
    target: str
    models: tuple[str, ...] = ()
    """Empty means "every available candidate for (family, output)"."""
    sampling: Literal["none", "undersample", "oversample", "smote"] = "none"
    seed: int = 42
    parked: tuple[ParkedQuestion, ...] = ()

    @model_validator(mode="after")
    def _output_matches_family(self) -> RunConfig:
        allowed: dict[str, set[str]] = {
            "classification": {"binary", "multiclass"},
            "clustering": {"unsupervised"},
            "prediction": {"continuous"},
        }
        if self.output not in allowed[self.family]:
            raise ValueError(
                f"output={self.output!r} is not valid for family={self.family!r} "
                f"(valid: {sorted(allowed[self.family])})"
            )
        return self


# ── training/ ────────────────────────────────────────────────────────────────


class ModelReport(_Base):
    """Produced by `training/`, consumed by `evaluation/` and `reporting/`.

    Deliberately carries no threshold: choosing one consumes costs, which are a
    business input, not a model output (naming.md §3 rule 2)."""

    model_name: str
    metrics: tuple[MetricValue, ...]
    split: SplitSpec
    fit_seconds: float = Field(default=0.0, ge=0.0)
    n_features: int = Field(default=0, ge=0)
    fitted_in_fold: bool = True
    """The no-fit-outside-fold claim, carried so a reader need not trust it."""
    failed_with: str | None = None
    """Set when the candidate did not fit. A candidate that vanishes from the
    table with no recorded reason is the catboost failure mode."""
    baseline_delta: float | None = None
    beats_baseline: bool | None = None
    """None when no baseline was available — distinct from False."""

    def metric(self, name: str) -> MetricValue | None:
        return next((m for m in self.metrics if m.name == name), None)


# ── calibration/ ─────────────────────────────────────────────────────────────


class OperatingPoint(_Base):
    """One threshold and what it buys — precision/recall/coverage at that cut."""

    threshold: float = Field(ge=0.0, le=1.0)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    """Fraction of the population flagged at this threshold."""
    expected_cost: float | None = None
    in_sample: bool = True
    """Defaults True: a threshold chosen on the same rows it is scored on is the
    common case and the one that needs the caveat."""


class ThresholdPolicy(_Base):
    """Produced by `calibration/`, consumed by `api/`. The operating point(s) the
    service will actually run at."""

    method: Literal["none", "sigmoid", "isotonic"] = "none"
    brier_before: float | None = None
    brier_after: float | None = None
    points: tuple[OperatingPoint, ...] = ()
    selected: OperatingPoint | None = None
    cost_fp: float | None = None
    cost_fn: float | None = None

    @model_validator(mode="after")
    def _selected_is_offered(self) -> ThresholdPolicy:
        if self.selected is not None and self.points and self.selected not in self.points:
            raise ValueError("selected operating point is not among points")
        return self


# ── monitoring/ ──────────────────────────────────────────────────────────────


class FeatureDrift(_Base):
    """Drift for one feature between a reference and a current window."""

    feature: str
    statistic: float
    method: Literal["psi", "ks", "chi2", "wasserstein"] = "psi"
    drifted: bool = False


class DriftReport(_Base):
    """Produced by `monitoring/`, consumed by `reporting/`."""

    features: tuple[FeatureDrift, ...] = ()
    reference_rows: int = Field(default=0, ge=0)
    current_rows: int = Field(default=0, ge=0)
    generated_at: datetime | None = None
    train_serve_skew: dict[str, Any] = Field(default_factory=dict)

    @property
    def drifted_features(self) -> tuple[str, ...]:
        return tuple(f.feature for f in self.features if f.drifted)
