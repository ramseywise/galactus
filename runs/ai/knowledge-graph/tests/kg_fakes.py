"""The scripted model seams the whole suite runs against.

`ScriptedProposer` and `ScriptedSeat` satisfy the `Proposer` and `JudgeSeat` Protocols
structurally. One fake per seam, so a port change breaks one class loudly instead of
several hand-rolled fakes quietly.

Named `kg_fakes`, not `fakes`: marketing-comms' tests import a bare `fakes` module from
the same pytest session, and two top-level modules with one name shadow each other.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from kg.contract import Pack
from kg.models import Candidate, NotRun, PageResult, Usage, Verdict
from kg.profile import Page

SCRIPTED = Usage(model="scripted")


class ScriptedProposer:
    """Returns a scripted `PageResult` per page path; unscripted pages get `no_candidates`.

    `script` maps page path -> list of candidates, or a `PageResult` to return verbatim
    (e.g. a `not_run`). `default` overrides what an unscripted page returns.
    """

    name = "scripted"

    def __init__(
        self,
        script: Mapping[str, list[Candidate] | PageResult] | None = None,
        *,
        default: Callable[[Page], PageResult] | None = None,
    ) -> None:
        self.script = dict(script or {})
        self.default = default
        self.calls: list[str] = []
        self.last_usage: Usage | None = None

    async def propose(self, page: Page, pack: Pack) -> PageResult:
        self.calls.append(page.path)
        self.last_usage = SCRIPTED
        got = self.script.get(page.path)
        if isinstance(got, PageResult):
            return got
        if got:
            return PageResult(page_path=page.path, status="proposed", candidates=tuple(got))
        if self.default is not None:
            return self.default(page)
        return PageResult(page_path=page.path, status="no_candidates")


class ScriptedSeat:
    """Judges by a function of the candidate (default: supported, score 0.9).

    `rule` returns a `Verdict`, a `NotRun`, or a `(label, score)` pair.
    """

    def __init__(
        self,
        rule: Callable[[Candidate, str], Verdict | NotRun | tuple[str, float]] | None = None,
        *,
        name: str = "scripted",
        available: tuple[bool, str] = (True, ""),
    ) -> None:
        self.name = name
        self.rule = rule or (lambda c, w: ("supported", 0.9))
        self._available = available
        self.calls: list[tuple[Candidate, str]] = []

    async def judge(self, candidate: Candidate, window: str) -> Verdict | NotRun:
        self.calls.append((candidate, window))
        out = self.rule(candidate, window)
        if isinstance(out, Verdict | NotRun):
            return out
        label, score = out
        return Verdict(label=label, score=score, usage=SCRIPTED)  # type: ignore[arg-type]

    def available(self) -> tuple[bool, str]:
        return self._available
