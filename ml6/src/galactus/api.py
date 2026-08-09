"""The HTTP surface: upload context, request collateral, poll for the result.

Generation takes several seconds and may make up to four model calls, which is
past what a client should hold a connection open for. So `POST /collateral`
returns 202 with a job id and the work continues in the background; the client
polls `GET /jobs/{job_id}`.

The 202 is not just a latency accommodation — it is what makes the repair loop
affordable. A synchronous endpoint would push back against retrying, and the
retries are where the contract guarantee comes from.

Dependencies are injected via FastAPI overrides rather than module globals, so
the test suite runs the real routes against an in-memory store and a fake
provider with no network and no spend.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from galactus.ml6.src.galactus.config import Settings
from galactus.ml6.src.galactus.generate import generate_collateral
from galactus.ml6.src.galactus.ingest.facts import ingest_pdf_bytes
from galactus.ml6.src.galactus.layout.contract import TemplateNotFoundError, load_template_cached
from galactus.ml6.src.galactus.llm.anthropic_adapter import AnthropicAdapter
from galactus.ml6.src.galactus.llm.port import LLM, LLMError
from galactus.ml6.src.galactus.models import PipelineState
from galactus.ml6.src.galactus.obs import bind_job, clear_job, configure_structlog
from galactus.ml6.src.galactus.store import Store

DEFAULT_TEMPLATE_ID = "two_column_brief"

_store = Store()


def get_store() -> Store:
    """The process-wide store. Overridden in tests."""
    return _store


def get_llm() -> LLM:
    """The provider adapter. Overridden in tests with a scripted fake.

    Construction does not touch the credential — only a generation call does —
    so this is safe to resolve on every request whether or not a key is set.
    """
    return AnthropicAdapter()


def get_settings() -> Settings:
    return Settings.load()


class CollateralRequest(BaseModel):
    """A request to generate one piece of collateral."""

    sender_company_id: str
    receiver_company_id: str
    prompt: str = ""
    template_id: str = DEFAULT_TEMPLATE_ID


class JobAccepted(BaseModel):
    job_id: str
    status: str = "queued"


class UploadAccepted(BaseModel):
    pdf_id: str
    company_id: str
    role: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    draft: dict[str, str] | None = None
    used_fallback: bool | None = None
    repair_attempts: int | None = None
    fact_count: int | None = None
    error: str | None = None
    template_id: str | None = None


app = FastAPI(
    title="galactus",
    description="Constrained collateral generation behind a deterministic layout contract.",
    version="0.1.0",
)

configure_structlog(Settings.load().log_level)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/companies/{company_id}/context",
    response_model=UploadAccepted,
    status_code=201,
)
async def upload_context(
    company_id: str,
    store: Annotated[Store, Depends(get_store)],
    file: Annotated[UploadFile, File()],
    role: Annotated[str, Form()] = "sender",
) -> UploadAccepted:
    """Store a company's context PDF.

    Ingest is deferred to generation time rather than run here. The vision path
    costs money, and a PDF that is uploaded but never used in a brief should
    not incur it.
    """
    if role not in {"sender", "receiver"}:
        raise HTTPException(422, detail="role must be 'sender' or 'receiver'")

    content = await file.read()
    if not content:
        raise HTTPException(422, detail="uploaded file is empty")

    pdf_id = store.put_pdf(company_id, role, file.filename or "upload.pdf", content)
    return UploadAccepted(pdf_id=pdf_id, company_id=company_id, role=role)


@app.post("/collateral", response_model=JobAccepted, status_code=202)
async def request_collateral(
    request: CollateralRequest,
    background: BackgroundTasks,
    store: Annotated[Store, Depends(get_store)],
    llm: Annotated[LLM, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> JobAccepted:
    """Queue a generation job and return immediately with its id."""
    try:
        load_template_cached(request.template_id)
    except (TemplateNotFoundError, ValueError) as exc:
        raise HTTPException(404, detail=f"unknown template: {request.template_id}") from exc

    if not store.get_pdfs(request.sender_company_id, role="sender"):
        raise HTTPException(
            404, detail=f"no sender context uploaded for {request.sender_company_id}"
        )

    job_id = store.create_job(
        request.sender_company_id,
        {"template_id": request.template_id, "prompt": request.prompt},
    )
    background.add_task(run_job, job_id, request, store, llm, settings)
    return JobAccepted(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, store: Annotated[Store, Depends(get_store)]) -> JobStatusResponse:
    """Poll a job. 404 for an unknown id; 200 with a status for a known one."""
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, detail=f"no such job: {job_id}")
    return JobStatusResponse(**job)


async def run_job(
    job_id: str,
    request: CollateralRequest,
    store: Store,
    llm: LLM,
    settings: Settings,
) -> None:
    """Ingest, generate, persist. Runs in the background after the 202.

    Every failure is caught and recorded as a failed job rather than raised. A
    background task that raises loses the error entirely — the client polls
    forever against a job stuck in `running`.
    """
    bind_job(job_id)
    store.update_job(job_id, "running")

    try:
        template = load_template_cached(request.template_id)
        state = PipelineState(job_id=job_id, prompt=request.prompt)

        # Fetch by role, not by company alone. The same company can appear on
        # both sides across different briefs, so a company-only query would pull
        # its receiver-role PDFs into `sender_facts` — collapsing the very
        # separation `_render_facts` builds the grounding block around.
        for company_id, role, target in (
            (request.sender_company_id, "sender", state.sender_facts),
            (request.receiver_company_id, "receiver", state.receiver_facts),
        ):
            for row in store.get_pdfs(company_id, role=role):
                target.extend(await ingest_pdf_bytes(row["content"], llm))

        draft, used_fallback = await generate_collateral(
            state,
            template,
            llm,
            max_repairs=settings.max_repairs,
            model=settings.model,
        )

        store.update_job(
            job_id,
            "succeeded",
            draft=draft,
            used_fallback=used_fallback,
            repair_attempts=state.repair_attempts,
            fact_count=len(state.sender_facts) + len(state.receiver_facts),
        )
    except (LLMError, TemplateNotFoundError, ValueError) as exc:
        store.update_job(job_id, "failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001 - a stuck job is worse than a broad catch
        store.update_job(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        # Background tasks run on a shared context pool, so a job id left bound
        # would leak onto the next job's log lines.
        clear_job()
