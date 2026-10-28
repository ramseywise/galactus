"""Google Calendar client — list/create events, find availability.

Uses a pre-obtained OAuth2 refresh token, not an interactive consent flow: this
integration acts on a human coordinator's own calendar (user-delegated scope),
so the one-time consent has to happen once, out-of-band, via a real OAuth
screen — not something a starter template can automate. One-time setup:

1. Create OAuth2 credentials (Desktop app type) in Google Cloud Console, scope
   ``https://www.googleapis.com/auth/calendar``.
2. Run any standard "installed app" OAuth flow once (e.g.
   ``google_auth_oauthlib.flow.InstalledAppFlow.run_local_server()``) in a
   throwaway script — not in this module — to obtain a refresh token.
3. Set GOOGLE_CALENDAR_CLIENT_ID / GOOGLE_CALENDAR_CLIENT_SECRET /
   GOOGLE_CALENDAR_REFRESH_TOKEN from that flow's output.
"""

from __future__ import annotations

from datetime import datetime

from integrations.settings import settings


class GoogleCalendarClient:
    def __init__(self) -> None:
        if not settings.google_calendar_refresh_token:
            raise RuntimeError(
                "GOOGLE_CALENDAR_REFRESH_TOKEN is not set — see this module's "
                "docstring for the one-time OAuth setup."
            )
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=settings.google_calendar_refresh_token,
            client_id=settings.google_calendar_client_id,
            client_secret=settings.google_calendar_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        self._service = build("calendar", "v3", credentials=creds)
        self._calendar_id = settings.google_calendar_id

    def list_events(
        self, time_min: datetime, time_max: datetime, max_results: int = 50
    ) -> list[dict]:
        """``time_min``/``time_max`` must be timezone-aware — the Calendar API
        requires RFC3339 timestamps with an explicit offset."""
        result = (
            self._service.events()
            .list(
                calendarId=self._calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])

    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendees: list[str] | None = None,
        description: str = "",
    ) -> dict:
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
            "attendees": [{"email": email} for email in (attendees or [])],
        }
        return self._service.events().insert(calendarId=self._calendar_id, body=body).execute()

    def find_availability(
        self, time_min: datetime, time_max: datetime, duration_minutes: int = 30
    ) -> list[tuple[datetime, datetime]]:
        """Returns open slots of at least ``duration_minutes`` between existing
        events in ``[time_min, time_max)`` — a simple gap-finding scan, not a
        full scheduling optimizer."""
        events = self.list_events(time_min, time_max)
        busy: list[tuple[datetime, datetime]] = []
        for event in events:
            start_str = event.get("start", {}).get("dateTime")
            end_str = event.get("end", {}).get("dateTime")
            if start_str and end_str:
                busy.append((datetime.fromisoformat(start_str), datetime.fromisoformat(end_str)))
        busy.sort()

        slots: list[tuple[datetime, datetime]] = []
        cursor = time_min
        for busy_start, busy_end in busy:
            if (busy_start - cursor).total_seconds() / 60 >= duration_minutes:
                slots.append((cursor, busy_start))
            cursor = max(cursor, busy_end)
        if (time_max - cursor).total_seconds() / 60 >= duration_minutes:
            slots.append((cursor, time_max))
        return slots
