"""Concurrent IP-range sweep: probe every host in a subnet for WLED."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable  # noqa: TC003
from ipaddress import IPv4Address, IPv4Network  # noqa: TC003
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from wrangled_contracts import WledDevice

from wrangler.scanner.probe import probe_device


async def sweep_subnet(
    subnet: IPv4Network,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
    concurrency: int = 32,
) -> list[WledDevice]:
    """Probe every host in `subnet`, return the WLED devices found, deduped by MAC."""
    return await sweep_hosts(subnet.hosts(), timeout=timeout, concurrency=concurrency)


async def sweep_hosts(
    hosts: Iterable[IPv4Address],
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
    concurrency: int = 32,
) -> list[WledDevice]:
    """Probe each host concurrently. Dedupe by MAC, sort by IP."""
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:

        async def _one(ip: IPv4Address) -> WledDevice | None:
            async with sem:
                return await probe_device(client, ip, source="sweep", timeout=timeout)

        results = await asyncio.gather(*(_one(ip) for ip in hosts))

    by_mac: dict[str, WledDevice] = {}
    for device in results:
        if device is None:
            continue
        by_mac.setdefault(device.mac, device)
    return sorted(by_mac.values(), key=lambda d: int(d.ip))
