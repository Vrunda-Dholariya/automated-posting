"""Runs every platform at the same time and builds the final response."""

import asyncio
import logging

import httpx

from app.config import settings
from app.platforms.base import Platform
from app.platforms.bluesky import Bluesky
from app.platforms.devto import DevTo
from app.platforms.gist import GitHubGist
from app.platforms.mastodon import Mastodon
from app.platforms.telegram import Telegram
from app.schemas import PlatformResult, PostResponse

logger = logging.getLogger(__name__)


def default_platforms() -> list[Platform]:
    """The platforms the API posts to. Add a new platform here (one line)."""
    return [Bluesky(), DevTo(), Mastodon(), Telegram(), GitHubGist()]


async def post_everywhere(
    message: str, platforms: list[Platform] | None = None
) -> PostResponse:
    """Post `message` to every platform at once and collect the results."""
    platforms = default_platforms() if platforms is None else platforms

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        outcomes = await asyncio.gather(
            *(platform.publish(client, message) for platform in platforms),
            return_exceptions=True,
        )

    results: list[PlatformResult] = []
    for platform, outcome in zip(platforms, outcomes):
        if isinstance(outcome, PlatformResult):
            results.append(outcome)
        else:
            logger.error("Platform %s escaped its safety net: %r", platform.name, outcome)
            results.append(PlatformResult.fail(platform.name, "Unexpected internal error"))

    success = any(result.status == "success" for result in results)
    return PostResponse(success=success, results=results)