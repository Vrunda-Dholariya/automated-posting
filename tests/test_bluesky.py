import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.platforms.bluesky import Bluesky

DID = "did:plc:abc123"


@pytest.fixture(autouse=True)
def fake_setup(monkeypatch):
    monkeypatch.setattr(settings, "bluesky_handle", "me.bsky.social")
    monkeypatch.setattr(settings, "bluesky_app_password", "pw")
    monkeypatch.setattr(Bluesky, "INDEX_DELAY", 0)


def happy_handler(captured, posts=None):
    posts = [{"uri": "x"}] if posts is None else posts

    def handler(request):
        path = request.url.path
        if path.endswith("createSession"):
            return httpx.Response(200, json={"accessJwt": "tok", "did": DID})
        if path.endswith("createRecord"):
            captured.update(json.loads(request.content))
            return httpx.Response(
                200, json={"uri": f"at://{DID}/app.bsky.feed.post/3kxyz", "cid": "c"}
            )
        if path.endswith("getPosts"):
            return httpx.Response(200, json={"posts": posts})
        return httpx.Response(404)

    return handler


def run(message, handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await Bluesky().publish(client, message)

    return asyncio.run(go())


def test_success_builds_url_and_confirms_public():
    result = run("Hello https://example.com", happy_handler({}))
    assert result.status == "success"
    assert result.posted_url == f"https://bsky.app/profile/{DID}/post/3kxyz"
    assert result.public_access is True


def test_link_marker_uses_byte_positions():
    captured = {}
    message = "Hi 🚀 https://example.com"
    run(message, happy_handler(captured))
    index = captured["record"]["facets"][0]["index"]
    marked = message.encode("utf-8")[index["byteStart"]:index["byteEnd"]]
    assert marked.decode() == "https://example.com"


def test_wrong_password_is_readable():
    def handler(request):
        return httpx.Response(401, json={"error": "AuthenticationRequired"})

    result = run("Hello https://example.com", handler)
    assert result.status == "failed"
    assert result.error.startswith("Authentication failed")


def test_post_not_found_means_not_public():
    result = run("Hello https://example.com", happy_handler({}, posts=[]))
    assert result.status == "success"
    assert result.public_access is False


def test_missing_credentials(monkeypatch):
    monkeypatch.setattr(settings, "bluesky_handle", "")
    result = run("Hello https://example.com", happy_handler({}))
    assert result.error == "Missing credentials in .env"