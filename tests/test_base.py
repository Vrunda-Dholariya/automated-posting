import asyncio

import httpx

from app.platforms.base import Platform, PlatformError


class Good(Platform):
    name = "Good"

    def is_configured(self):
        return True

    async def _send(self, client, message):
        return "https://example.com/post/1"

    async def _is_public(self, client, url):
        return True  # skip the real network check in tests


class Unconfigured(Good):
    name = "Unconfigured"

    def is_configured(self):
        return False


class Rejected(Good):
    name = "Rejected"

    async def _send(self, client, message):
        raise PlatformError("Authentication failed")


class Slow(Good):
    name = "Slow"

    async def _send(self, client, message):
        raise httpx.ReadTimeout("too slow")


class Crashy(Good):
    name = "Crashy"

    async def _send(self, client, message):
        return 1 / 0


def run(platform):
    async def go():
        async with httpx.AsyncClient() as client:
            return await platform.publish(client, "hello")

    return asyncio.run(go())


def test_success():
    result = run(Good())
    assert result.status == "success"
    assert result.posted_url == "https://example.com/post/1"
    assert result.public_access is True


def test_missing_credentials():
    assert run(Unconfigured()).error == "Missing credentials in .env"


def test_expected_error_is_shown():
    assert run(Rejected()).error == "Authentication failed"


def test_timeout_is_readable():
    assert run(Slow()).error == "Request timed out"


def test_crash_never_escapes_and_hides_details():
    result = run(Crashy())
    assert result.status == "failed"
    assert result.error == "Unexpected internal error"



class BrokenCheck(Good):
    name = "BrokenCheck"

    async def _is_public(self, client, url):
        raise KeyError("boom")


def test_crashing_public_check_keeps_the_successful_post():
    result = run(BrokenCheck())
    assert result.status == "success"
    assert result.posted_url == "https://example.com/post/1"
    assert result.public_access is False