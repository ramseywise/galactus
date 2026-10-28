"""LinkedIn client — post a text update via the UGC Posts API."""

from __future__ import annotations

import httpx

from integrations.settings import settings

_BASE_URL = "https://api.linkedin.com/v2"


class LinkedInClient:
    def __init__(self) -> None:
        if not settings.linkedin_access_token:
            raise RuntimeError("LINKEDIN_ACCESS_TOKEN is not set")
        self._client = httpx.Client(
            base_url=_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.linkedin_access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            timeout=30.0,
        )
        self._author_urn = settings.linkedin_author_urn

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def post_update(self, text: str) -> dict:
        try:
            resp = self._client.post(
                "/ugcPosts",
                json={
                    "author": self._author_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": text},
                            "shareMediaCategory": "NONE",
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"LinkedIn API error: {exc.response.status_code} {exc.response.text}"
            ) from exc
