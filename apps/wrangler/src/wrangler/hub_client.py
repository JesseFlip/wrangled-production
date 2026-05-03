"""Outbound WS client — wrangler dialing home to api."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx
import websockets
from pydantic import TypeAdapter, ValidationError
from wrangled_contracts import (
    ApiMessage,
    CommandResult,
    DevicesChanged,
    GetState,
    Hello,
    Ping,
    Pong,
    PushResult,
    RelayCommand,
    Rescan,
    SetDeviceName,
    SetDeviceNameResult,
    StateSnapshot,
    Welcome,
)

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any

    from wrangler.server.registry import Registry

from wrangler import __version__
from wrangler.pusher import push_command
from wrangler.scanner import ScanOptions
from wrangler.scanner.probe import probe_device
from wrangler.server.wled_client import WledUnreachableError, fetch_state, set_name

logger = logging.getLogger(__name__)

_API_ADAPTER = TypeAdapter(ApiMessage)

_MIN_BACKOFF = 1.0
_MAX_BACKOFF = 60.0


class HubClient:
    """Maintains an outbound WS connection to apps/api.

    Started as a background task when WRANGLED_API_URL is set. Never
    raises out of run(); always reconnects on failure with exponential backoff.
    """

    def __init__(
        self,
        *,
        api_url: str,
        auth_token: str | None,
        wrangler_id: str,
        registry: Registry,
    ) -> None:
        self._api_url = api_url
        self._auth_token = auth_token
        self._wrangler_id = wrangler_id
        self._registry = registry
        self._socket: websockets.WebSocketClientProtocol | None = None
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    async def run(self) -> None:
        backoff = _MIN_BACKOFF
        while True:
            try:
                await self._connect_once()
                backoff = _MIN_BACKOFF
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.info("hub_client: connection lost: %s (retry in %.1fs)", exc, backoff)
            finally:
                self._socket = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF)

    async def notify_devices_changed(self) -> None:
        """Push a DevicesChanged to api if connected."""
        if self._socket is None:
            return
        msg = DevicesChanged(devices=self._registry.all())
        try:
            await self._send(msg.model_dump_json())
        except Exception:  # noqa: BLE001
            logger.debug("hub_client: notify_devices_changed failed; will retry on reconnect")

    async def _send(self, raw: str) -> None:
        async with self._lock:
            sock = self._socket
            if sock is None:
                return
            await sock.send(raw)

    async def _connect_once(self) -> None:
        url = self._api_url
        if self._auth_token:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}token={self._auth_token}"
        async with websockets.connect(url) as sock:
            self._socket = sock
            hello = Hello(
                wrangler_id=self._wrangler_id,
                wrangler_version=__version__,
                devices=self._registry.all(),
            )
            await sock.send(hello.model_dump_json())
            async for raw in sock:
                await self._handle(raw)

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        """Create a task and keep a strong reference to prevent GC."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            message = _API_ADAPTER.validate_json(raw)
        except ValidationError as exc:
            logger.debug("hub_client: invalid message: %s", exc)
            return

        if isinstance(message, Welcome):
            logger.info("hub_client: connected to api (server_version=%s)", message.server_version)
            return
        if isinstance(message, Ping):
            await self._send(Pong().model_dump_json())
            return
        if isinstance(message, RelayCommand):
            self._spawn(self._handle_command(message))
            return
        if isinstance(message, GetState):
            self._spawn(self._handle_get_state(message))
            return
        if isinstance(message, Rescan):
            self._spawn(self._handle_rescan())
            return
        if isinstance(message, SetDeviceName):
            self._spawn(self._handle_set_device_name(message))

    async def _handle_command(self, msg: RelayCommand) -> None:
        device = self._registry.get(msg.mac)
        if device is None:
            result = PushResult(ok=False, error=f"unknown device on this wrangler: {msg.mac}")
        else:
            async with httpx.AsyncClient() as client:
                result = await push_command(client, device, msg.command)
        await self._send(
            CommandResult(request_id=msg.request_id, result=result).model_dump_json(),
        )

    async def _handle_get_state(self, msg: GetState) -> None:
        device = self._registry.get(msg.mac)
        if device is None:
            snapshot = StateSnapshot(
                request_id=msg.request_id,
                mac=msg.mac,
                state=None,
                error=f"unknown device on this wrangler: {msg.mac}",
            )
        else:
            async with httpx.AsyncClient() as client:
                try:
                    state = await fetch_state(client, device)
                    snapshot = StateSnapshot(request_id=msg.request_id, mac=msg.mac, state=state)
                except WledUnreachableError as exc:
                    snapshot = StateSnapshot(
                        request_id=msg.request_id,
                        mac=msg.mac,
                        state=None,
                        error=str(exc),
                    )
        await self._send(snapshot.model_dump_json())

    async def _handle_rescan(self) -> None:
        await self._registry.scan(ScanOptions(mdns_timeout=2.0))

    async def _handle_set_device_name(self, msg: SetDeviceName) -> None:
        device = self._registry.get(msg.mac)
        if device is None:
            result = SetDeviceNameResult(
                request_id=msg.request_id,
                error=f"unknown: {msg.mac}",
            )
        else:
            async with httpx.AsyncClient() as client:
                try:
                    await set_name(client, device, msg.name)
                    refreshed = await probe_device(
                        client,
                        device.ip,
                        source="mdns",
                        timeout=2.0,
                    )
                    result = SetDeviceNameResult(
                        request_id=msg.request_id,
                        device=refreshed,
                    )
                    if refreshed:
                        self._registry.put(refreshed)
                except WledUnreachableError as exc:
                    result = SetDeviceNameResult(
                        request_id=msg.request_id,
                        error=str(exc),
                    )
        await self._send(result.model_dump_json())
