"""Eventbrite client — create + publish an event via Eventbrite's REST API v3."""

from __future__ import annotations

from datetime import datetime

import httpx

from integrations.settings import settings

_BASE_URL = "https://www.eventbriteapi.com/v3"


class EventbriteClient:
    def __init__(self) -> None:
        if not settings.eventbrite_api_token:
            raise RuntimeError("EVENTBRITE_API_TOKEN is not set")
        self._client = httpx.Client(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {settings.eventbrite_api_token}"},
            timeout=30.0,
        )
        self._organization_id = settings.eventbrite_organization_id

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def publish_event(
        self,
        name: str,
        start: datetime,
        end: datetime,
        currency: str = "USD",
        description: str = "",
    ) -> dict:
        """Creates a draft event, then publishes it — Eventbrite requires a
        separate publish step after creation (drafts aren't public by default)."""
        try:
            create_resp = self._client.post(
                f"/organizations/{self._organization_id}/events/",
                json={
                    "event": {
                        "name": {"html": name},
                        "description": {"html": description},
                        "start": {"timezone": "UTC", "utc": start.isoformat()},
                        "end": {"timezone": "UTC", "utc": end.isoformat()},
                        "currency": currency,
                    }
                },
            )
            create_resp.raise_for_status()
            event = create_resp.json()
            publish_resp = self._client.post(f"/events/{event['id']}/publish/")
            publish_resp.raise_for_status()
            return event
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Eventbrite API error: {exc.response.status_code} {exc.response.text}"
            ) from exc
