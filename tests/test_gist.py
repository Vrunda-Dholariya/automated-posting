import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.platforms.gist import GitHubGist

GIST_URL = "https://gist.github.com/me/abc123"


@pytest.fixture(autouse=True)
def fake_token(monkeypatch):
    monkeypatch.setattr(settings, "github_gist_token", "ghp_fake")


def run(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await GitHubGist().publish(client, "Hello https://example.com")

    return asyncio.run(go())


def test_success_creates_public_gist_and_stranger_check_has_no_token():
    seen = {}

    def handler(request):
        if request.method == "POST":
            seen["auth"] = request.headers["Authorization"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(201, json={"html_url": GIST_URL})
        seen["stranger_auth"] = request.headers.get("Authorization")
        assert request.url.path == "/gists/abc123"
        return httpx.Response(200, json={"id": "abc123"})

    result = run(handler)
    assert result.status == "success"
    assert result.posted_url == GIST_URL
    assert result.public_access is True
    assert seen["auth"] == "Bearer ghp_fake"
    assert seen["body"]["public"] is True
    assert seen["body"]["files"]["message.md"]["content"] == "Hello https://example.com"
    assert seen["stranger_auth"] is None


def test_gist_not_visible_to_strangers_is_not_public():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(201, json={"html_url": GIST_URL})
        return httpx.Response(404)

    result = run(handler)
    assert result.status == "success"
    assert result.public_access is False


def test_bad_token_is_readable():
    result = run(lambda request: httpx.Response(401, json={"message": "Bad credentials"}))
    assert result.status == "failed"
    assert result.error.startswith("Authentication failed")


def test_token_without_gist_permission_is_readable():
    result = run(lambda request: httpx.Response(403, json={"message": "Forbidden"}))
    assert result.error.startswith("Authentication failed")


def test_rejected_gist_shows_reason():
    result = run(lambda request: httpx.Response(422, json={"error": "Validation Failed"}))
    assert result.error == "GitHub rejected the gist: Validation Failed"


def test_missing_token(monkeypatch):
    monkeypatch.setattr(settings, "github_gist_token", "")
    assert run(lambda request: httpx.Response(500)).error == "Missing credentials in .env"