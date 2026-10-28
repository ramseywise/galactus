from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    id: str
    title: str
    score: float


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str


class ChatResponse(BaseModel):
    message: str
    sources: list[Source] = Field(default_factory=list)
    confidence: float = 0.0


class RetrievalRequest(BaseModel):
    thread_id: str
    query: str = Field(min_length=1, max_length=2000)


class RetrievalResponse(BaseModel):
    """Documents + confidence only — no answer synthesis.

    Mirrors playground's real integration point: a caller (an MCP tool, another
    agent) that wants retrieved context to synthesize its own answer rather than
    getting one back pre-written.
    """

    sources: list[Source] = Field(default_factory=list)
    context: str = ""
    confidence: float = 0.0
