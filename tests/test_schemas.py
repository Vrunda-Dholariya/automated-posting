import pytest
from pydantic import ValidationError

from app.schemas import PlatformResult, PostRequest, PostResponse


def test_valid_message():
    req = PostRequest(message="Grow your reach today. https://example.com")
    assert "https://example.com" in req.message


def test_link_followed_by_period_is_valid():
    PostRequest(message="Visit https://example.com.")


def test_exactly_200_characters_is_valid():
    PostRequest(message="x" * 180 + " https://example.com")


@pytest.mark.parametrize(
    "bad_message",
    [
        "",
        "   ",
        "No link here",
        "Two links https://a.com and https://b.com",
        "Bad link https://:::",
        "x" * 190 + " https://example.com",
    ],
)
def test_invalid_messages_are_rejected(bad_message):
    with pytest.raises(ValidationError):
        PostRequest(message=bad_message)



def test_ok_result_has_url_and_timestamp():
    result = PlatformResult.ok("Bluesky", "https://bsky.app/x", True)
    assert result.status == "success"
    assert result.error is None
    assert result.date and result.time


def test_failed_result_matches_task_example():
    result = PlatformResult.fail("Platform B", "Authentication failed")
    assert result.model_dump() == {
        "platform": "Platform B",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "Authentication failed",
    }


def test_response_has_expected_shape():
    response = PostResponse(success=True, results=[PlatformResult.fail("A", "boom")])
    assert set(response.model_dump()) == {"success", "results"}