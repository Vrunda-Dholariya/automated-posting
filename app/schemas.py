"""Input rules for the POST /posting endpoint."""

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, TypeAdapter, ValidationError, field_validator
MAX_LENGTH = 200
URL_PATTERN = re.compile(r"https?://\S+")
TRAILING_PUNCTUATION = ".,;:!?)]}\"'"
_url_checker = TypeAdapter(AnyHttpUrl)


def extract_links(text: str) -> list[str]:
    """Return every http(s) link found in the text."""
    return [link.rstrip(TRAILING_PUNCTUATION) for link in URL_PATTERN.findall(text)]


class PostRequest(BaseModel):
    """The JSON body the user sends: {"message": "..."}"""

    message: str

    @field_validator("message")
    @classmethod
    def check_message(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Message must not be empty.")

        if len(value) > MAX_LENGTH:
            raise ValueError(
                f"Message is {len(value)} characters; the limit is {MAX_LENGTH}."
            )

        links = extract_links(value)
        if len(links) != 1:
            raise ValueError(
                f"Message must contain exactly one link starting with "
                f"http:// or https://; found {len(links)}."
            )

        try:
            _url_checker.validate_python(links[0])
        except ValidationError:
            raise ValueError("The link is not a valid URL.") from None

        return value



class PlatformResult(BaseModel):
    """One platform's report card."""

    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = None
    time: str | None = None
    error: str | None = None

    @classmethod
    def ok(cls, platform: str, posted_url: str, public_access: bool) -> "PlatformResult":
        """Build a success result, stamped with the current UTC date and time."""
        now = datetime.now(timezone.utc)
        return cls(
            platform=platform,
            status="success",
            posted_url=posted_url,
            public_access=public_access,
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H:%M:%S"),
        )

    @classmethod
    def fail(cls, platform: str, error: str) -> "PlatformResult":
        """Build a failed result with a readable error."""
        return cls(platform=platform, status="failed", error=error)


class PostResponse(BaseModel):
    """The full reply: overall flag plus one result per platform."""

    success: bool
    results: list[PlatformResult]   