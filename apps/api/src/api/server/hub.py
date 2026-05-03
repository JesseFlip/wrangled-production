"""Connection manager + command routing."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from wrangled_contracts import (
    ApiMessage,
    Command,
    CommandResult,
    GetState,
    PushResult,
    RelayCommand,
    Rescan,
    SetDeviceName,
    SetDeviceNameResult,
    StateSnapshot,
    WledDevice,
    WranglerMessage,
)

from api.server.connection import WranglerConnection  # noqa: TC001

logger = logging.getLogger(__name__)


class NoWranglerForDeviceError(LookupError):
    """Raised when a command targets a MAC that no connected wrangler owns."""


class WranglerTimeoutError(TimeoutError):
    """Raised when a wrangler doesn't respond within the deadline."""


class WranglerDisconnectedError(RuntimeError):
    """Raised when a wrangler disconnects while a request is outstanding."""


async def _send(conn: WranglerConnection, msg: ApiMessage) -> None:
    await conn.socket.send_text(msg.model_dump_json())


class Hub:
    """Holds connections and routes commands."""

    def __init__(self) -> None:
        self._conns: dict[str, WranglerConnection] = {}
        self._ownership: dict[str, str] = {}  # mac → wrangler_id

    # lifecycle -------------------------------------------------------

    async def attach(self, conn: WranglerConnection) -> None:
        existing = self._conns.pop(conn.wrangler_id, None)
        if existing is not None:
            logger.warning(
                "attach: wrangler %s reconnected; dropping stale connection",
                conn.wrangler_id,
            )
            self._cancel_pending(existing, reason="replaced by new connection")
        self._conns[conn.wrangler_id] = conn
        self.apply_devices(conn.wrangler_id, list(conn.devices.values()))

    async def detach(self, wrangler_id: str) -> None:
        conn = self._conns.pop(wrangler_id, None)
        if conn is None:
            return
        self._cancel_pending(conn, reason="wrangler disconnected")
        for mac, owner in list(self._ownership.items()):
            if owner == wrangler_id:
                self._ownership.pop(mac, None)

    def _cancel_pending(self, conn: WranglerConnection, *, reason: str) -> None:
        for fut in conn.pending.values():
            if not fut.done():
                fut.set_exception(WranglerDisconnectedError(reason))
        conn.pending.clear()

    # device / ownership ---------------------------------------------

    def apply_devices(self, wrangler_id: str, devices: list[WledDevice]) -> None:
        conn = self._conns.get(wrangler_id)
        if conn is None:
            return
        conn.apply_devices(devices)
        for dev in devices:
            current = self._ownership.get(dev.mac)
            if current is not None and current != wrangler_id:
                logger.warning(
                    "device %s now owned by %s (was %s)",
                    dev.mac,
                    wrangler_id,
                    current,
                )
            self._ownership[dev.mac] = wrangler_id

    def find_device(self, mac: str) -> WledDevice | None:
        owner = self._ownership.get(mac)
        if owner is None:
            return None
        conn = self._conns.get(owner)
        return conn.devices.get(mac) if conn else None

    def all_devices(self) -> list[WledDevice]:
        seen: dict[str, WledDevice] = {
            mac: dev
            for conn in self._conns.values()
            for mac, dev in conn.devices.items()
            if self._ownership.get(mac) == conn.wrangler_id
        }
        return sorted(seen.values(), key=lambda d: int(d.ip))

    def wranglers_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "wrangler_id": c.wrangler_id,
                "wrangler_version": c.wrangler_version,
                "connected_at": c.connected_at.isoformat(),
                "last_pong_at": c.last_pong_at.isoformat(),
                "device_count": len(c.devices),
            }
            for c in self._conns.values()
        ]

    # request/response ------------------------------------------------

    async def send_command(
        self,
        mac: str,
        command: Command,
        *,
        timeout: float = 8.0,  # noqa: ASYNC109
    ) -> PushResult:
        owner_id = self._ownership.get(mac)
        if owner_id is None or owner_id not in self._conns:
            msg = f"no wrangler owns {mac}"
            raise NoWranglerForDeviceError(msg)
        conn = self._conns[owner_id]
        request_id = uuid.uuid4().hex
        future: asyncio.Future[PushResult] = asyncio.get_event_loop().create_future()
        conn.pending[request_id] = future
        await _send(conn, RelayCommand(request_id=request_id, mac=mac, command=command))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            conn.pending.pop(request_id, None)
            msg = f"wrangler {conn.wrangler_id} did not respond within {timeout}s"
            raise WranglerTimeoutError(msg) from exc

    async def get_state(
        self,
        mac: str,
        *,
        timeout: float = 3.0,  # noqa: ASYNC109
    ) -> dict:
        owner_id = self._ownership.get(mac)
        if owner_id is None or owner_id not in self._conns:
            msg = f"no wrangler owns {mac}"
            raise NoWranglerForDeviceError(msg)
        conn = self._conns[owner_id]
        request_id = uuid.uuid4().hex
        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        conn.pending[request_id] = future
        await _send(conn, GetState(request_id=request_id, mac=mac))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            conn.pending.pop(request_id, None)
            msg = f"wrangler {conn.wrangler_id} did not respond within {timeout}s"
            raise WranglerTimeoutError(msg) from exc

    async def send_rename(
        self,
        mac: str,
        name: str,
        *,
        timeout: float = 5.0,  # noqa: ASYNC109
    ) -> WledDevice:
        owner_id = self._ownership.get(mac)
        if owner_id is None or owner_id not in self._conns:
            msg = f"no wrangler owns {mac}"
            raise NoWranglerForDeviceError(msg)
        conn = self._conns[owner_id]
        request_id = uuid.uuid4().hex
        future: asyncio.Future[WledDevice] = asyncio.get_event_loop().create_future()
        conn.pending[request_id] = future
        await _send(conn, SetDeviceName(request_id=request_id, mac=mac, name=name))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            conn.pending.pop(request_id, None)
            msg = f"wrangler {conn.wrangler_id} did not respond within {timeout}s"
            raise WranglerTimeoutError(msg) from exc

    async def rescan_all(self, *, grace: float = 2.0) -> list[WledDevice]:
        if not self._conns:
            return []
        for conn in list(self._conns.values()):
            await _send(conn, Rescan())
        await asyncio.sleep(grace)
        return self.all_devices()

    # inbound message resolution -------------------------------------

    def resolve_response(
        self,
        wrangler_id: str,
        message: WranglerMessage,
    ) -> None:
        conn = self._conns.get(wrangler_id)
        if conn is None:
            return
        if isinstance(message, CommandResult):
            fut = conn.pending.pop(message.request_id, None)
            if fut and not fut.done():
                fut.set_result(message.result)
        elif isinstance(message, StateSnapshot):
            fut = conn.pending.pop(message.request_id, None)
            if fut and not fut.done():
                if message.state is not None:
                    fut.set_result(message.state)
                else:
                    fut.set_exception(
                        RuntimeError(message.error or "wrangler reported unreachable"),
                    )
        elif isinstance(message, SetDeviceNameResult):
            fut = conn.pending.pop(message.request_id, None)
            if fut and not fut.done():
                if message.device is not None:
                    self.apply_devices(conn.wrangler_id, [message.device])
                    fut.set_result(message.device)
                else:
                    fut.set_exception(
                        RuntimeError(message.error or "wrangler reported rename failure"),
                    )
