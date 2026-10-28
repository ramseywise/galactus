from __future__ import annotations

from pydantic import BaseModel


class Article(BaseModel):
    id: str
    title: str
    text: str
    category: str = "general"
    source_path: str


class SearchResult(BaseModel):
    id: str
    title: str
    text: str
    category: str
    score: float
