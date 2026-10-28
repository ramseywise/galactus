"""Provider-agnostic ports for the generation harness.

Two Protocols, each narrow on purpose:

``LLM`` is the provider a producer calls to generate structured content.
``FieldSpec`` is the five attributes the scripted dry-run adapter needs to
know about a contract field — nothing about the contract's domain, its
prompt, or how it is validated.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable


class LLMError(RuntimeError):
    """A provider call failed in a way the caller cannot repair by re-prompting.

    Distinct from a contract violation. An output that comes back too long is
    a normal outcome the repair loop handles; a 401, a connection reset, or a
    refusal is not, and stops generation.
    """


@runtime_checkable
class LLM(Protocol):
    """A provider that can return schema-shaped JSON for a prompt.

    A Protocol rather than an ABC so the scripted dry-run adapter is a plain
    class with the right method — no import from this module, no
    inheritance, no registration.
    """

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object conforming to `schema`.

        Args:
            prompt: The full instruction, including any output limits. Schema
                constraints alone rarely bind a model — the limits must be
                stated in prose too.
            schema: A JSON Schema describing the object to return.

        Raises:
            LLMError: If the provider call fails or returns unusable output.
        """
        ...


FieldKind = Literal["text", "image_placeholder", "color_ref"]


@runtime_checkable
class FieldSpec(Protocol):
    """The five attributes a contract field needs for the scripted adapter to
    fake a plausible value for it.

    Deliberately narrow: this is not a general contract-field type, it is the
    exact surface `ScriptedProvider._value_for` touches. A concrete contract
    type (e.g. a Pydantic model) satisfies this by structural typing — no
    inheritance required.
    """

    name: str
    kind: FieldKind
    max_words: int | None
    min_words: int | None
    max_chars: int | None
