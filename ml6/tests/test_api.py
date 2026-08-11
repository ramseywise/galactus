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

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from galactus.api import app, get_llm, get_settings, get_store
from galactus.config import Settings
from galactus.layout.validator import validate
from galactus.llm.port import LLMError
from galactus.store import Store

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SENDER_PDF = FIXTURE_DIR / "sender.pdf"
RECEIVER_PDF = FIXTURE_DIR / "receiver.pdf"


class ScriptedLLM:
    """Returns `draft` for generation calls and facts for vision calls.

    One fake serves both pipeline stages because both go through the same port.
    The vision schema is the one with a `facts` key, which is enough to tell
    them apart without threading a mode flag through.
    """

    def __init__(self, draft: dict[str, str], error: bool = False) -> None:
        self.draft = draft
        self.error = error
        self.calls = 0

    async def complete_structured(
        self, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls += 1
        if self.error:
            raise LLMError("provider unavailable")
        if "facts" in schema.get("properties", {}):
            return {"facts": ["A table row reports 96.2 percent on-time."]}
        return dict(self.draft)


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
    return ScriptedLLM(clean_draft)


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


def _walk(
    client: TestClient, prompt: str = "Announce the partnership."
) -> dict[str, Any]:
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


def test_accepted_response_carries_a_queued_job(client):
    _upload(client, "meridian", SENDER_PDF, "sender")

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


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_generation_without_uploaded_context_is_404(client):
    response = client.post(
        "/collateral",
        json={"sender_company_id": "nobody", "receiver_company_id": "calder"},
    )

    assert response.status_code == 404


def test_unknown_template_is_404(client):
    _upload(client, "meridian", SENDER_PDF, "sender")

    response = client.post(
        "/collateral",
        json={
            "sender_company_id": "meridian",
            "receiver_company_id": "calder",
            "template_id": "no_such_template",
        },
    )

    assert response.status_code == 404


def test_polling_an_unknown_job_is_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_a_company_on_both_sides_does_not_leak_across_roles(client):
    """Role separation has to hold through the API, not just in the store.

    `meridian` has uploaded context under both roles — it is the sender here and
    was the receiver in some earlier brief. Fetching by company id alone would
    ingest both PDFs into `sender_facts`, silently collapsing the separation the
    grounding block is built on. Counting facts is what catches it: the sender
    side must carry one PDF's worth, not two.
    """
    _upload(client, "meridian", SENDER_PDF, "sender")

    # `calder` uploaded nothing, so this job's facts are meridian's sender PDF
    # alone — the reference count for one role's worth of context.
    sender_only = _run(client, "meridian", "calder")["fact_count"]

    # Now meridian also has receiver-role context on file. The request is
    # identical, so the fact count must not move. Fetching by company id alone
    # pulled the second PDF into `sender_facts` and inflated this.
    _upload(client, "meridian", RECEIVER_PDF, "receiver")
    both_roles = _run(client, "meridian", "calder")["fact_count"]

    assert both_roles == sender_only


def _run(client: TestClient, sender: str, receiver: str) -> dict[str, Any]:
    """Request collateral and poll once, asserting the job succeeded."""
    accepted = client.post(
        "/collateral",
        json={"sender_company_id": sender, "receiver_company_id": receiver},
    )
    assert accepted.status_code == 202, accepted.text

    job = client.get(f"/jobs/{accepted.json()['job_id']}").json()
    assert job["status"] == "succeeded", job
    return job


def test_sender_context_under_the_wrong_role_is_404(client):
    """Uploading only receiver-role context is not sender context."""
    _upload(client, "meridian", SENDER_PDF, "receiver")

    response = client.post(
        "/collateral",
        json={"sender_company_id": "meridian", "receiver_company_id": "calder"},
    )

    assert response.status_code == 404


def test_a_provider_failure_is_recorded_not_raised(store, settings, clean_draft):
    """A background task that raises would leave the client polling forever."""
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM(clean_draft, error=True)
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
    app.dependency_overrides[get_llm] = lambda: ScriptedLLM(overlong)
    app.dependency_overrides[get_settings] = lambda: settings

    with TestClient(app) as client:
        job = _walk(client)

    app.dependency_overrides.clear()

    assert job["status"] == "succeeded"
    assert job["used_fallback"] is True
    assert job["repair_attempts"] == 3


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def test_store_round_trips_a_pdf(store):
    pdf_id = store.put_pdf("acme", "sender", "a.pdf", b"%PDF-1.4 bytes")

    rows = store.get_pdfs("acme")

    assert len(rows) == 1
    assert rows[0]["pdf_id"] == pdf_id
    assert rows[0]["content"] == b"%PDF-1.4 bytes"


def test_store_filters_pdfs_by_role(store):
    store.put_pdf("acme", "sender", "a.pdf", b"a")
    store.put_pdf("acme", "receiver", "b.pdf", b"b")

    assert len(store.get_pdfs("acme", role="sender")) == 1
    assert len(store.get_pdfs("acme")) == 2


def test_store_isolates_companies(store):
    store.put_pdf("acme", "sender", "a.pdf", b"a")

    assert store.get_pdfs("other") == []


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
