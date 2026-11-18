"""The rulebook every platform must follow."""

import logging
from abc import ABC, abstractmethod

import httpx

from app.schemas import PlatformResult

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PostingBot/1.0)"}


class PlatformError(Exception):
    """An expected failure with a message that is safe to show the user."""


class Platform(ABC):
    """Base class. Each platform fills in `name`, `is_configured` and `_send`."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """True if all credentials for this platform exist in .env."""

    @abstractmethod
    async def _send(self, client: httpx.AsyncClient, message: str) -> str:
        """Post the message and return the public URL of the new post."""

    async def publish(self, client: httpx.AsyncClient, message: str) -> PlatformResult:
        """Post safely. This NEVER raises; it always returns a result."""
        if not self.is_configured():
            return PlatformResult.fail(self.name, "Missing credentials in .env")

        try:
            url = await self._send(client, message)
        except PlatformError as exc:
            return PlatformResult.fail(self.name, str(exc))
        except httpx.TimeoutException:
            return PlatformResult.fail(self.name, "Request timed out")
        except httpx.HTTPError as exc:
            return PlatformResult.fail(self.name, f"Network error: {type(exc).__name__}")
        except Exception:
            logger.exception("Unexpected error while posting to %s", self.name)
            return PlatformResult.fail(self.name, "Unexpected internal error")
        try:
            public = await self._is_public(client, url)
        except Exception:
            logger.exception("Public-access check crashed for %s", self.name)
            public = False
        return PlatformResult.ok(self.name, url, public)

    async def _is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        """Really open the posted URL, like a stranger would."""
        try:
            response = await client.get(url, headers=BROWSER_HEADERS, follow_redirects=True)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    @staticmethod
    def check_response(response: httpx.Response) -> None:
        """Turn a bad HTTP reply into a short, readable PlatformError."""
        if response.is_success:
            return
        if response.status_code in (401, 403):
            raise PlatformError("Authentication failed (check your credentials)")
        if response.status_code == 429:
            raise PlatformError("Rate limited by the platform; try again later")
        if response.status_code == 404:
            raise PlatformError(
                "HTTP 404: endpoint not found (check the platform's server address)"
            )
        if "json" in response.headers.get("content-type", ""):
            raise PlatformError(f"HTTP {response.status_code}: {response.text[:150]}")
        raise PlatformError(f"HTTP {response.status_code}")

    @staticmethod
    def error_text(response: httpx.Response) -> str:
        """Best-effort readable reason from an error reply."""
        try:
            return str(response.json()["error"])
        except (ValueError, KeyError, TypeError):
            return response.text[:150]