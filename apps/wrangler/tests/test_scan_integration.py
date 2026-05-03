"""Integration tests for the scan() orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv4Network
from unittest.mock import AsyncMock, patch

import pytest
from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions, scan


def _device(ip: str, mac: str, via: str) -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name=f"WLED-{ip}",
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via=via,  # type: ignore[arg-type]
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_scan_prefers_mdns_and_skips_sweep_when_found() -> None:
    with (
        patch(
            "wrangler.scanner.discover_via_mdns",
            AsyncMock(return_value={IPv4Address("10.0.6.207")}),
        ),
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[]),
        ) as mock_sweep,
        patch(
            "wrangler.scanner.probe_device",
            AsyncMock(return_value=_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "mdns")),
        ),
    ):
        devices = await scan(ScanOptions(mdns_timeout=0.01))

    assert len(devices) == 1
    assert devices[0].discovered_via == "mdns"
    mock_sweep.assert_not_awaited()


@pytest.mark.asyncio
async def test_scan_falls_back_to_sweep_when_mdns_empty() -> None:
    with (
        patch(
            "wrangler.scanner.discover_via_mdns",
            AsyncMock(return_value=set()),
        ),
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "sweep")]),
        ) as mock_sweep,
        patch(
            "wrangler.scanner.detect_default_subnet",
            return_value=IPv4Network("10.0.6.0/24"),
        ),
    ):
        devices = await scan(ScanOptions(mdns_timeout=0.01))

    assert len(devices) == 1
    assert devices[0].discovered_via == "sweep"
    mock_sweep.assert_awaited_once()


@pytest.mark.asyncio
async def test_scan_force_sweep_runs_both() -> None:
    with (
        patch(
            "wrangler.scanner.discover_via_mdns",
            AsyncMock(return_value={IPv4Address("10.0.6.207")}),
        ),
        patch(
            "wrangler.scanner.probe_device",
            AsyncMock(return_value=_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "mdns")),
        ),
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[_device("10.0.6.208", "11:22:33:44:55:66", "sweep")]),
        ) as mock_sweep,
        patch(
            "wrangler.scanner.detect_default_subnet",
            return_value=IPv4Network("10.0.6.0/24"),
        ),
    ):
        devices = await scan(ScanOptions(mdns_timeout=0.01, sweep=True))

    assert len(devices) == 2
    mock_sweep.assert_awaited_once()


@pytest.mark.asyncio
async def test_scan_no_mdns_is_sweep_only() -> None:
    with (
        patch("wrangler.scanner.discover_via_mdns", AsyncMock(return_value=set())) as mock_mdns,
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "sweep")]),
        ),
        patch(
            "wrangler.scanner.detect_default_subnet",
            return_value=IPv4Network("10.0.6.0/24"),
        ),
    ):
        devices = await scan(ScanOptions(use_mdns=False))

    assert len(devices) == 1
    mock_mdns.assert_not_awaited()
