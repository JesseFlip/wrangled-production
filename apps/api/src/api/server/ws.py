"""/ws endpoint — wrangler dial-home channel."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import TypeAdapter, ValidationError
from wrangled_contracts import (
    DevicesChanged,
    Hello,
    Ping,
    Pong,
    Welcome,
    WranglerMessage,
)

from api import __version__

if TYPE_CHECKING:
    from api.server.auth import AuthChecker
    from api.server.hub import Hub

from api.server.connection import WranglerConnection

logger = logging.getLogger(__name__)

_WRANGLER_ADAPTER = TypeAdapter(WranglerMessage)

_HELLO_DEADLINE_SECONDS = 5.0
_PING_INTERVAL_SECONDS = 30.0
_DEAD_AFTER_SECONDS = 70.0


def build_ws_router(hub: Hub, auth: AuthChecker) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket, token: str | None = None) -> None:
        try:
            auth.check_query_token(token)
        except Exception:  # noqa: BLE001
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()

        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=_HELLO_DEADLINE_SECONDS,
            )
        except (TimeoutError, WebSocketDisconnect):
            await websocket.close(code=status.WS_1002_PROTOCOL_ERROR)
            return

        try:
            message = _WRANGLER_ADAPTER.validate_json(raw)
        except ValidationError:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        if not isinstance(message, Hello):
            await websocket.close(code=status.WS_1002_PROTOCOL_ERROR)
            return

        conn = WranglerConnection(
            wrangler_id=message.wrangler_id,
            socket=websocket,
            wrangler_version=message.wrangler_version,
        )
        conn.apply_devices(message.devices)
        await hub.attach(conn)
        await websocket.send_text(
            Welcome(server_version=__version__).model_dump_json(),
        )

        heartbeat_task = asyncio.create_task(_heartbeat(websocket, conn))
        try:
            await _main_loop(websocket, conn, hub)
        finally:
            heartbeat_task.cancel()
            await hub.detach(conn.wrangler_id)

    return router


async def _main_loop(websocket: WebSocket, conn: WranglerConnection, hub: Hub) -> None:
    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return
        try:
            message = _WRANGLER_ADAPTER.validate_json(raw)
        except ValidationError as exc:
            logger.debug("ws %s: invalid message: %s", conn.wrangler_id, exc)
            continue

        if isinstance(message, Pong):
            conn.last_pong_at = datetime.now(tz=UTC)
            continue
        if isinstance(message, DevicesChanged):
            hub.apply_devices(conn.wrangler_id, message.devices)
            continue
        if isinstance(message, Hello):
            logger.debug("ws %s: ignoring repeat Hello", conn.wrangler_id)
            continue

        hub.resolve_response(conn.wrangler_id, message)


async def _heartbeat(websocket: WebSocket, conn: WranglerConnection) -> None:
    while True:
        await asyncio.sleep(_PING_INTERVAL_SECONDS)
        now = datetime.now(tz=UTC)
        if (now - conn.last_pong_at).total_seconds() > _DEAD_AFTER_SECONDS:
            with contextlib.suppress(Exception):
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return
        with contextlib.suppress(Exception):
            await websocket.send_text(Ping().model_dump_json())
