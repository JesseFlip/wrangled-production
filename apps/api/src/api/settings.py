"""Env-driven configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Runtime settings for the api process."""

    model_config = SettingsConfigDict(env_prefix="WRANGLED_", env_file=".env", extra="ignore")

    auth_token: str | None = None
    host: str = "127.0.0.1"
    port: int = 8500


class DiscordSettings(BaseSettings):
    """Discord bot settings (separate prefix so DISCORD_BOT_TOKEN works)."""

    model_config = SettingsConfigDict(env_prefix="DISCORD_", env_file=".env", extra="ignore")

    bot_token: str | None = None
    guild_id: int | None = None  # single guild (legacy); prefer guild_ids
    guild_ids: str | None = None  # comma-separated guild IDs for multi-server sync
