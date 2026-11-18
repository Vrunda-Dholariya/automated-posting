import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.platforms.mastodon import Mastodon

POST_URL = "https://mastodon.example/@me/111"


@pytest.fixture(autouse=True)
def fake_setup(monkeypatch):
    monkeypatch.setattr(settings, "mastodon_base_url", "https://mastodon.example/")
    monkeypatch.setattr(settings, "mastodon_access_token", "tok")


def run(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await Mastodon().publish(client, "Hello https://example.com")

    return asyncio.run(go())


def test_success_and_stranger_check_has_no_token():
    seen = {}

    def handler(request):
        if request.method == "POST":
            seen["path"] = request.url.path
            seen["auth"] = request.headers["Authorization"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"id": "111", "url": POST_URL})
        seen["stranger_auth"] = request.headers.get("Authorization")
        assert request.url.path == "/api/v1/statuses/111"
        return httpx.Response(200, json={"id": "111"})

    result = run(handler)
    assert result.status == "success"
    assert result.posted_url == POST_URL
    assert result.public_access is True
    assert seen["path"] == "/api/v1/statuses"  # trailing slash in base URL was handled
    assert seen["auth"] == "Bearer tok"
    assert seen["body"]["visibility"] == "public"
    assert seen["stranger_auth"] is None


def test_post_hidden_from_strangers_is_not_public():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"id": "111", "url": POST_URL})
        return httpx.Response(404)

    result = run(handler)
    assert result.status == "success"
    assert result.public_access is False


def test_bad_token_is_readable():
    result = run(lambda request: httpx.Response(401, json={"error": "invalid token"}))
    assert result.error.startswith("Authentication failed")


def test_rejected_post_shows_reason():
    result = run(
        lambda request: httpx.Response(422, json={"error": "Validation failed: Text too long"})
    )
    assert result.error == "Mastodon rejected the post: Validation failed: Text too long"


def test_missing_token(monkeypatch):
    monkeypatch.setattr(settings, "mastodon_access_token", "")
    assert run(lambda request: httpx.Response(500)).error == "Missing credentials in .env"


def test_missing_server_address(monkeypatch):
    monkeypatch.setattr(settings, "mastodon_base_url", "")
    assert run(lambda request: httpx.Response(500)).error == "Missing credentials in .env"