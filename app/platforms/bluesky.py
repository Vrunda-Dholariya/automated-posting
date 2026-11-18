"""Bluesky integration (AT Protocol)."""

import asyncio
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.platforms.base import Platform
from app.schemas import extract_links

API = "https://bsky.social/xrpc"
PUBLIC_API = "https://public.api.bsky.app/xrpc"


class Bluesky(Platform):
    name = "Bluesky"
    INDEX_RETRIES = 3
    INDEX_DELAY = 1.0

    def is_configured(self) -> bool:
        return bool(settings.bluesky_handle and settings.bluesky_app_password)

    async def _send(self, client: httpx.AsyncClient, message: str) -> str:
        # 1. Log in
        login = await client.post(
            f"{API}/com.atproto.server.createSession",
            json={
                "identifier": settings.bluesky_handle,
                "password": settings.bluesky_app_password,
            },
        )
        self.check_response(login)
        session = login.json()

        # 2. Create the post
        created = await client.post(
            f"{API}/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={
                "repo": session["did"],
                "collection": "app.bsky.feed.post",
                "record": self._build_record(message),
            },
        )
        self.check_response(created)

        # 3. Build the public link
        post_id = created.json()["uri"].rsplit("/", 1)[-1]
        return f"https://bsky.app/profile/{session['did']}/post/{post_id}"

    @staticmethod
    def _build_record(message: str) -> dict:
        """Post body, with the link marked so it is clickable."""
        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        facets = []
        for link in extract_links(message):
            start = message.find(link)
            if start == -1:
                continue
            byte_start = len(message[:start].encode("utf-8"))
            facets.append(
                {
                    "index": {
                        "byteStart": byte_start,
                        "byteEnd": byte_start + len(link.encode("utf-8")),
                    },
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
                }
            )
        if facets:
            record["facets"] = facets
        return record

    async def _is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        """Ask Bluesky's public API (no login) whether the post exists."""
        parts = url.rstrip("/").split("/")
        at_uri = f"at://{parts[-3]}/app.bsky.feed.post/{parts[-1]}"

        for attempt in range(self.INDEX_RETRIES):
            if attempt:
                await asyncio.sleep(self.INDEX_DELAY)
            try:
                response = await client.get(
                    f"{PUBLIC_API}/app.bsky.feed.getPosts", params={"uris": at_uri}
                )
                if response.status_code == 200 and response.json().get("posts"):
                    return True
            except (httpx.HTTPError, ValueError):
                pass
        return False