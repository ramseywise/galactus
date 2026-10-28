"""Local embedding model — no API key required. Same model for indexing and
query-time retrieval, so vectors are directly comparable."""

from __future__ import annotations

import contextlib
import io
import logging
import threading
from functools import lru_cache
from typing import Any

from langchain_core.embeddings import Embeddings

from agents.rag_agent.settings import settings

log = logging.getLogger(__name__)

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, Any] = {}


def _load_sentence_transformer(model_name: str, revision: str | None) -> Any:
    """Load and cache a SentenceTransformer model process-wide."""
    key = f"{model_name}@{revision or 'default'}"
    with _MODEL_LOCK:
        if key not in _MODEL_CACHE:
            from sentence_transformers import SentenceTransformer

            for noisy in ("sentence_transformers", "transformers", "huggingface_hub"):
                logging.getLogger(noisy).setLevel(logging.ERROR)

            log.info("loading embedding model: %s", model_name)
            kwargs: dict[str, Any] = {"revision": revision} if revision else {}
            with contextlib.redirect_stdout(io.StringIO()):
                _MODEL_CACHE[key] = SentenceTransformer(model_name, **kwargs)
        return _MODEL_CACHE[key]


class _LocalEmbeddings(Embeddings):
    """LangChain-compatible wrapper around a local SentenceTransformer model."""

    def __init__(self, model_name: str, revision: str | None) -> None:
        self._model_name = model_name
        self._revision = revision or None

    def _model(self) -> Any:
        return _load_sentence_transformer(self._model_name, self._revision)

    def embed_query(self, text: str) -> list[float]:
        vec = self._model().encode(text, normalize_embeddings=True, show_progress_bar=False)
        return vec.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()


@lru_cache(maxsize=1)
def get_embeddings() -> _LocalEmbeddings:
    return _LocalEmbeddings(settings.embedding_model, settings.embedding_model_revision)
