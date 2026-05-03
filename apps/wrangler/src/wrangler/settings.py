"""Runtime settings loaded from environment."""

from __future__ import annotations

import socket

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WranglerSettings(BaseSettings):
    """Environment-driven configuration for the wrangler agent."""

    model_config = SettingsConfigDict(env_prefix="WRANGLED_", env_file=".env", extra="ignore")

    api_url: str = "wss://wrangled.lumbergh.dev/ws"
    auth_token: str | None = None
    wrangler_id: str = Field(default_factory=socket.gethostname)

    mdns_timeout_seconds: float = 3.0
    probe_timeout_seconds: float = 2.0
    probe_concurrency: int = 32
