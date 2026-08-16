"""The one fake provider the whole suite scripts against.

Satisfies `model.gateway.LLM` structurally — no inheritance, which is the point
of the Protocol. One class rather than a hand-rolled fake per test module: the
port's contract (signature, the `images` channel, the vision-schema convention)
lives in exactly one place, so a port change breaks one fake loudly instead of
three quietly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from model.gateway import LLMError

DEFAULT_VISION_FACTS = ["A table row states 96.2 percent."]


class ScriptedLLM:
    """Returns scripted drafts for generation calls and facts for vision calls.

    One fake serves both pipeline stages because both go through the same port.
    The vision schema is the one with a `facts` key, which is enough to tell
    them apart without threading a mode flag through.

    Drafts are returned in order; the last repeats if the repair loop asks for
    more than were scripted, so a test that scripts one bad draft gets a loop
    that keeps failing rather than an IndexError. Every call's prompt, schema,
    and images are recorded for assertions.
    """

    def __init__(
        self,
        responses: list[dict[str, Any]] | None = None,
        *,
        vision_facts: list[str] | None = None,
        error: bool = False,
    ) -> None:
        self.responses = list(responses or [])
        self.vision_facts = DEFAULT_VISION_FACTS if vision_facts is None else list(vision_facts)
        self.error = error
        self.prompts: list[str] = []
        self.schemas: list[dict[str, Any]] = []
        self.images: list[tuple[bytes, ...]] = []
        self.draft_calls = 0
        self.vision_calls = 0

    @property
    def calls(self) -> int:
        return len(self.prompts)

    @property
    def call_count(self) -> int:
        return len(self.prompts)

    async def complete_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        images: Sequence[bytes] = (),
    ) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        self.images.append(tuple(images))

        if self.error:
            raise LLMError("provider unavailable")

        if "facts" in schema.get("properties", {}):
            self.vision_calls += 1
            return {"facts": list(self.vision_facts)}

        if not self.responses:
            raise AssertionError("ScriptedLLM got a draft call but no responses were scripted")
        index = min(self.draft_calls, len(self.responses) - 1)
        self.draft_calls += 1
        return dict(self.responses[index])
