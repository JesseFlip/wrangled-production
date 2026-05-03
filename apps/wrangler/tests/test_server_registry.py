"""Tests for wrangler.server.registry."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest
from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions
from wrangler.server.registry import Registry


def _dev(mac: str, ip: str, name: str) -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name=name,
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_registry_starts_empty() -> None:
    r = Registry(scanner=AsyncMock())
    assert r.all() == []
    assert r.get("aa:bb:cc:dd:ee:ff") is None


@pytest.mark.asyncio
async def test_registry_scan_populates_map() -> None:
    fake_scan = AsyncMock(return_value=[_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")])
    r = Registry(scanner=fake_scan)
    devices = await r.scan(ScanOptions(mdns_timeout=0.01))
    assert len(devices) == 1
    assert r.get("aa:bb:cc:dd:ee:01") is not None
    assert len(r.all()) == 1


@pytest.mark.asyncio
async def test_registry_scan_replaces_previous() -> None:
    first = [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")]
    second = [_dev("aa:bb:cc:dd:ee:02", "10.0.6.2", "B")]
    fake_scan = AsyncMock(side_effect=[first, second])
    r = Registry(scanner=fake_scan)
    await r.scan(ScanOptions(mdns_timeout=0.01))
    await r.scan(ScanOptions(mdns_timeout=0.01))
    macs = [d.mac for d in r.all()]
    assert macs == ["aa:bb:cc:dd:ee:02"]


@pytest.mark.asyncio
async def test_registry_concurrent_scans_serialize() -> None:
    calls = 0

    async def slow_scan(_opts: ScanOptions) -> list[WledDevice]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")]

    r = Registry(scanner=slow_scan)
    a, b = await asyncio.gather(
        r.scan(ScanOptions(mdns_timeout=0.01)),
        r.scan(ScanOptions(mdns_timeout=0.01)),
    )
    assert a == b
    assert calls == 2  # both awaited serially — not at the same time


@pytest.mark.asyncio
async def test_registry_put_replaces_single_device() -> None:
    r = Registry(scanner=AsyncMock(return_value=[]))
    await r.scan(ScanOptions(mdns_timeout=0.01))  # empty result
    r.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A-renamed"))
    assert r.get("aa:bb:cc:dd:ee:01").name == "A-renamed"


@pytest.mark.asyncio
async def test_registry_notifies_observers_on_scan() -> None:
    fake_scan = AsyncMock(return_value=[_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")])
    r = Registry(scanner=fake_scan)

    events: list[str] = []

    async def observer() -> None:
        events.append("notified")

    r.on_changed(observer)
    await r.scan(ScanOptions(mdns_timeout=0.01))
    assert events == ["notified"]


@pytest.mark.asyncio
async def test_registry_notifies_observers_on_put() -> None:
    r = Registry(scanner=AsyncMock())

    events: list[str] = []

    async def observer() -> None:
        events.append("put")

    r.on_changed(observer)
    r.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A"))
    # put schedules via create_task; let the loop drain.
    await asyncio.sleep(0)
    assert events == ["put"]


@pytest.mark.asyncio
async def test_registry_observer_failure_isolated() -> None:
    r = Registry(scanner=AsyncMock(return_value=[]))

    calls: list[str] = []

    async def bad() -> None:
        calls.append("bad")
        msg = "boom"
        raise RuntimeError(msg)

    async def good() -> None:
        calls.append("good")

    r.on_changed(bad)
    r.on_changed(good)
    await r.scan(ScanOptions(mdns_timeout=0.01))
    assert calls == ["bad", "good"]
