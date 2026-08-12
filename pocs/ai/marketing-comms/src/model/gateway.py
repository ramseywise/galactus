"""The provider boundary: the interface and the one real implementation.

`LLM` is the provider-agnostic port. `complete_structured(prompt, schema) -> dict`
is everything the generation pipeline asks of a provider, and the narrowness is
the point: a port wide enough to express streaming, tool use, and multi-turn
state would be a second orchestration framework, and swapping it would be a
rewrite rather than a new class.

Provider-agnostic, deliberately not orchestration-agnostic. Swapping Anthropic
for another provider means writing one adapter with one method. Swapping the
*pipeline* is not a goal — the DAG lives in function composition, and an
abstraction that anticipated a different one would be speculative.

Implementations must return a JSON object matching `schema`, or raise
`LLMError`. Returning a partial or malformed draft is not an error path the
caller handles specially: the deterministic validator rejects it like any other
non-conforming draft, and the repair loop takes over.

`AnthropicAdapter` is the one real implementation. Everything Anthropic-specific
is confined below: the client, the model id, the structured-output request
shape, and the SDK's exception hierarchy. The pipeline sees only
`complete_structured`. Two SDK details drive its shape:

1. Structured outputs go in `output_config={"format": {...}}`. The older
   top-level `output_format` parameter is deprecated.
2. Sampling parameters (`temperature`, `top_p`, `top_k`) are rejected outright
   by current models. Determinism is not available as a knob, which is the
   deeper reason the layout contract is enforced by code rather than by asking
   the model nicely.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from galactus.config import Settings


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

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
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


MAX_TOKENS = 8000
"""Ceiling for a single collateral draft.

The largest template totals well under 2000 words across all fields, so this is
roughly 4x headroom. Sized generously on purpose: a `max_tokens` cut produces a
truncated JSON object that fails to parse, which surfaces as an `LLMError`
rather than as a repairable violation.
"""


class AnthropicAdapter:
    """Calls the Anthropic Messages API with a constrained output schema.

    The client is constructed lazily so that importing this module — which the
    API layer does at startup — never requires a credential. Only an actual
    generation call does.
    """

    def __init__(self, settings: Settings | None = None, client: Any = None) -> None:
        """
        Args:
            settings: Resolved configuration. Loaded from the environment when
                omitted.
            client: A pre-built `AsyncAnthropic`. Injected by tests that want to
                exercise this adapter's response handling without a network
                call; production leaves it None.
        """
        self._settings = settings if settings is not None else Settings.load()
        self._client = client

    @property
    def model(self) -> str:
        return self._settings.model

    def _get_client(self) -> Any:
        """Build the async client on first use, gated on the API key."""
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._settings.require_api_key())
        return self._client

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object conforming to `schema`. See `port.LLM`."""
        import anthropic

        client = self._get_client()

        try:
            response = await client.messages.create(
                model=self._settings.model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        # Most specific first. Matching on exception classes rather than on
        # message text, which is not part of the SDK's contract.
        except anthropic.NotFoundError as exc:
            raise LLMError(
                f"model {self._settings.model!r} not found or not available to this account"
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("rate limited by the Anthropic API") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API returned status {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("could not reach the Anthropic API") from exc

        return _extract_json(response)


def _extract_json(response: Any) -> dict[str, Any]:
    """Pull the JSON object out of a Messages response.

    `stop_reason` is checked before the content is read. A refusal means the
    output is not schema-shaped even though the request asked for it, and a
    `max_tokens` stop means the JSON is very likely truncated — both are worth
    distinguishing from a plain parse failure, because the fix differs.
    """
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        raise LLMError("model declined to produce output for this prompt")
    if stop_reason == "max_tokens":
        raise LLMError(f"response hit the {MAX_TOKENS}-token ceiling and is incomplete")

    blocks = getattr(response, "content", None) or []
    text = "".join(block.text for block in blocks if getattr(block, "type", None) == "text")
    if not text.strip():
        raise LLMError("response contained no text content")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMError(f"expected a JSON object, got {type(parsed).__name__}")

    return parsed
