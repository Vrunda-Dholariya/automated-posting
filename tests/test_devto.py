import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.platforms.devto import DevTo


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    monkeypatch.setattr(settings, "devto_api_key", "secret-key")


def run(handler, message="Hello world https://example.com"):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await DevTo().publish(client, message)

    return asyncio.run(go())


def test_success_sends_key_and_confirms_public():
    seen = {}

    def handler(request):
        if request.method == "POST":
            seen["key"] = request.headers["api-key"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(201, json={"id": 1, "url": "https://dev.to/me/hello-123"})
        assert request.url.path == "/api/articles/me/hello-123"
        return httpx.Response(200, json={"id": 1})

    result = run(handler)
    assert result.status == "success"
    assert result.posted_url == "https://dev.to/me/hello-123"
    assert result.public_access is True
    assert seen["key"] == "secret-key"
    assert seen["body"]["article"]["published"] is True
    assert seen["body"]["article"]["title"] == "Hello world"


def test_not_found_publicly_means_not_public():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(201, json={"url": "https://dev.to/me/hello-123"})
        return httpx.Response(404)

    result = run(handler)
    assert result.status == "success"
    assert result.public_access is False


def test_wrong_key_is_readable():
    result = run(lambda request: httpx.Response(401, json={"error": "unauthorized"}))
    assert result.status == "failed"
    assert result.error.startswith("Authentication failed")


def test_rejected_post_shows_devto_reason():
    result = run(
        lambda request: httpx.Response(422, json={"error": "Title is too long", "status": 422})
    )
    assert result.error == "Dev.to rejected the post: Title is too long"


def test_missing_key(monkeypatch):
    monkeypatch.setattr(settings, "devto_api_key", "")
    result = run(lambda request: httpx.Response(500))
    assert result.error == "Missing credentials in .env"


def test_title_rules():
    assert DevTo._make_title("Grow your reach. https://example.com") == "Grow your reach."
    assert DevTo._make_title("https://example.com") == "New post"
    long_title = DevTo._make_title("word " * 50 + "https://example.com")
    assert len(long_title) <= 80 and long_title.endswith("…")