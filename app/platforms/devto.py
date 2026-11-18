"""Dev.to integration (Forem API)."""

from urllib.parse import urlparse

import httpx

from app.config import settings
from app.platforms.base import Platform, PlatformError
from app.schemas import extract_links

API = "https://dev.to/api"
MAX_TITLE = 80


class DevTo(Platform):
    name = "Dev.to"

    def is_configured(self) -> bool:
        return bool(settings.devto_api_key)

    async def _send(self, client: httpx.AsyncClient, message: str) -> str:
        response = await client.post(
            f"{API}/articles",
            headers={
                "api-key": settings.devto_api_key,
                "Accept": "application/vnd.forem.api-v1+json",
            },
            json={
                "article": {
                    "title": self._make_title(message),
                    "body_markdown": message,
                    "published": True,
                }
            },
        )
        if response.status_code == 422:
            raise PlatformError(f"Dev.to rejected the post: {self.error_text(response)}")
        self.check_response(response)

        try:
            return response.json()["url"]
        except (ValueError, KeyError):
            raise PlatformError("Dev.to replied without a post URL") from None

    @staticmethod
    def _make_title(message: str) -> str:
        """Use the message minus its link as the title, shortened if needed."""
        text = message
        for link in extract_links(message):
            text = text.replace(link, "")
        text = " ".join(text.split())

        if not text:
            return "New post"
        if len(text) > MAX_TITLE:
            text = text[: MAX_TITLE - 1].rstrip() + "…"
        return text

    async def _is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        """Ask Dev.to's public API (no key) whether the article exists."""
        path = urlparse(url).path.strip("/")
        try:
            response = await client.get(f"{API}/articles/{path}")
            return response.status_code == 200
        except httpx.HTTPError:
            return False