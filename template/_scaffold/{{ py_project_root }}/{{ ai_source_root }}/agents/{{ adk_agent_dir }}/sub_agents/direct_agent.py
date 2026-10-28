"""Direct sub-agent — answers from model knowledge without retrieval. Baseline for comparison."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import Agent
from google.genai import types

from ..schema import AssistantResponse

_INSTRUCTION = (Path(__file__).parent.parent / "prompts" / "direct_agent.txt").read_text()


direct_agent = Agent(
    model="gemini-2.5-flash",
    name="direct_agent",
    description=(
        "Answers questions directly from model knowledge, without retrieval. "
        "Use for simple conversational follow-up or general knowledge questions."
    ),
    static_instruction=types.Content(role="user", parts=[types.Part(text=_INSTRUCTION)]),
    output_schema=AssistantResponse,
    output_key="response",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.4,
        max_output_tokens=1024,
    ),
)
