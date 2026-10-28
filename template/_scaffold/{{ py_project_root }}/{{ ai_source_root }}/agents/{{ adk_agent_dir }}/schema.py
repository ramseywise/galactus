"""Shared output schema for the support assistant. Every agent turn must
produce an AssistantResponse regardless of which sub-agent served it."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str = Field(description="Article or page title.")
    url: str = Field(description="Full URL to the knowledge base article.")


class AssistantResponse(BaseModel):
    message: str = Field(
        description="Main response content as markdown. Never include raw JSON here."
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="2-4 suggested follow-up questions shown as chips.",
    )
    sources: list[Source] = Field(
        default_factory=list,
        description="Knowledge base articles cited in this response.",
    )
    contact_support: bool = Field(
        default=False,
        description="True when the question is out of scope or needs human follow-up.",
    )
