"""The web API: one endpoint, POST /posting."""

import logging

from fastapi import FastAPI

from app.schemas import PostRequest, PostResponse
from app.services.posting_service import post_everywhere

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# httpx logs full request URLs at INFO level, and Telegram's URL contains the
# bot token. Keep those logs quiet so the token can never reach a log file.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

app = FastAPI(
    title="Automated Posting API",
    description=(
        "Send one short message with one link. It is validated, then posted "
        "to several platforms at the same time. Each platform reports its own "
        "result, so one failure never stops the others."
    ),
    version="1.0.0",
)


@app.post(
    "/posting",
    response_model=PostResponse,
    summary="Post a message to all platforms",
)
async def create_posting(request: PostRequest) -> PostResponse:
    return await post_everywhere(request.message)


@app.get("/health", summary="Is the API running?")
async def health() -> dict[str, str]:
    return {"status": "ok"}
