"""The `Proposer` seam: one page in, one `PageResult` out, never an exception for a model
failure. An SDK error, refusal, schema mismatch or truncated body is `not_run` with a
reason (spec F2), so a failed page is never read as a page with nothing to say."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from kg.contract import Pack
from kg.models import PageResult, Usage
from kg.profile import Page


class ProposerError(RuntimeError):
    """A provider failure inside an adapter; the adapter maps it to `not_run`."""


@runtime_checkable
class Proposer(Protocol):
    name: str
    last_usage: Usage | None
    """Usage of the most recent `propose` call, for the runtime meter (A7)."""

    async def propose(self, page: Page, pack: Pack) -> PageResult: ...
