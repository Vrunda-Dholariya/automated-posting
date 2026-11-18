import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.platforms.telegram import Telegram


@pytest.fixture(autouse=True)
def fake_setup(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "token123")
    monkeypatch.setattr(settings, "telegram_chat_id", "@MyChan")
    monkeypatch.setattr(Telegram, "CHECK_DELAY", 0)


def run(handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await Telegram().publish(client, "Hello https://example.com")

    return asyncio.run(go())


def sent_ok(chat):
    return httpx.Response(200, json={"ok": True, "result": {"message_id": 7, "chat": chat}})


PUBLIC_CHAT = {"id": -1001234567, "username": "MyChan", "type": "channel"}


def test_success_builds_link_and_confirms_public():
    seen = {}

    def handler(request):
        if request.method == "POST":
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return sent_ok(PUBLIC_CHAT)
        assert request.url.path == "/s/MyChan"
        return httpx.Response(200, text='<div data-post="MyChan/7">Hello</div>')

    result = run(handler)
    assert result.status == "success"
    assert result.posted_url == "https://t.me/MyChan/7"
    assert result.public_access is True
    assert seen["path"] == "/bottoken123/sendMessage"
    assert seen["body"]["chat_id"] == "@MyChan"


def test_message_missing_from_preview_is_not_public():
    def handler(request):
        if request.method == "POST":
            return sent_ok(PUBLIC_CHAT)
        return httpx.Response(200, text="<div>nothing here</div>")

    result = run(handler)
    assert result.status == "success"
    assert result.public_access is False


def test_private_channel_gets_member_link_and_is_not_public():
    def handler(request):
        if request.method == "POST":
            return sent_ok({"id": -1001234567, "type": "channel"})
        return httpx.Response(500)

    result = run(handler)
    assert result.status == "success"
    assert result.posted_url == "https://t.me/c/1234567/7"
    assert result.public_access is False


def test_bot_not_admin_shows_telegram_reason():
    result = run(
        lambda request: httpx.Response(
            403, json={"ok": False, "description": "Forbidden: bot is not a member of the channel chat"}
        )
    )
    assert result.error == "Telegram refused the post: Forbidden: bot is not a member of the channel chat"


def test_wrong_channel_shows_telegram_reason():
    result = run(
        lambda request: httpx.Response(
            400, json={"ok": False, "description": "Bad Request: chat not found"}
        )
    )
    assert result.error == "Telegram refused the post: Bad Request: chat not found"


def test_wrong_token_is_readable():
    result = run(lambda request: httpx.Response(401, json={"ok": False, "description": "Unauthorized"}))
    assert result.error.startswith("Authentication failed")


def test_network_error_never_leaks_the_token():
    def handler(request):
        raise httpx.ConnectError(f"cannot reach {request.url}")

    result = run(handler)
    assert result.status == "failed"
    assert result.error == "Network error: ConnectError"
    assert "token123" not in result.error


def test_missing_credentials(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    assert run(lambda request: httpx.Response(500)).error == "Missing credentials in .env"



def test_falls_back_to_telegram_me_when_t_me_is_unreachable():
    def handler(request):
        if request.method == "POST":
            return sent_ok(PUBLIC_CHAT)
        if request.url.host == "t.me":
            raise httpx.ConnectError("connection reset")
        return httpx.Response(200, text='<div data-post="MyChan/7">Hello</div>')

    result = run(handler)
    assert result.status == "success"
    assert result.public_access is True