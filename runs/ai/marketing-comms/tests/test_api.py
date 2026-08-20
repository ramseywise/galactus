"""The HTTP surface, walked end to end.

The headline test is `test_full_walk_upload_to_contract_valid_json`: upload,
202, poll, succeeded, contract-valid draft. Everything else exists to pin the
failure modes around it.

FastAPI's TestClient runs background tasks synchronously before the response is
returned, so a poll immediately after the 202 already sees a terminal status.
That makes the walk deterministic without sleeping, at the cost of not
exercising true concurrency — which is not what these tests are for.
"""

from __future__ import annotations

import asyncio
import dataclasses
import sqlite3
from pathlib import Path
from typing import Any

import pymupdf
import pytest
from fakes import ScriptedLLM
from fastapi.testclient import TestClient

import api
from api import (
    CollateralRequest,
    RateLimiter,
    app,
    get_llm,
    get_rate_limiter,
    get_settings,
    get_store,
)
from config import Settings
from guardrails.validator import validate
from store import DuplicateJobError, Store

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SENDER_PDF = FIXTURE_DIR / "sender.pdf"
RECEIVER_PDF = FIXTURE_DIR / "receiver.pdf"


@pytest.fixture(autouse=True)
def _fresh_process_state():
    """Reset the module-level rate limiter and job gate around every test.

    Both are process-globals on purpose — one window, one gate per process —
    but a test suite is many processes in miniature: without the reset the
    limiter's window accumulates across tests until unrelated ones start
    drawing 429s, and the semaphore stays bound to a dead test's event loop.
    """
    api._rate_limiter = RateLimiter(api._settings.rate_limit_per_minute)
    api._job_slots = None
    yield
    api._job_slots = None


@pytest.fixture
def store() -> Store:
    store = Store()
    yield store
    store.close()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        anthropic_api_key="sk-ant-test",
        model="claude-sonnet-5",
        max_repairs=3,
        log_level="INFO",
    )


@pytest.fixture
def llm(clean_draft) -> ScriptedLLM:
    return ScriptedLLM([clean_draft])


@pytest.fixture
def client(store, llm, settings) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _upload(client: TestClient, company_id: str, pdf: Path, role: str) -> str:
    response = client.post(
        f"/companies/{company_id}/context",
        files={"file": (pdf.name, pdf.read_bytes(), "application/pdf")},
        data={"role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()["pdf_id"]


def _walk(client: TestClient, prompt: str = "Announce the partnership.") -> dict[str, Any]:
    """Upload both PDFs, request collateral, and poll once."""
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    accepted = client.post(
        "/collateral",
        json={
            "sender_company_id": "meridian",
            "receiver_company_id": "calder",
            "prompt": prompt,
        },
    )
    assert accepted.status_code == 202, accepted.text

    job_id = accepted.json()["job_id"]
    polled = client.get(f"/jobs/{job_id}")
    assert polled.status_code == 200, polled.text
    return polled.json()


def _blank_pdf() -> bytes:
    """A structurally valid PDF with one empty page — no text, no tables."""
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes()


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


def test_full_walk_upload_to_contract_valid_json(client, template, clean_draft):
    job = _walk(client)

    assert job["status"] == "succeeded"
    assert job["draft"] == clean_draft
    assert validate(job["draft"], template) == []
    assert job["used_fallback"] is False


def test_the_walk_grounds_on_ingested_facts(client):
    job = _walk(client)

    # Both fixture PDFs contribute; each yields well over five text facts.
    assert job["fact_count"] >= 10


def test_vision_calls_carry_the_rendered_page(client, llm):
    """The regression that motivated the port change: the image must travel.

    Each fixture has one text-sparse table page, so the walk makes one vision
    call per PDF — and every one of them must actually attach a rendered PNG,
    not just a prompt that talks about a page the model never sees.
    """
    _walk(client)

    vision_images = [
        images
        for schema, images in zip(llm.schemas, llm.images, strict=True)
        if "facts" in schema["properties"]
    ]
    assert vision_images, "no vision calls were made"
    for images in vision_images:
        assert len(images) == 1
        assert images[0].startswith(b"\x89PNG\r\n\x1a\n")


def test_accepted_response_carries_a_queued_job(client):
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    response = client.post(
        "/collateral",
        json={"sender_company_id": "meridian", "receiver_company_id": "calder"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["job_id"]


def test_health_is_ok(client):
    assert client.get("/health").json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def test_upload_returns_a_pdf_id(client):
    pdf_id = _upload(client, "meridian", SENDER_PDF, "sender")

    assert pdf_id


def test_upload_rejects_an_unknown_role(client):
    response = client.post(
        "/companies/meridian/context",
        files={"file": (SENDER_PDF.name, SENDER_PDF.read_bytes(), "application/pdf")},
        data={"role": "bystander"},
    )

    assert response.status_code == 422


def test_upload_rejects_an_empty_file(client):
    response = client.post(
        "/companies/meridian/context",
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"role": "sender"},
    )

    assert response.status_code == 422


def test_upload_rejects_bytes_that_are_not_a_pdf(client):
    """A mislabelled JPEG accepted today is a failed generation job tomorrow."""
    response = client.post(
        "/companies/meridian/context",
        files={"file": ("photo.pdf", b"\xff\xd8\xff\xe0 not a pdf", "application/pdf")},
        data={"role": "sender"},
    )

    assert response.status_code == 422
    assert "not a PDF" in response.json()["detail"]


def test_upload_rejects_an_oversized_file(client, monkeypatch):
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 1024)

    response = client.post(
        "/companies/meridian/context",
        files={"file": ("big.pdf", b"%PDF-" + b"x" * 2048, "application/pdf")},
        data={"role": "sender"},
    )

    assert response.status_code == 413


def test_uploaded_context_can_be_listed_and_deleted(client):
    """The recovery path for a bad upload: find it, remove it."""
    pdf_id = _upload(client, "meridian", SENDER_PDF, "sender")

    listed = client.get("/companies/meridian/context").json()
    assert [row["pdf_id"] for row in listed] == [pdf_id]
    assert listed[0]["size_bytes"] == len(SENDER_PDF.read_bytes())
    assert "content" not in listed[0]

    assert client.delete(f"/companies/meridian/context/{pdf_id}").status_code == 204
    assert client.get("/companies/meridian/context").json() == []
    assert client.delete(f"/companies/meridian/context/{pdf_id}").status_code == 404


def test_deleting_another_companys_pdf_by_id_is_404(client):
    pdf_id = _upload(client, "meridian", SENDER_PDF, "sender")

    assert client.delete(f"/companies/calder/context/{pdf_id}").status_code == 404
    assert client.get("/companies/meridian/context").json() != []


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_generation_without_sender_context_is_404(client):
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    response = client.post(
        "/collateral",
        json={"sender_company_id": "nobody", "receiver_company_id": "calder"},
    )

    assert response.status_code == 404
    assert "sender" in response.json()["detail"]


def test_generation_without_receiver_context_is_404(client):
    """The symmetric check: a brief grounded on one side is not a success."""
    _upload(client, "meridian", SENDER_PDF, "sender")

    response = client.post(
        "/collateral",
        json={"sender_company_id": "meridian", "receiver_company_id": "calder"},
    )

    assert response.status_code == 404
    assert "receiver" in response.json()["detail"]


def test_unknown_template_is_404(client):
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    response = client.post(
        "/collateral",
        json={
            "sender_company_id": "meridian",
            "receiver_company_id": "calder",
            "template_id": "no_such_template",
        },
    )

    assert response.status_code == 404


def test_path_traversal_template_id_is_404_not_a_file_probe(client):
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    for hostile in ("../../../etc/passwd", "/tmp/evil", "..%2Fescape"):
        response = client.post(
            "/collateral",
            json={
                "sender_company_id": "meridian",
                "receiver_company_id": "calder",
                "template_id": hostile,
            },
        )
        assert response.status_code == 404, hostile


def test_polling_an_unknown_job_is_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_job_response_omits_internal_fields(client):
    """company_id, prompt, and the dedup key stay in the store, not the poll."""
    job = _walk(client)

    assert "company_id" not in job
    assert "prompt" not in job
    assert "dedup_key" not in job


def test_a_company_on_both_sides_does_not_leak_across_roles(client):
    """Role separation has to hold through the API, not just in the store.

    `meridian` has uploaded context under both roles — it is the sender here and
    was the receiver in some earlier brief. Fetching by company id alone would
    ingest both PDFs into `sender_facts`, silently collapsing the separation the
    grounding block is built on. Counting facts is what catches it: the sender
    side must carry one PDF's worth, not two.
    """
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    # Distinct prompts so idempotency does not collapse the two runs.
    baseline = _run(client, "meridian", "calder", prompt="first run")["fact_count"]

    # Now meridian also has receiver-role context on file. The request is
    # otherwise identical, so the fact count must not move. Fetching by company
    # id alone would pull the second PDF into `sender_facts` and inflate this.
    _upload(client, "meridian", RECEIVER_PDF, "receiver")
    both_roles = _run(client, "meridian", "calder", prompt="second run")["fact_count"]

    assert both_roles == baseline


def _run(client: TestClient, sender: str, receiver: str, prompt: str = "") -> dict[str, Any]:
    """Request collateral and poll once, asserting the job succeeded."""
    accepted = client.post(
        "/collateral",
        json={"sender_company_id": sender, "receiver_company_id": receiver, "prompt": prompt},
    )
    assert accepted.status_code == 202, accepted.text

    job = client.get(f"/jobs/{accepted.json()['job_id']}").json()
    assert job["status"] == "succeeded", job
    return job


def test_sender_context_under_the_wrong_role_is_404(client):
    """Uploading only receiver-role context is not sender context."""
    _upload(client, "meridian", SENDER_PDF, "receiver")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    response = client.post(
        "/collateral",
        json={"sender_company_id": "meridian", "receiver_company_id": "calder"},
    )

    assert response.status_code == 404


def test_identical_requests_reuse_the_job(client):
    """Idempotency: a double submit is one billed generation, not two."""
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    body = {
        "sender_company_id": "meridian",
        "receiver_company_id": "calder",
        "prompt": "Announce the partnership.",
    }
    first = client.post("/collateral", json=body)
    second = client.post("/collateral", json=body)

    assert first.json()["job_id"] == second.json()["job_id"]
    # The replay reports the job's real state rather than pretending to queue.
    assert second.json()["status"] == "succeeded"

    different = client.post("/collateral", json={**body, "prompt": "A different brief."})
    assert different.json()["job_id"] != first.json()["job_id"]


def test_a_failed_job_does_not_block_resubmission(store, settings, clean_draft):
    """Failed attempts are not duplicates — resubmitting one must generate."""
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM(error=True)
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        first = _walk(client)
        assert first["status"] == "failed"

        app.dependency_overrides[get_llm] = lambda: ScriptedLLM([clean_draft])
        retry = client.post(
            "/collateral",
            json={
                "sender_company_id": "meridian",
                "receiver_company_id": "calder",
                "prompt": "Announce the partnership.",
            },
        )
        job = client.get(f"/jobs/{retry.json()['job_id']}").json()

    app.dependency_overrides.clear()
    assert job["status"] == "succeeded"


def test_a_provider_failure_is_recorded_not_raised(store, settings, clean_draft):
    """A background task that raises would leave the client polling forever."""
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM(error=True)
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        job = _walk(client)

    app.dependency_overrides.clear()

    assert job["status"] == "failed"
    assert "provider unavailable" in job["error"]
    assert job["draft"] is None


def test_a_degraded_draft_is_reported_as_degraded(store, settings, clean_draft):
    """The API never presents a fallback draft as undegraded work."""
    overlong = {**clean_draft, "headline": " ".join(["overlong"] * 20)}
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM([overlong])
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        job = _walk(client)

    app.dependency_overrides.clear()

    assert job["status"] == "succeeded"
    assert job["used_fallback"] is True
    assert job["fallback_fields"] == ["headline"]
    assert job["repair_attempts"] == 3


def test_context_that_yields_no_facts_fails_the_job_explicitly(store, settings, clean_draft):
    """Blank context must surface as an error, not an ungrounded 'success'."""
    app.dependency_overrides[get_store] = lambda: store
    # No vision facts either — the blank page has nothing to read.
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM([clean_draft], vision_facts=[])
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        blank = _blank_pdf()
        for company, role in (("meridian", "sender"), ("calder", "receiver")):
            response = client.post(
                f"/companies/{company}/context",
                files={"file": ("blank.pdf", blank, "application/pdf")},
                data={"role": role},
            )
            assert response.status_code == 201

        accepted = client.post(
            "/collateral",
            json={"sender_company_id": "meridian", "receiver_company_id": "calder"},
        )
        job = client.get(f"/jobs/{accepted.json()['job_id']}").json()

    app.dependency_overrides.clear()

    assert job["status"] == "failed"
    assert "no usable facts" in job["error"]


def test_api_key_gate_when_configured(store, llm, settings, monkeypatch):
    monkeypatch.setattr(api, "_settings", dataclasses.replace(api._settings, api_key="sekret"))
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        denied = client.get("/companies/meridian/context")
        allowed = client.get("/companies/meridian/context", headers={"X-API-Key": "sekret"})
        health = client.get("/health")

    app.dependency_overrides.clear()

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert health.status_code == 200


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def test_store_round_trips_a_pdf(store):
    pdf_id = store.put_pdf("acme", "sender", "a.pdf", b"%PDF-1.4 bytes")

    rows = store.get_pdfs("acme")

    assert len(rows) == 1
    assert rows[0]["pdf_id"] == pdf_id
    assert rows[0]["content"] == b"%PDF-1.4 bytes"
    assert rows[0]["created_at"]


def test_store_filters_pdfs_by_role(store):
    store.put_pdf("acme", "sender", "a.pdf", b"a")
    store.put_pdf("acme", "receiver", "b.pdf", b"b")

    assert len(store.get_pdfs("acme", role="sender")) == 1
    assert len(store.get_pdfs("acme")) == 2


def test_store_isolates_companies(store):
    store.put_pdf("acme", "sender", "a.pdf", b"a")

    assert store.get_pdfs("other") == []


def test_store_lists_metadata_without_content(store):
    store.put_pdf("acme", "sender", "a.pdf", b"abcdef")

    rows = store.list_pdfs("acme")

    assert rows[0]["size_bytes"] == 6
    assert "content" not in rows[0]


def test_update_job_merges_into_the_payload(store):
    job_id = store.create_job("acme", {"template_id": "two_column_brief"})

    store.update_job(job_id, "succeeded", draft={"headline": "x"})
    job = store.get_job(job_id)

    assert job["status"] == "succeeded"
    assert job["template_id"] == "two_column_brief"
    assert job["draft"] == {"headline": "x"}


def test_updating_an_unknown_job_raises(store):
    with pytest.raises(KeyError):
        store.update_job("nope", "succeeded")


def test_get_job_returns_none_for_an_unknown_id(store):
    assert store.get_job("nope") is None


def test_find_active_job_skips_failed_attempts(store):
    first = store.create_job("acme", {}, dedup_key="k1")
    assert store.find_active_job("k1")["job_id"] == first

    store.update_job(first, "failed", error="boom")
    assert store.find_active_job("k1") is None

    second = store.create_job("acme", {}, dedup_key="k1")
    store.update_job(second, "succeeded")
    assert store.find_active_job("k1")["job_id"] == second


def test_fail_stale_jobs_terminates_non_terminal_states(store):
    queued = store.create_job("acme", {})
    running = store.create_job("acme", {})
    store.update_job(running, "running")
    done = store.create_job("acme", {})
    store.update_job(done, "succeeded", draft={"headline": "x"})

    assert store.fail_stale_jobs() == 2

    assert store.get_job(queued)["status"] == "failed"
    assert "restarted" in store.get_job(running)["error"]
    assert store.get_job(done)["status"] == "succeeded"


# ---------------------------------------------------------------------------
# Dedup under the unique index
# ---------------------------------------------------------------------------


def test_create_job_rejects_a_second_active_dedup_key(store):
    """The database, not a read-then-insert, decides who wins."""
    store.create_job("acme", {}, dedup_key="k")

    with pytest.raises(DuplicateJobError):
        store.create_job("acme", {}, dedup_key="k")


def test_dedup_key_frees_on_failure_and_stays_held_after_success(store):
    first = store.create_job("acme", {}, dedup_key="k")
    store.update_job(first, "failed", error="boom")

    second = store.create_job("acme", {}, dedup_key="k")
    store.update_job(second, "succeeded")

    # A succeeded job is still the active holder — resubmitting an identical
    # request must reuse it, not bill again.
    with pytest.raises(DuplicateJobError):
        store.create_job("acme", {}, dedup_key="k")


def test_jobs_without_dedup_keys_never_collide(store):
    store.create_job("acme", {})
    store.create_job("acme", {})  # must not raise: NULLs are not duplicates


def test_init_resolves_preexisting_duplicate_active_jobs(tmp_path):
    """A database from before the unique index can hold live duplicates.

    The index build would fail forever on such a file; init has to resolve
    them — newest survives, older ones are failed loudly — and then enforce.
    """
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, status TEXT NOT NULL,
            dedup_key TEXT, payload TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        );
        CREATE INDEX idx_jobs_dedup ON jobs (dedup_key);
        INSERT INTO jobs (job_id, company_id, status, dedup_key, payload)
            VALUES ('job-1', 'acme', 'queued', 'k', '{}');
        INSERT INTO jobs (job_id, company_id, status, dedup_key, payload)
            VALUES ('job-2', 'acme', 'running', 'k', '{}');
        """
    )
    conn.commit()
    conn.close()

    store = Store(path)
    try:
        assert store.find_active_job("k")["job_id"] == "job-2"
        assert store.get_job("job-1")["status"] == "failed"
        assert "superseded" in store.get_job("job-1")["error"]
        with pytest.raises(DuplicateJobError):
            store.create_job("acme", {}, dedup_key="k")
    finally:
        store.close()


def test_lost_insert_race_returns_the_winning_job(client, store, monkeypatch):
    """The check-then-insert race, replayed deterministically.

    The first `find_active_job` reads before the winner is visible; the insert
    then loses to the unique index, and the retry must hand back the winner's
    job rather than a 500 or a second generation.
    """
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    body = {
        "sender_company_id": "meridian",
        "receiver_company_id": "calder",
        "prompt": "Announce the partnership.",
    }
    winner = store.create_job(
        "meridian",
        {"template_id": "two_column_brief", "prompt": body["prompt"]},
        dedup_key=CollateralRequest(**body).dedup_key(),
    )

    real_find = store.find_active_job
    calls = {"n": 0}

    def stale_then_real(dedup_key):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(dedup_key)

    monkeypatch.setattr(store, "find_active_job", stale_then_real)

    response = client.post("/collateral", json=body)

    assert response.status_code == 202
    assert response.json()["job_id"] == winner


def test_a_race_that_cannot_be_resolved_is_409_not_500(client, store, monkeypatch):
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")

    body = {"sender_company_id": "meridian", "receiver_company_id": "calder"}
    store.create_job(
        "meridian",
        {"template_id": "two_column_brief", "prompt": ""},
        dedup_key=CollateralRequest(**body).dedup_key(),
    )
    monkeypatch.setattr(store, "find_active_job", lambda dedup_key: None)

    response = client.post("/collateral", json=body)

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Rate limit and the job gate
# ---------------------------------------------------------------------------


def test_rate_limit_blocks_the_burst_and_isolates_callers(client):
    _upload(client, "meridian", SENDER_PDF, "sender")
    _upload(client, "calder", RECEIVER_PDF, "receiver")
    _upload(client, "calder", SENDER_PDF, "sender")
    _upload(client, "meridian", RECEIVER_PDF, "receiver")

    # One instance, not a per-request lambda-fresh one — the window has to
    # accumulate across requests to limit anything.
    limiter = RateLimiter(1)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    body = {"sender_company_id": "meridian", "receiver_company_id": "calder"}
    first = client.post("/collateral", json={**body, "prompt": "one"})
    second = client.post("/collateral", json={**body, "prompt": "two"})

    assert first.status_code == 202
    assert second.status_code == 429
    assert "meridian" in second.json()["detail"]
    assert int(second.headers["Retry-After"]) >= 1

    # A different caller draws from its own window, not meridian's.
    swapped = client.post(
        "/collateral",
        json={"sender_company_id": "calder", "receiver_company_id": "meridian", "prompt": "one"},
    )
    assert swapped.status_code == 202


def test_rate_limiter_window_slides(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(api.time, "monotonic", lambda: clock["now"])
    limiter = RateLimiter(2)

    assert limiter.retry_after("acme") is None
    assert limiter.retry_after("acme") is None
    assert limiter.retry_after("acme") == pytest.approx(60.0)

    clock["now"] = 61.0
    assert limiter.retry_after("acme") is None


def test_rate_limiter_zero_disables(monkeypatch):
    limiter = RateLimiter(0)
    for _ in range(50):
        assert limiter.retry_after("acme") is None


async def test_job_gate_bounds_concurrent_generations(settings, clean_draft, monkeypatch):
    """Two jobs, one slot: their running→terminal windows must not overlap.

    The gate bounds *jobs*, not provider calls — one job's sender and receiver
    ingest legitimately overlap inside it. So the assertion is on the status
    timeline: with one slot, the second job may not turn `running` until the
    first is done.
    """

    class YieldingLLM(ScriptedLLM):
        async def complete_structured(self, *args, **kwargs):
            await asyncio.sleep(0)  # yield so the other job could interleave
            return await super().complete_structured(*args, **kwargs)

    store = Store()
    store.put_pdf("meridian", "sender", "s.pdf", SENDER_PDF.read_bytes())
    store.put_pdf("calder", "receiver", "r.pdf", RECEIVER_PDF.read_bytes())
    llm = YieldingLLM([clean_draft])
    gated = dataclasses.replace(settings, max_concurrent_jobs=1)

    events: list[tuple[str, str]] = []
    real_update = store.update_job

    def logging_update(job_id, status, **fields):
        events.append((job_id, status))
        real_update(job_id, status, **fields)

    monkeypatch.setattr(store, "update_job", logging_update)

    requests = [
        CollateralRequest(sender_company_id="meridian", receiver_company_id="calder", prompt=p)
        for p in ("one", "two")
    ]
    job_ids = [
        store.create_job("meridian", {"template_id": r.template_id, "prompt": r.prompt})
        for r in requests
    ]

    try:
        await asyncio.gather(
            *(
                api.run_job(job_id, request, store, llm, gated)
                for job_id, request in zip(job_ids, requests, strict=True)
            )
        )
        for job_id in job_ids:
            assert store.get_job(job_id)["status"] == "succeeded"
        # Four events in two uninterleaved pairs: whoever ran first finished
        # before the other started.
        assert [job for job, _ in events] == [events[0][0]] * 2 + [events[2][0]] * 2
        assert [status for _, status in events] == ["running", "succeeded"] * 2
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Upload page cap
# ---------------------------------------------------------------------------


def _pdf_with_pages(count: int) -> bytes:
    doc = pymupdf.open()
    for number in range(count):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {number + 1}")
    return doc.tobytes()


def test_upload_rejects_a_pdf_over_the_page_cap(store, llm, settings):
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_settings] = lambda: dataclasses.replace(settings, max_pdf_pages=2)

    with TestClient(app) as client:
        response = client.post(
            "/companies/meridian/context",
            files={"file": ("long.pdf", _pdf_with_pages(3), "application/pdf")},
            data={"role": "sender"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 413
    assert "3 pages" in response.json()["detail"]


def test_upload_accepts_a_pdf_at_the_page_cap(store, llm, settings):
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_settings] = lambda: dataclasses.replace(settings, max_pdf_pages=3)

    with TestClient(app) as client:
        response = client.post(
            "/companies/meridian/context",
            files={"file": ("exact.pdf", _pdf_with_pages(3), "application/pdf")},
            data={"role": "sender"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201


def test_upload_rejects_magic_bytes_without_a_readable_document(client):
    """The magic-byte check alone let corrupt files through to fail at
    generation time, in front of the wrong person."""
    response = client.post(
        "/companies/meridian/context",
        files={"file": ("broken.pdf", b"%PDF-1.4 not actually a pdf", "application/pdf")},
        data={"role": "sender"},
    )

    assert response.status_code == 422
    assert "readable" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


ANCIENT = "2000-01-01T00:00:00.000Z"


def _backdate(store: Store, table: str, id_column: str, row_id: str) -> None:
    with store._connect() as conn:
        conn.execute(
            f"UPDATE {table} SET created_at = ? WHERE {id_column} = ?",
            (ANCIENT, row_id),
        )


def test_sweep_expired_deletes_only_old_terminal_rows(store):
    old_done = store.create_job("acme", {})
    store.update_job(old_done, "succeeded")
    old_running = store.create_job("acme", {})
    store.update_job(old_running, "running")
    fresh = store.create_job("acme", {})
    store.update_job(fresh, "succeeded")

    old_pdf = store.put_pdf("acme", "sender", "old.pdf", b"a")
    store.put_pdf("acme", "sender", "new.pdf", b"b")

    for row_id in (old_done, old_running):
        _backdate(store, "jobs", "job_id", row_id)
    _backdate(store, "pdfs", "pdf_id", old_pdf)

    assert store.sweep_expired(30) == (1, 1)

    assert store.get_job(old_done) is None
    # Old but non-terminal stays: it belongs to a worker or to fail_stale_jobs.
    assert store.get_job(old_running)["status"] == "running"
    assert store.get_job(fresh)["status"] == "succeeded"
    assert [row["filename"] for row in store.list_pdfs("acme")] == ["new.pdf"]


def test_sweeping_a_succeeded_job_frees_its_dedup_key(store):
    job = store.create_job("acme", {}, dedup_key="k")
    store.update_job(job, "succeeded")
    _backdate(store, "jobs", "job_id", job)

    store.sweep_expired(30)

    store.create_job("acme", {}, dedup_key="k")  # must not raise


def test_sweep_expired_rejects_a_nonpositive_retention(store):
    with pytest.raises(ValueError):
        store.sweep_expired(0)
