"""RAG sub-agent — retrieval-grounded answers via ADK's native MCPToolset,
pointed at this project's own MCP server (mcp_servers/<slug>), which in turn
calls the standalone rag_agent HTTP service's /api/v1/retrieval endpoint.

This is the ADK-side half of the same MCP integration the LangGraph chat agent demonstrates
via langchain-mcp-adapters — same server, two frameworks' native client tools."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import Agent
from google.genai import types

from ..callbacks import before_model_rag
from ..mcp_tools import get_mcp_toolset
from ..schema import AssistantResponse

_INSTRUCTION = (Path(__file__).parent.parent / "prompts" / "rag_agent.txt").read_text()

_toolset = get_mcp_toolset()

rag_agent = Agent(
    model="gemini-2.5-flash",
    name="rag_agent",
    description=(
        "Answers knowledge-base questions by searching the project's documentation. "
        "Requires rag_agent (`make rag-up`) and the MCP server to be running."
    ),
    static_instruction=types.Content(role="user", parts=[types.Part(text=_INSTRUCTION)]),
    output_schema=AssistantResponse,
    output_key="response",
    tools=[_toolset] if _toolset is not None else [],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2048,
    ),
    before_model_callback=before_model_rag,
)
