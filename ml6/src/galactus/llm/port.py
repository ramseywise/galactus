"""The provider-agnostic LLM interface.

One method. `complete_structured(prompt, schema) -> dict` is everything the
generation pipeline asks of a provider, and the narrowness is the point: a port
wide enough to express streaming, tool use, and multi-turn state would be a
second orchestration framework, and swapping it would be a rewrite rather than a
new class.

Provider-agnostic, deliberately not orchestration-agnostic. Swapping Anthropic
for another provider means writing one adapter with one method. Swapping the
*pipeline* is not a goal — the DAG lives in function composition, and an
abstraction that anticipated a different one would be speculative.

Implementations must return a JSON object matching `schema`, or raise
`LLMError`. Returning a partial or malformed draft is not an error path the
caller handles specially: the deterministic validator rejects it like any other
non-conforming draft, and the repair loop takes over.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class LLMError(RuntimeError):
    """A provider call failed in a way the caller cannot repair by re-prompting.

    Distinct from a contract violation. A draft that comes back too long is a
    normal outcome the repair loop handles; a 401, a connection reset, or a
    refusal is not, and stops generation.
    """


@runtime_checkable
class LLM(Protocol):
    """A provider that can return schema-shaped JSON for a prompt.

    A Protocol rather than an ABC so the fake adapter in the test suite is a
    plain class with the right method — no import from this module, no
    inheritance, no registration.
    """

    async def complete_structured(
        self, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a JSON object conforming to `schema`.

        Args:
            prompt: The full instruction, including the layout limits. Schema
                constraints alone do not bind the model (see
                `generate.schema_for`), so the limits must be stated in prose
                here too.
            schema: A JSON Schema describing the object to return.

        Raises:
            LLMError: If the provider call fails or returns unusable output.
        """
        ...
