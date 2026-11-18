"""Telegram integration (Bot API, posting to a public channel)."""

import asyncio
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.platforms.base import BROWSER_HEADERS, Platform, PlatformError

API = "https://api.telegram.org"
PREVIEW_HOSTS = ("t.me", "telegram.me")  # two official names for the same site


class Telegram(Platform):
    name = "Telegram"
    CHECK_RETRIES = 3
    CHECK_DELAY = 1.0

    def is_configured(self) -> bool:
        return bool(settings.telegram_bot_token and settings.telegram_chat_id)

    async def _send(self, client: httpx.AsyncClient, message: str) -> str:
        response = await client.post(
            f"{API}/bot{settings.telegram_bot_token}/sendMessage",
            json={"chat_id": settings.telegram_chat_id, "text": message},
        )
        if response.status_code in (400, 403):
            raise PlatformError(f"Telegram refused the post: {self._reason(response)}")
        self.check_response(response)

        try:
            result = response.json()["result"]
            message_id = result["message_id"]
            chat = result["chat"]
        except (ValueError, KeyError, TypeError):
            raise PlatformError("Telegram replied without a message ID") from None

        username = chat.get("username")
        if username:
            return f"https://t.me/{username}/{message_id}"

        # Private channel: this link only opens for members.
        private_id = str(chat.get("id", "")).removeprefix("-100")
        return f"https://t.me/c/{private_id}/{message_id}"

    @staticmethod
    def _reason(response: httpx.Response) -> str:
        """Telegram explains errors in a 'description' field."""
        try:
            return str(response.json()["description"])
        except (ValueError, KeyError, TypeError):
            return f"HTTP {response.status_code}"

    async def _is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        """Look for our message on the channel's public web preview."""
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) != 2:  # private-channel links have 3 parts (c/<id>/<msg>)
            return False

        username, message_id = parts
        marker = f'data-post="{username}/{message_id}"'.lower()

        for attempt in range(self.CHECK_RETRIES):
            if attempt:
                await asyncio.sleep(self.CHECK_DELAY)
            for host in PREVIEW_HOSTS:
                try:
                    response = await client.get(
                        f"https://{host}/s/{username}",
                        headers=BROWSER_HEADERS,
                        follow_redirects=True,
                    )
                except httpx.HTTPError:
                    continue  # this host is unreachable; try the next one
                if response.status_code == 200 and marker in response.text.lower():
                    return True
        return False