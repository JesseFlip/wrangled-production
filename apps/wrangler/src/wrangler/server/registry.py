"""In-memory registry of discovered WLED devices, with serialized scans."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions

logger = logging.getLogger(__name__)

ScanFn = Callable[[ScanOptions], Awaitable[list[WledDevice]]]
ObserverFn = Callable[[], Awaitable[None]]


class Registry:
    """Tracks the most recent scan result, keyed by MAC."""

    def __init__(self, *, scanner: ScanFn) -> None:
        self._scanner = scanner
        self._devices: dict[str, WledDevice] = {}
        self._lock = asyncio.Lock()
        self._observers: list[ObserverFn] = []

    def on_changed(self, cb: ObserverFn) -> None:
        """Register an async callback fired after each scan/put."""
        self._observers.append(cb)

    async def _notify(self) -> None:
        for cb in self._observers:
            try:
                await cb()
            except Exception:
                logger.exception("observer failed")

    def _schedule_notify(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._notify())
        # Keep a strong reference so the task is not garbage-collected.
        self._pending_notify = task

    def all(self) -> list[WledDevice]:
        """Return all known devices, sorted by IP."""
        return sorted(self._devices.values(), key=lambda d: int(d.ip))

    def get(self, mac: str) -> WledDevice | None:
        return self._devices.get(mac)

    def put(self, device: WledDevice) -> None:
        """Replace (or add) a single device in-place."""
        self._devices[device.mac] = device
        self._schedule_notify()

    async def scan(self, opts: ScanOptions) -> list[WledDevice]:
        """Run a fresh scan; replace the full registry with the results.

        For each discovered device, the original ``discovered_at`` timestamp
        is preserved when the MAC was already known — this keeps the value
        stable across back-to-back scans of the same set of devices.
        """
        async with self._lock:
            discovered = await self._scanner(opts)
            new_map: dict[str, WledDevice] = {}
            for d in discovered:
                if d.mac in self._devices:
                    d.discovered_at = self._devices[d.mac].discovered_at
                new_map[d.mac] = d
            self._devices = new_map
        await self._notify()
        return self.all()
