"""Per-wrangler connection state held by the Hub."""

from __future__ import annotations

import asyncio  # noqa: TC003
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from wrangled_contracts import WledDevice  # noqa: TC002


@dataclass
class WranglerConnection:
    wrangler_id: str
    socket: Any  # WebSocket at runtime, AsyncMock in tests
    wrangler_version: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    last_pong_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    devices: dict[str, WledDevice] = field(default_factory=dict)
    pending: dict[str, asyncio.Future] = field(default_factory=dict)

    def apply_devices(self, devices: list[WledDevice]) -> None:
        self.devices = {d.mac: d for d in devices}
