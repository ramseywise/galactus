"""Minimal, honest Anthropic client helpers for a timeboxed build.

Copy this file (and its tests) into any Python project. It depends on the
stdlib plus ``anthropic`` and nothing else — no settings module, no framework,
no scaffold. That is the point: it has to work in the first ten minutes of a
60-minute exercise, where a copier render has not happened and will not.

Every function here exists to make one failure mode visible instead of silent.
See README.md for the clock, the trade-off template, and why this file
deliberately duplicates concepts from the scaffold's ``observability/`` tree.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic

log = logging.getLogger("llm_kit")

MODEL = "claude-opus-5"

# $ per 1M tokens, (input, output). Extend as needed; cost_of() is loud about
# models it does not know rather than quietly reporting $0.00.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_TOKENS = 4096


# --------------------------------------------------------------------------
# client
# --------------------------------------------------------------------------


def _client(
    timeout: float = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> anthropic.Anthropic:
    """Build a client with an explicit timeout and retry budget.

    The SDK already retries connection errors and 408/409/429/5xx with
    exponential backoff. Do NOT wrap calls to this client in your own retry
    loop — you would multiply the attempts, not add resilience.

    Worst-case wall clock for a single call is ``timeout * (max_retries + 1)``.
    With the defaults that is 30s * 3 = 90s. Pick numbers you can defend
    against your own deadline; the defaults are tuned for an interactive
    timebox, not for a batch job.

    Credentials come from the environment (``ANTHROPIC_API_KEY`` and the SDK's
    other credential sources). An unset ``ANTHROPIC_API_KEY`` does not
    guarantee construction fails — the SDK falls through to other sources — so
    never use key-absence as a test fixture.
    """
    return anthropic.Anthropic(timeout=timeout, max_retries=max_retries)


# --------------------------------------------------------------------------
# calling
# --------------------------------------------------------------------------


def call(
    prompt: str,
    *,
    system: str | None = None,
    model: str = MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: Any = None,
    **kwargs: Any,
) -> Any:
    """One turn. Returns the raw ``Message`` — not a string.

    Returning the raw response is deliberate: callers need ``usage`` and
    ``stop_reason`` as much as they need the text, and a helper that returns
    only ``str`` throws both away. Use :func:`text_of` to extract text.

    Note there is no ``temperature`` parameter. Claude Opus 5 and the other
    thinking-by-default models reject ``temperature``/``top_p``/``top_k`` with
    a 400. Pass one via ``**kwargs`` only if you know your model accepts it.
    """
    client = client or _client()
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system is not None:
        params["system"] = system
    params.update(kwargs)

    response = client.messages.create(**params)

    usage = usage_of(response)
    log.info(
        "llm_kit.call",
        extra={
            "model": model,
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "stop_reason": getattr(response, "stop_reason", None),
        },
    )
    return response


def parsed(
    prompt: str,
    output_format: Any,
    *,
    system: str | None = None,
    model: str = MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    client: Any = None,
    **kwargs: Any,
) -> Any:
    """Structured output. ``output_format`` is a Pydantic model class.

    Returns ``response.parsed_output`` — the validated object, not the raw
    message. If you need ``usage`` alongside it, call ``client.messages.parse``
    yourself; this helper optimizes for the common case of wanting the data.

    ``pydantic`` arrives transitively with ``anthropic``, so this adds no
    dependency. Use the raw ``output_config={"format": {"type": "json_schema",
    "schema": {...}}}`` form on :func:`call` if you would rather hand-write a
    JSON Schema dict and skip Pydantic entirely.
    """
    client = client or _client()
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "output_format": output_format,
    }
    if system is not None:
        params["system"] = system
    params.update(kwargs)

    response = client.messages.parse(**params)
    log.info(
        "llm_kit.parsed",
        extra={"model": model, "stop_reason": getattr(response, "stop_reason", None)},
    )
    return response.parsed_output


# --------------------------------------------------------------------------
# reading the response
# --------------------------------------------------------------------------


def text_of(response: Any) -> str:
    """First text block, or ``""`` — but never silently.

    Two things go wrong here and both are invisible if you just iterate for a
    text block and fall off the end:

    * ``stop_reason == "max_tokens"`` — you got a truncated answer. It may look
      complete. Raise ``max_tokens`` or shorten the prompt.
    * no text block at all — the turn was tool use, a refusal, or empty. An
      empty string flowing downstream reads as "the model had nothing to say".

    Both are logged at WARNING. If your caller can meaningfully recover, check
    ``response.stop_reason`` yourself rather than reading the log.
    """
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "max_tokens":
        log.warning(
            "llm_kit.truncated",
            extra={"stop_reason": stop_reason, "hint": "raise max_tokens"},
        )
    if stop_reason == "refusal":
        log.warning(
            "llm_kit.refusal",
            extra={"stop_details": getattr(response, "stop_details", None)},
        )

    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "text":
            return block.text

    log.warning(
        "llm_kit.no_text_block",
        extra={"stop_reason": stop_reason, "returning": ""},
    )
    return ""


def usage_of(response: Any) -> dict[str, int]:
    """Token counts as a plain dict, cache fields included when present."""
    usage = getattr(response, "usage", None)
    if usage is None:
        log.warning("llm_kit.no_usage", extra={"returning": "{}"})
        return {}

    out = {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }
    for field in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        value = getattr(usage, field, None)
        if value:
            out[field] = value
    return out


def cost_of(response: Any, model: str = MODEL) -> float:
    """USD for one response. Cache reads are billed as input here.

    This is an estimate for steering a timebox, not an invoice. It ignores
    cache-write premiums and batch discounts; if the number matters to a
    decision, check the console.
    """
    if model not in PRICES:
        log.warning(
            "llm_kit.unknown_model_price",
            extra={"model": model, "returning": 0.0},
        )
        return 0.0

    price_in, price_out = PRICES[model]
    usage = usage_of(response)
    billed_in = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
    billed_out = usage.get("output_tokens", 0)
    return (billed_in * price_in + billed_out * price_out) / 1_000_000


# --------------------------------------------------------------------------
# budgeting
# --------------------------------------------------------------------------


def guard_tokens(
    prompt: str,
    *,
    limit: int,
    system: str | None = None,
    model: str = MODEL,
    client: Any = None,
) -> int:
    """Count input tokens before spending them. Raises if over ``limit``.

    Uses ``client.messages.count_tokens()`` — the only correct counter for
    Claude. Do not reach for ``tiktoken``: it is an OpenAI tokenizer and
    undercounts Claude by roughly 15-20% on prose and worse on code, which is
    exactly the direction that turns a "safe" prompt into a 400.

    Counts are model-specific, so this passes the same ``model`` you will use
    for inference.
    """
    client = client or _client()
    params: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system is not None:
        params["system"] = system

    count = client.messages.count_tokens(**params).input_tokens
    if count > limit:
        log.warning(
            "llm_kit.over_budget",
            extra={"input_tokens": count, "limit": limit, "model": model},
        )
        raise ValueError(f"prompt is {count} input tokens, limit is {limit}")

    log.info("llm_kit.token_check", extra={"input_tokens": count, "limit": limit})
    return count


__all__ = [
    "MODEL",
    "PRICES",
    "call",
    "cost_of",
    "guard_tokens",
    "parsed",
    "text_of",
    "usage_of",
]


if __name__ == "__main__":  # pragma: no cover - smoke check, costs one call
    logging.basicConfig(level=logging.INFO)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("set ANTHROPIC_API_KEY to run the smoke check")
    reply = call("Reply with the single word: ready")
    print(text_of(reply))
    print(f"cost ~${cost_of(reply):.6f}  usage={usage_of(reply)}")
