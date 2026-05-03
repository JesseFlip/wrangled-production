"""SSE command event bus and /api/stream endpoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from api.server.auth import AuthChecker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


# ── Event model ──────────────────────────────────────────────────────


class CommandEvent(BaseModel):
    """A single command event broadcast over SSE."""

    who: str
    source: str
    command_kind: str
    content: str = ""
    target: str = ""
    result: str = ""
    flag: bool = False
    flag_reason: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


# ── Pub/sub bus ──────────────────────────────────────────────────────


class CommandEventBus:
    """Broadcast CommandEvents to any number of SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[CommandEvent]] = []

    def publish(self, event: CommandEvent) -> None:
        dead: list[asyncio.Queue] = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            self._subscribers.remove(queue)

    async def subscribe(self) -> AsyncIterator[CommandEvent]:
        queue: asyncio.Queue[CommandEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._subscribers.remove(queue)


# ── Router factory ───────────────────────────────────────────────────


def build_stream_router(bus: CommandEventBus, auth: AuthChecker) -> APIRouter:
    """Return an APIRouter with the SSE stream endpoint."""
    router = APIRouter()

    @router.get("/api/stream")
    async def stream(
        token: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> EventSourceResponse:
        # SSE EventSource can't set headers, so accept token as query param too
        if authorization:
            auth.check_header(authorization)
        else:
            auth.check_query_token(token)

        async def _generate() -> AsyncIterator[dict[str, str]]:
            async for event in bus.subscribe():
                yield {"event": "command", "data": event.model_dump_json()}

        return EventSourceResponse(_generate())

    return router
