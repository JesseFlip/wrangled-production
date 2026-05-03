"""Opt-in live test hitting a real WLED on the LAN.

Run with: `uv run pytest -m live`
Skipped by default (see pytest addopts in pyproject.toml).
"""

from __future__ import annotations

from ipaddress import IPv4Address

import httpx
import pytest
from wrangled_contracts import RGB, ColorCommand

from wrangler.pusher import push_command
from wrangler.scanner import ScanOptions, scan
from wrangler.scanner.probe import probe_device

LIVE_IP = "10.0.6.207"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_scan_finds_known_device() -> None:
    devices = await scan(ScanOptions(mdns_timeout=3.0))
    found = [d for d in devices if str(d.ip) == LIVE_IP]
    assert found, (
        f"expected to find WLED at {LIVE_IP}; found instead: {[str(d.ip) for d in devices]}"
    )
    device = found[0]
    assert device.mac
    assert device.led_count > 0


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_push_color_succeeds() -> None:
    async with httpx.AsyncClient() as client:
        device = await probe_device(
            client,
            IPv4Address(LIVE_IP),
            source="mdns",
            timeout=2.0,
        )
        assert device is not None, f"no WLED responding at {LIVE_IP}"

        result = await push_command(
            client,
            device,
            ColorCommand(color=RGB(r=0, g=0, b=255), brightness=1),
        )
    assert result.ok, f"push failed: {result}"
