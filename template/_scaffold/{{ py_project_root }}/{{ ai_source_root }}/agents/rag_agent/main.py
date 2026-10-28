from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from langchain_core.runnables import RunnableConfig

from agents.rag_agent.graph import build_graph
from agents.rag_agent.nodes.retrieve import retrieve_node
from agents.rag_agent.schema import ChatRequest, ChatResponse, RetrievalRequest, RetrievalResponse
from agents.rag_agent.settings import settings

_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    if not Path(settings.rag_vectordb_path).exists():
        print(
            f"Warning: {settings.rag_vectordb_path} does not exist yet — "
            "run `make rag-corpus-ingest` before sending requests."
        )
    _graph = build_graph()
    yield


app = FastAPI(title="rag_agent", lifespan=lifespan)

try:
    from integrations.n8n_webhook import router as n8n_webhook_router

    app.include_router(n8n_webhook_router)
except ImportError:
    pass  # include_n8n_webhook=false — integrations/ wasn't scaffolded

try:
    from fastapi.middleware.cors import CORSMiddleware

    from middleware.auth import get_current_user_id
    from middleware.settings import settings as auth_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=auth_settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Applied to the POST routes below. Without this the split-service backend
    # accepts unauthenticated calls and middleware/auth.py ships as
    # documentation nothing executes (AIT-51). Degrades to DEV_USER_ID when
    # Supabase is unconfigured, so local dev needs no token.
    chat_auth: list = [Depends(get_current_user_id)]
except ImportError:
    # frontend_backend_topology != split_service — middleware/ wasn't scaffolded
    chat_auth = []


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, dependencies=chat_auth)
async def chat(request: ChatRequest) -> ChatResponse:
    assert _graph is not None
    config: RunnableConfig = {"configurable": {"thread_id": request.thread_id}}
    result = _graph.invoke({"message": request.message}, config)
    return ChatResponse(
        message=result["answer"],
        sources=result.get("sources", []),
        confidence=result.get("confidence", 0.0),
    )


@app.post("/api/v1/retrieval", response_model=RetrievalResponse, dependencies=chat_auth)
async def retrieval(request: RetrievalRequest) -> RetrievalResponse:
    """Retrieval only — no answer synthesis. This is the endpoint the project's
    MCP server (mcp_servers/<slug>) search tool calls into — see
    .claude/skills/mcp-builder/SKILL.md's "Consuming your server" section for
    the client side of this same integration."""
    result = retrieve_node({"message": request.query})
    return RetrievalResponse(
        sources=result.get("sources", []),
        context="\n\n---\n\n".join(result.get("context_snippets", [])),
        confidence=result.get("confidence", 0.0),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal error"})
