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
    blocked: bool = False
