"""`JevSeat`: a second `JudgeSeat`, backed by the Jev decision model on OpenRouter.

UNVERIFIED API SHAPE. The endpoint, the request body and the response field below were
written without network access or a key, from the plan, not from live docs. They are pinned
by `tests/test_kg_judge_jev.py` (`REQUEST_SHAPE`), so a drift between this file and the
documented API shows up as a deliberate test edit, not a silent change. Check them against
the live docs before the first paid call.

Request (JSON POST, `Authorization: Bearer <OPENROUTER_API_KEY>`):

    {"model": "typesafe/jev-1.13", "question_type": "noul",
     "input": {"subject", "subject_type", "relation", "object", "object_type", "quote",
               "evidence": <the +-400-char window>}}

Response: a JSON object with a numeric `probability` that the claim is supported.

Failure mapping follows `ClaudeSeat` (A5): every failure to answer is a `NotRun` with a
distinct reason prefix, never a `Verdict` and never `unclear`. A probability outside [0, 1]
is a `schema_mismatch` `NotRun`, never clamped or rescaled (fog FA-003); `Verdict` would
raise on it, and the adapter reports it instead so one bad response cannot crash a build.
"""

from __future__ import annotations

import math
from typing import Any

import httpx
from pydantic import ValidationError

from kg.config import Settings
from kg.models import Candidate, NotRun, Usage, Verdict

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MODEL = "typesafe/jev-1.13"
QUESTION_TYPE = "noul"
THRESHOLD = 0.5
"""p >= THRESHOLD is `supported`, else `not_supported`. Jev never says `unclear`."""
TIMEOUT_S = 60.0


def build_body(candidate: Candidate, window: str) -> dict[str, Any]:
    """The request body. Blind like the Claude prompt: candidate and window only."""
    return {
        "model": MODEL,
        "question_type": QUESTION_TYPE,
        "input": {
            "subject": candidate.subject,
            "subject_type": candidate.subject_type,
            "relation": candidate.relation,
            "object": candidate.object,
            "object_type": candidate.object_type,
            "quote": candidate.quote,
            "evidence": window,
        },
    }


class JevSeat:
    name = "jev"

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """`client` is an injected `httpx.AsyncClient` (a `MockTransport` in tests)."""
        self._settings = settings if settings is not None else Settings.load(use_dotenv=False)
        self._client = client
        self.model = MODEL
        self.calls = 0

    def available(self) -> tuple[bool, str]:
        if not self._settings.openrouter_api_key:
            return False, "OPENROUTER_API_KEY not set"
        return True, ""

    async def judge(self, candidate: Candidate, window: str) -> Verdict | NotRun:
        ok, why = self.available()
        if not ok:
            return NotRun(reason=f"unavailable: {why}")
        usage = Usage(model=MODEL)
        headers = {"Authorization": f"Bearer {self._settings.require_openrouter_key()}"}
        self.calls += 1
        try:
            if self._client is not None:
                resp = await self._client.post(
                    ENDPOINT, json=build_body(candidate, window), headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                    resp = await client.post(
                        ENDPOINT, json=build_body(candidate, window), headers=headers
                    )
        except httpx.HTTPError as exc:
            return NotRun(reason=f"http_error: {type(exc).__name__}")
        if not resp.is_success:
            return NotRun(reason=f"http_error: status {resp.status_code}")

        try:
            data = resp.json()
        except ValueError:
            return NotRun(reason="schema_mismatch: response was not valid JSON", usage=usage)
        p = data.get("probability") if isinstance(data, dict) else None
        if isinstance(p, bool) or not isinstance(p, int | float):
            return NotRun(
                reason="schema_mismatch: response has no numeric `probability`", usage=usage
            )
        if math.isnan(p) or not 0.0 <= p <= 1.0:
            return NotRun(
                reason=f"schema_mismatch: probability out of range [0, 1]: {p!r}", usage=usage
            )
        label = "supported" if p >= THRESHOLD else "not_supported"
        try:
            return Verdict(label=label, score=float(p), usage=usage)
        except ValidationError:  # unreachable after the range check; fail as NotRun anyway
            return NotRun(reason="schema_mismatch: invalid verdict", usage=usage)
