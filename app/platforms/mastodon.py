"""Mastodon integration."""

from urllib.parse import urlparse

import httpx

from app.config import settings
from app.platforms.base import Platform, PlatformError


class Mastodon(Platform):
    name = "Mastodon"

    def is_configured(self) -> bool:
        return bool(settings.mastodon_base_url and settings.mastodon_access_token)

    @property
    def _base(self) -> str:
        """Keep only scheme://host, even if .env has extra text after it."""
        raw = settings.mastodon_base_url.strip()
        if "://" not in raw:
            raw = "https://" + raw
        parsed = urlparse(raw)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _send(self, client: httpx.AsyncClient, message: str) -> str:
        response = await client.post(
            f"{self._base}/api/v1/statuses",
            headers={"Authorization": f"Bearer {settings.mastodon_access_token}"},
            json={"status": message, "visibility": "public"},
        )
        if response.status_code == 422:
            raise PlatformError(f"Mastodon rejected the post: {self.error_text(response)}")
        self.check_response(response)

        try:
            return response.json()["url"]
        except (ValueError, KeyError, TypeError):
            raise PlatformError("Mastodon replied without a post URL") from None

    async def _is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        """Ask the server for the post WITHOUT a token, like a stranger."""
        status_id = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        try:
            response = await client.get(f"{self._base}/api/v1/statuses/{status_id}")
            return response.status_code == 200
        except httpx.HTTPError:
            return False