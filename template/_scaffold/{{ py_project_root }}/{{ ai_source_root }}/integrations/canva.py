"""Canva client — generate a design from a brand template via the Canva Connect
API's Autofill endpoint."""

from __future__ import annotations

import httpx

from integrations.settings import settings

_BASE_URL = "https://api.canva.com/rest/v1"


class CanvaClient:
    def __init__(self) -> None:
        if not settings.canva_api_token:
            raise RuntimeError("CANVA_API_TOKEN is not set")
        self._client = httpx.Client(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {settings.canva_api_token}"},
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def generate_asset(self, brand_template_id: str, data: dict) -> dict:
        """``data`` maps template field names to autofill values — see Canva's
        Autofill API docs for the per-field-type shape (text/image fields
        differ)."""
        try:
            resp = self._client.post(
                "/autofills",
                json={"brand_template_id": brand_template_id, "data": data},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Canva API error: {exc.response.status_code} {exc.response.text}"
            ) from exc
