"""Records that flow from proposer to gates to judge to store.

`NotApplicable` is re-exported from `experiments.record` so a metric with no denominator
is the same type in the store, the router and the conformance record (fog FA-002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from experiments.record import NotApplicable as NotApplicable
from kg.profile.normalise import norm_surface


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Candidate(_Strict):
    """One triple as the proposer emitted it, before any gate."""

    subject: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    object: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class Mention(_Strict):
    surface: str = Field(min_length=1)
    entity_type: str = Field(min_length=1)
    page_path: str = Field(min_length=1)

    @property
    def norm(self) -> str:
        return norm_surface(self.surface)


class Evidence(_Strict):
    quote: str = Field(min_length=1)
    span: tuple[int, int]
    page_path: str = Field(min_length=1)

    @model_validator(mode="after")
    def _span_matches_quote(self) -> Evidence:
        start, end = self.span
        if not 0 <= start < end or end - start != len(self.quote):
            raise ValueError(f"span {self.span} does not fit a quote of {len(self.quote)} chars")
        return self


TripleKey = tuple[str, str, str, str]


def canonical_key(subject: str, relation: str, obj: str, page_path: str) -> TripleKey:
    """Dedupe key and store write key: `(subject_norm, relation, object_norm, page_path)`."""
    return (norm_surface(subject), relation, norm_surface(obj), page_path)


class Triple(_Strict):
    subject: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    object: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    page_path: str = Field(min_length=1)

    @classmethod
    def from_candidate(cls, c: Candidate, page_path: str) -> Triple:
        return cls(
            subject=c.subject,
            subject_type=c.subject_type,
            relation=c.relation,
            object=c.object,
            object_type=c.object_type,
            page_path=page_path,
        )

    @property
    def key(self) -> TripleKey:
        return canonical_key(self.subject, self.relation, self.object, self.page_path)


Tier = Literal["accept", "review", "reject"]
"""Router outcome for a judged triple. Only `accept` is served by default."""

ALL_TIERS: frozenset[Tier] = frozenset({"accept", "review", "reject"})
ACCEPT_ONLY: frozenset[Tier] = frozenset({"accept"})

SeatLabel = Literal["supported", "not_supported", "unclear"]


class Judgement(_Strict):
    """One seat's verdict on one triple, as stored."""

    seat: str = Field(min_length=1)
    label: SeatLabel
    score: float = Field(ge=0.0, le=1.0)
    model: str | None = None


PageStatus = Literal["proposed", "no_candidates", "not_run"]


class PageResult(_Strict):
    """What the proposer produced for one page. `not_run` is never read as `no_candidates`."""

    page_path: str = Field(min_length=1)
    status: PageStatus
    reason: str | None = None
    candidates: tuple[Candidate, ...] = ()

    @model_validator(mode="after")
    def _status_is_consistent(self) -> PageResult:
        if self.status == "not_run" and not self.reason:
            raise ValueError("a not_run page must say why")
        if self.status == "not_run" and self.candidates:
            raise ValueError("a not_run page has no candidates")
        if self.status == "no_candidates" and self.candidates:
            raise ValueError("status no_candidates with candidates present")
        if self.status == "proposed" and not self.candidates:
            raise ValueError("status proposed with no candidates; use no_candidates")
        return self


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str | None
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class GateReport:
    """The gate results for one candidate, in the order they ran."""

    candidate: Candidate
    page_path: str
    results: dict[str, GateResult] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(r.passed for r in self.results.values())

    @property
    def failed(self) -> dict[str, str | None]:
        return {name: r.reason for name, r in self.results.items() if not r.passed}

    def evidence(self) -> Evidence:
        span = self.results["verbatim"].span if "verbatim" in self.results else None
        if not self.passed or span is None:
            raise ValueError("evidence exists only for a candidate that passed every gate")
        return Evidence(quote=self.candidate.quote, span=span, page_path=self.page_path)


# -- model seams (A5): shared by the proposer, every judge seat, the router and the meter --


class Usage(_Strict):
    """Metered tokens for one model call. Zero for scripted fakes."""

    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)


class Verdict(_Strict):
    """A seat that answered. `score` outside [0, 1] raises, never clamps (fog FA-003):
    a seat returning 85.0 or a 0–10 rating must fail loudly, not route to accept.
    `unclear` means the judge answered and could not decide; it routes to `review`."""

    label: SeatLabel
    score: float = Field(ge=0.0, le=1.0)
    usage: Usage


class NotRun(_Strict):
    """A seat that did not answer: SDK/HTTP error, schema mismatch, refusal, truncation.
    Never a verdict and never `unclear` (fog FA-002, FA-013)."""

    reason: str = Field(min_length=1)
    usage: Usage | None = None
