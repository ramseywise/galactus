"""Generation node — also guard layer 3, the output filter.

`check_output` runs on the model's text before it becomes `state["answer"]`,
which is what the caller receives. Non-streaming, so layer 3 is the simple
case here: the whole answer exists before anything is returned. (The
TypeScript twin streams, and pays for that with a carry-window transform —
see guardrails/guards.py's AIT-50 decision block.)

Tool results are filtered by layer 2 at `retrieve_node` for retrieval and here
for MCP tool output, before either re-enters the prompt.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.tools import BaseTool

from context_budget.context_budget import compact_history, should_compact, track_usage
from guardrails.guards import check_output, filter_content
from observability.spans import chat_span, execute_tool_span, record_finish_reason

from ..model.gateway import agenerate, get_client
from ..model.mcp import get_mcp_tools
from ..settings import settings
from ..stall_detector import StallDetectedError, StallDetector
from ..state import State

_SYSTEM_PROMPT = """You are a support assistant answering questions using the provided \
context articles and any tools available to you. If neither the context nor a tool \
call can answer the question, say so plainly instead of guessing. Be concise.

Context:
{context}
"""

# Safety valve against a tool-call loop that never converges — not a quality target.
_MAX_TOOL_TURNS = 4


def _to_anthropic_tool(tool: BaseTool) -> dict:
    # langchain-mcp-adapters sets args_schema to the tool's raw JSON schema dict
    # (MCP tools are JSON-schema-native) rather than a pydantic model — pass it
    # through directly instead of calling a pydantic method that isn't there.
    if isinstance(tool.args_schema, dict):
        schema = tool.args_schema
    else:
        schema = {"type": "object", "properties": tool.args}
    return {"name": tool.name, "description": tool.description or "", "input_schema": schema}


async def generate_node(state: State) -> dict:
    if state.get("blocked", False):
        return {"answer": state.get("block_reason", "")}

    context_snippets = state.get("context_snippets", [])
    context = "\n\n---\n\n".join(context_snippets) or "(no matching articles found)"
    system_prompt = _SYSTEM_PROMPT.format(context=context)

    mcp_tools = await get_mcp_tools()
    tools_by_name = {tool.name: tool for tool in mcp_tools}
    anthropic_tools = [_to_anthropic_tool(tool) for tool in mcp_tools]

    messages: list[dict[str, Any]] = [{"role": "user", "content": state["message"]}]
    stall = StallDetector()

    for _ in range(_MAX_TOOL_TURNS):
        with chat_span(model=settings.lg_model) as _span:
            response = await agenerate(system_prompt, messages, tools=anthropic_tools)
            # Set real token counts inside the with-block so the span is still
            # open. Dedenting past the with exits start_as_current_span, which
            # ends the span — set_attribute on an ended span is a no-op in the
            # OTel Python SDK. _span is None when OTel is unavailable.
            if _span is not None:
                _span.set_attribute("gen_ai.usage.input_tokens", response.usage.input_tokens)
                _span.set_attribute("gen_ai.usage.output_tokens", response.usage.output_tokens)
            # Not span.set_attribute — record_finish_reason also arms chat_span's
            # truncation warning, and it must run even when _span is None.
            record_finish_reason(_span, response.stop_reason)

        track_usage(response)
        if should_compact(response):
            # compact_history calls client.messages.create synchronously; run in a
            # thread pool so the blocking call does not stall the async event loop.
            messages = await asyncio.to_thread(
                compact_history, messages, get_client(), model=settings.lg_model
            )

        # Record the assistant's text on every turn so repeated identical outputs
        # across turns accumulate toward the stall threshold.
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            stall.record_output(text)
        except StallDetectedError as exc:
            return {"answer": f"Stall detected in LLM output: {exc}"}

        if response.stop_reason != "tool_use":
            # Guard layer 3 -- scrub before the answer leaves the graph. .text is
            # the safe value either way, so the verdict needs no branch here.
            return {"answer": check_output(text).text}

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool = tools_by_name.get(block.name)
            if tool is None:
                result_text = f"Unknown tool: {block.name}"
            else:
                try:
                    stall.record_tool_call(block.name, block.input)
                    with execute_tool_span(tool_name=block.name, inputs=block.input):
                        result_text = str(await tool.ainvoke(block.input))
                except StallDetectedError as exc:
                    return {"answer": f"Stall detected in tool loop: {exc}"}
                except Exception as exc:
                    result_text = f"Tool error: {exc}"
            # Guard layer 2 -- an MCP tool reaches servers this graph does not
            # own, so its result is untrusted text about to re-enter the prompt.
            result_text = filter_content(result_text, source=f"tool:{block.name}").text
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
            )
        messages.append({"role": "user", "content": tool_results})

    return {"answer": "Reached max tool-call turns without a final answer."}
