"""GitHub Gist integration."""

from urllib.parse import urlparse

import httpx

from app.config import settings
from app.platforms.base import Platform, PlatformError

API = "https://api.github.com"


class GitHubGist(Platform):
    name = "GitHub Gist"

    def is_configured(self) -> bool:
        return bool(settings.github_gist_token)

    async def _send(self, client: httpx.AsyncClient, message: str) -> str:
        response = await client.post(
            f"{API}/gists",
            headers={
                "Authorization": f"Bearer {settings.github_gist_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": "Posted via the automated posting API",
                "public": True,
                "files": {"message.md": {"content": message}},
            },
        )
        if response.status_code == 422:
            raise PlatformError(f"GitHub rejected the gist: {self.error_text(response)}")
        self.check_response(response)

        try:
            return response.json()["html_url"]
        except (ValueError, KeyError, TypeError):
            raise PlatformError("GitHub replied without a gist URL") from None

    async def _is_public(self, client: httpx.AsyncClient, url: str) -> bool:
        """Ask GitHub for the gist WITHOUT a token, like a stranger."""
        gist_id = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        try:
            response = await client.get(
                f"{API}/gists/{gist_id}",
                headers={"Accept": "application/vnd.github+json"},
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False