"""The `JudgeSeat` seam. The judge is blind: it sees the candidate and a ±400-char window
of the normalised body, never the proposer's reasoning."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kg.models import Candidate, NotRun, Verdict

WINDOW_CHARS = 400


def window(body: str, span: tuple[int, int], chars: int = WINDOW_CHARS) -> str:
    start, end = span
    return body[max(0, start - chars) : end + chars]


@runtime_checkable
class JudgeSeat(Protocol):
    name: str

    async def judge(self, candidate: Candidate, window: str) -> Verdict | NotRun: ...
    def available(self) -> tuple[bool, str]: ...  # (ok, reason-if-not)
