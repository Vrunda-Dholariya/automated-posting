import pytest
from fastapi.testclient import TestClient

from app import main
from app.schemas import PlatformResult, PostResponse

client = TestClient(main.app)


@pytest.fixture
def calls(monkeypatch):
    """Replace the real posting service with a fake that records its input."""
    seen = []

    async def fake_post_everywhere(message):
        seen.append(message)
        return PostResponse(
            success=True,
            results=[PlatformResult.ok("Fake", "https://example.com/1", True)],
        )

    monkeypatch.setattr(main, "post_everywhere", fake_post_everywhere)
    return seen


def test_valid_request_returns_the_report(calls):
    response = client.post("/posting", json={"message": "  Hello https://example.com  "})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["results"][0]["platform"] == "Fake"
    assert body["results"][0]["posted_url"] == "https://example.com/1"
    assert calls == ["Hello https://example.com"]  # spaces were trimmed


@pytest.mark.parametrize(
    "bad_body",
    [
        {"message": ""},
        {"message": "No link here"},
        {"message": "Two https://a.com and https://b.com"},
        {"message": "x" * 250 + " https://example.com"},
        {},
    ],
)
def test_bad_input_is_rejected_and_nothing_is_posted(calls, bad_body):
    response = client.post("/posting", json=bad_body)

    assert response.status_code == 422
    assert calls == []  # the posting service was never reached


def test_validation_error_explains_the_problem(calls):
    response = client.post("/posting", json={"message": "No link here"})
    assert "exactly one link" in response.text


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}