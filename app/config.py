"""Loads secrets and settings from the .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting the app needs. Values come from .env."""

    # Bluesky
    bluesky_handle: str = ""
    bluesky_app_password: str = ""

    # Dev.to
    devto_api_key: str = ""

    # Mastodon
    mastodon_base_url: str = "https://mastodon.social"
    mastodon_access_token: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # GitHub Gist
    github_gist_token: str = ""

    # Discord (optional)
    discord_webhook_url: str = ""

    # Shared settings
    request_timeout: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()