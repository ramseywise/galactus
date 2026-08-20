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

Idempotency lives here and in the store, not in a queue: an identical request
(same sender, receiver, template, prompt) while a previous attempt is queued,
running, or succeeded returns that job rather than billing a second generation
— the same conditional-write rule the cloud design puts on the job document.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from typing import Annotated

import structlog
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel

from config import ConfigError, Settings
from generate import generate_collateral
from ingest.facts import ingest_pdf_bytes, pdf_page_count
from layout.contract import DEFAULT_TEMPLATE_ID, TemplateNotFoundError, load_template_cached
from model.gateway import LLM, AnthropicAdapter, LLMError
from models import PipelineState
from observability import bind_job, clear_job, configure_structlog
from store import DuplicateJobError, Store

log = structlog.get_logger(__name__)

RETENTION_SWEEP_SECONDS = 3600.0
"""How often the retention sweep re-runs after the one at startup. Deletion is
by age, so the only cost of a coarse interval is rows lingering up to an hour
past their retention date."""

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
"""Ceiling on one uploaded PDF.

Uploads are held in memory and copied into the store; without a cap the
endpoint is an invitation to OOM the process with one request. 25 MB is
generous for marketing/context decks — a fixture that legitimately exceeds it
should raise the constant, not remove it.
"""

PDF_MAGIC = b"%PDF-"


class RateLimiter:
    """Sliding one-minute window per caller, held in process memory.

    Guards the billed endpoint: a client loop resubmitting varied requests is
    otherwise an unbounded model bill. Per-process by construction — two
    instances each enforce their own window, which is why the Cloud Run notes
    pin `max-instances=1`; scaling out means moving this to shared storage or
    an edge quota. A limit of 0 disables it.
    """

    WINDOW_SECONDS = 60.0

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, caller: str) -> float | None:
        """Record one request. None if allowed; seconds until a slot frees if not."""
        if self.per_minute <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            events = self._events[caller]
            while events and now - events[0] >= self.WINDOW_SECONDS:
                events.popleft()
            if len(events) >= self.per_minute:
                return self.WINDOW_SECONDS - (now - events[0])
            events.append(now)
            return None


_settings = Settings.load()
_store = Store(_settings.db_path)
_adapter: AnthropicAdapter | None = None
_rate_limiter = RateLimiter(_settings.rate_limit_per_minute)

_job_slots: asyncio.Semaphore | None = None
"""The process-wide cap on concurrent generations — see `_job_gate`."""

configure_structlog(_settings.log_level)


def get_store() -> Store:
    """The process-wide store. Overridden in tests."""
    return _store


def get_llm() -> LLM:
    """The provider adapter — one per process. Overridden in tests.

    A single adapter means a single HTTP client underneath, so TCP+TLS setup is
    paid once and amortized over every job instead of once per request.
    Construction still does not touch the credential; only a generation call
    does.
    """
    global _adapter
    if _adapter is None:
        _adapter = AnthropicAdapter(_settings)
    return _adapter


def get_settings() -> Settings:
    """Process settings, loaded once at import. Overridden in tests."""
    return _settings


def get_rate_limiter() -> RateLimiter:
    """The process-wide rate limiter. Overridden in tests."""
    return _rate_limiter


def _job_gate(settings: Settings) -> asyncio.Semaphore:
    """The shared semaphore bounding concurrent generations, made on first use.

    Lazy because a Semaphore binds to the running event loop, which does not
    exist at import time. Module-level so every background task passes through
    the same gate; a job waiting here is honestly reported as `queued`.
    """
    global _job_slots
    if _job_slots is None:
        _job_slots = asyncio.Semaphore(settings.max_concurrent_jobs)
    return _job_slots


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Shared-secret gate, active only when GALACTUS_API_KEY is configured.

    Not tenant auth — every keyholder can see every company. It is the minimum
    that makes a non-localhost deployment defensible until the cloud design's
    real identity layer exists, and /health stays open for probes.
    """
    if _settings.api_key and x_api_key != _settings.api_key:
        raise HTTPException(401, detail="invalid or missing API key")


class CollateralRequest(BaseModel):
    """A request to generate one piece of collateral."""

    sender_company_id: str
    receiver_company_id: str
    prompt: str = ""
    template_id: str = DEFAULT_TEMPLATE_ID

    def dedup_key(self) -> str:
        parts = "|".join(
            (self.sender_company_id, self.receiver_company_id, self.template_id, self.prompt)
        )
        return hashlib.sha256(parts.encode("utf-8")).hexdigest()


class JobAccepted(BaseModel):
    job_id: str
    status: str = "queued"


class UploadAccepted(BaseModel):
    pdf_id: str
    company_id: str
    role: str


class PdfInfo(BaseModel):
    pdf_id: str
    company_id: str
    role: str
    filename: str
    size_bytes: int
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    draft: dict[str, str] | None = None
    used_fallback: bool | None = None
    fallback_fields: list[str] | None = None
    repair_attempts: int | None = None
    fact_count: int | None = None
    error: str | None = None
    template_id: str | None = None


async def _retention_loop(store: Store, settings: Settings) -> None:
    """Sweep expired jobs and PDFs now, then hourly until cancelled.

    A failed sweep is logged and retried next interval rather than raised — a
    cleanup task must never take the serving process down with it.
    """
    while True:
        try:
            jobs, pdfs = await asyncio.to_thread(store.sweep_expired, settings.retention_days)
            if jobs or pdfs:
                log.info(
                    "retention_sweep",
                    jobs_deleted=jobs,
                    pdfs_deleted=pdfs,
                    retention_days=settings.retention_days,
                )
        except Exception:
            log.exception("retention_sweep_failed")
        await asyncio.sleep(RETENTION_SWEEP_SECONDS)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    stale = _store.fail_stale_jobs()
    if stale:
        log.warning("stale_jobs_failed_at_startup", count=stale)
    sweeper = (
        asyncio.create_task(_retention_loop(_store, _settings))
        if _settings.retention_days > 0
        else None
    )
    yield
    if sweeper is not None:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper


app = FastAPI(
    title="galactus",
    description="Constrained collateral generation behind a deterministic layout contract.",
    version="0.1.0",
    lifespan=_lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/companies/{company_id}/context",
    response_model=UploadAccepted,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
async def upload_context(
    company_id: str,
    store: Annotated[Store, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, File()],
    role: Annotated[str, Form()] = "sender",
) -> UploadAccepted:
    """Store a company's context PDF.

    Ingest is deferred to generation time rather than run here. The vision path
    costs money, and a PDF that is uploaded but never used in a brief should
    not incur it. What is checked here is what would otherwise fail invisibly
    later: the size cap, and that the bytes are a PDF at all — a mislabelled
    JPEG accepted today is a failed generation job tomorrow, discovered by the
    wrong person.
    """
    if role not in {"sender", "receiver"}:
        raise HTTPException(422, detail="role must be 'sender' or 'receiver'")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(422, detail="uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            413, detail=f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit"
        )
    if not content.startswith(PDF_MAGIC):
        raise HTTPException(422, detail="file is not a PDF")

    # Page-cap and readability, checked while the uploader is still on the
    # line. Ingest re-checks the cap (rows can predate a lowered cap), but the
    # person who can fix an oversized or corrupt deck is the one uploading it,
    # not whoever requests a brief against it next week.
    try:
        page_count = await asyncio.to_thread(pdf_page_count, content)
    except Exception as exc:
        raise HTTPException(422, detail="file is not a readable PDF") from exc
    if page_count > settings.max_pdf_pages:
        raise HTTPException(
            413,
            detail=(
                f"PDF has {page_count} pages, over the {settings.max_pdf_pages}-page limit — "
                "split the document before uploading"
            ),
        )

    pdf_id = await asyncio.to_thread(
        store.put_pdf, company_id, role, file.filename or "upload.pdf", content
    )
    return UploadAccepted(pdf_id=pdf_id, company_id=company_id, role=role)


@app.get(
    "/companies/{company_id}/context",
    response_model=list[PdfInfo],
    dependencies=[Depends(require_api_key)],
)
def list_context(company_id: str, store: Annotated[Store, Depends(get_store)]) -> list[PdfInfo]:
    """List a company's uploaded context — metadata only, no document bytes."""
    return [PdfInfo(**row) for row in store.list_pdfs(company_id)]


@app.delete(
    "/companies/{company_id}/context/{pdf_id}",
    status_code=204,
    dependencies=[Depends(require_api_key)],
)
def delete_context(
    company_id: str, pdf_id: str, store: Annotated[Store, Depends(get_store)]
) -> None:
    """Remove one uploaded PDF — the recovery path for a bad upload."""
    if not store.delete_pdf(company_id, pdf_id):
        raise HTTPException(404, detail=f"no such pdf for {company_id}: {pdf_id}")


@app.post(
    "/collateral",
    response_model=JobAccepted,
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
async def request_collateral(
    request: CollateralRequest,
    background: BackgroundTasks,
    store: Annotated[Store, Depends(get_store)],
    llm: Annotated[LLM, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> JobAccepted:
    """Queue a generation job and return immediately with its id.

    Both sides' context is checked up front — a partnership brief grounded on
    one company is not a degraded success, it is a request that cannot be
    served, and the caller should hear that as a 404 now rather than infer it
    from a hollow draft later.
    """
    # Cheapest guard first, before any store read. The caller is the sender
    # company — the shared X-API-Key cannot tell callers apart, and the sender
    # is the party a runaway client loop would be billing against. Duplicate
    # resubmissions spend window slots too; they are still requests.
    wait = limiter.retry_after(request.sender_company_id)
    if wait is not None:
        raise HTTPException(
            429,
            detail=(
                f"rate limit exceeded for {request.sender_company_id}: "
                f"{limiter.per_minute} generation requests per minute"
            ),
            headers={"Retry-After": str(max(1, math.ceil(wait)))},
        )

    try:
        load_template_cached(request.template_id)
    except (TemplateNotFoundError, ValueError) as exc:
        raise HTTPException(404, detail=f"unknown template: {request.template_id}") from exc

    for company_id, role in (
        (request.sender_company_id, "sender"),
        (request.receiver_company_id, "receiver"),
    ):
        if not store.get_pdfs(company_id, role=role):
            raise HTTPException(404, detail=f"no {role} context uploaded for {company_id}")

    # Read-then-insert alone is a race: two identical requests interleaving
    # between the read and the insert used to bill two generations. The
    # store's partial unique index now arbitrates — the loser's insert raises
    # and the retry re-reads the winner. Two rounds cover the realistic
    # interleavings; losing both means the winner failed in the microseconds
    # between insert and re-read, and the client's retry will land.
    dedup_key = request.dedup_key()
    for _ in range(2):
        existing = store.find_active_job(dedup_key)
        if existing is not None:
            return JobAccepted(job_id=existing["job_id"], status=existing["status"])
        try:
            job_id = store.create_job(
                request.sender_company_id,
                {"template_id": request.template_id, "prompt": request.prompt},
                dedup_key=dedup_key,
            )
            break
        except DuplicateJobError:
            continue
    else:
        raise HTTPException(409, detail="a concurrent identical request is being resolved; retry")

    background.add_task(run_job, job_id, request, store, llm, settings)
    return JobAccepted(job_id=job_id)


@app.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    dependencies=[Depends(require_api_key)],
)
def get_job(job_id: str, store: Annotated[Store, Depends(get_store)]) -> JobStatusResponse:
    """Poll a job. 404 for an unknown id; 200 with a status for a known one."""
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, detail=f"no such job: {job_id}")

    # The store document carries fields the response deliberately omits
    # (company_id, the original prompt, the dedup key). Whitelisting here keeps
    # the response schema the contract, whatever the payload accretes.
    known = {name: value for name, value in job.items() if name in JobStatusResponse.model_fields}
    return JobStatusResponse(**known)


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
    forever against a job stuck in `running`. That includes the bookkeeping
    writes themselves: a store hiccup while recording a failure must not
    resurrect the stuck-job outcome this function exists to prevent.
    """
    bind_job(job_id)

    try:
        # The gate bounds concurrent generations; a job waiting for a slot is
        # still honestly `queued`, and flips to `running` only once it holds
        # one. Without this, N simultaneous submissions are N simultaneous
        # ingest+generate pipelines in one process.
        async with _job_gate(settings):
            store.update_job(job_id, "running")

            template = load_template_cached(request.template_id)
            state = PipelineState(job_id=job_id, prompt=request.prompt)

            # Fetch by role, not by company alone. The same company can appear on
            # both sides across different briefs, so a company-only query would pull
            # its receiver-role PDFs into `sender_facts` — collapsing the very
            # separation `_render_facts` builds the grounding block around.
            sender_rows, receiver_rows = await asyncio.gather(
                asyncio.to_thread(store.get_pdfs, request.sender_company_id, "sender"),
                asyncio.to_thread(store.get_pdfs, request.receiver_company_id, "receiver"),
            )
            state.sender_facts, state.receiver_facts = await asyncio.gather(
                _ingest_rows(sender_rows, llm, settings.model, settings.max_pdf_pages),
                _ingest_rows(receiver_rows, llm, settings.model, settings.max_pdf_pages),
            )

            # Context was uploaded, but nothing checkable came out of it — a scan
            # with no key for vision, or a decorative deck. Generating anyway would
            # produce an ungrounded brief presented as a grounded one.
            for side, facts in (
                ("sender", state.sender_facts),
                ("receiver", state.receiver_facts),
            ):
                if not facts:
                    raise ValueError(
                        f"no usable facts extracted from the {side} context — "
                        "the PDFs may be scans (vision needs a provider credential) "
                        "or carry no checkable text"
                    )

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
                fallback_fields=state.fallback_fields,
                repair_attempts=state.repair_attempts,
                fact_count=len(state.sender_facts) + len(state.receiver_facts),
            )
    except (LLMError, ConfigError, TemplateNotFoundError, ValueError) as exc:
        _record_failure(store, job_id, str(exc))
    except Exception as exc:  # noqa: BLE001 - a stuck job is worse than a broad catch
        _record_failure(store, job_id, f"{type(exc).__name__}: {exc}")
    finally:
        # Background tasks run on a shared context pool, so a job id left bound
        # would leak onto the next job's log lines.
        clear_job()


async def _ingest_rows(rows: list[dict], llm: LLM, model: str, max_pages: int) -> list:
    """Ingest one role's PDFs concurrently; order within the role is kept."""
    batches = await asyncio.gather(
        *(ingest_pdf_bytes(row["content"], llm, model=model, max_pages=max_pages) for row in rows)
    )
    return [fact for batch in batches for fact in batch]


def _record_failure(store: Store, job_id: str, message: str) -> None:
    try:
        store.update_job(job_id, "failed", error=message)
    except Exception:  # the failure write failing must not raise past run_job
        log.exception("job_failure_unrecorded", job_id=job_id, error=message)
