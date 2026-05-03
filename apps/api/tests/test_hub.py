"""Tests for api.server.hub (Hub + routing, no WS yet)."""

from __future__ import annotations

import asyncio
import json as _json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest
from wrangled_contracts import (
    RGB,
    ColorCommand,
    CommandResult,
    DevicesChanged,
    Hello,
    PushResult,
    SetDeviceNameResult,
    StateSnapshot,
    WledDevice,
)

from api.server.connection import WranglerConnection
from api.server.hub import Hub, NoWranglerForDeviceError, WranglerTimeoutError


def _dev(mac: str, ip: str) -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name=f"WLED-{ip}",
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


def _conn(wrangler_id: str, devices: list[WledDevice]) -> WranglerConnection:
    conn = WranglerConnection(
        wrangler_id=wrangler_id,
        socket=AsyncMock(),
        wrangler_version="0.1.0",
    )
    conn.apply_devices(devices)
    return conn


@pytest.mark.asyncio
async def test_attach_registers_ownership() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    assert hub.find_device("aa:bb:cc:dd:ee:01") is not None
    assert hub.all_devices() == [conn.devices["aa:bb:cc:dd:ee:01"]]
    assert hub.wranglers_summary()[0]["wrangler_id"] == "pi-a"


@pytest.mark.asyncio
async def test_detach_removes_devices() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)
    await hub.detach("pi-a")

    assert hub.find_device("aa:bb:cc:dd:ee:01") is None
    assert hub.all_devices() == []


@pytest.mark.asyncio
async def test_send_command_resolves_when_result_arrives() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    sent: list[str] = []
    conn.socket.send_text = AsyncMock(side_effect=sent.append)

    task = asyncio.create_task(
        hub.send_command("aa:bb:cc:dd:ee:01", ColorCommand(color=RGB(r=1, g=2, b=3))),
    )
    await asyncio.sleep(0)

    payload = _json.loads(sent[-1])
    request_id = payload["request_id"]

    hub.resolve_response(
        "pi-a",
        CommandResult(request_id=request_id, result=PushResult(ok=True, status=200)),
    )
    result = await task
    assert result.ok is True


@pytest.mark.asyncio
async def test_send_command_times_out() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    conn.socket.send_text = AsyncMock()
    await hub.attach(conn)

    with pytest.raises(WranglerTimeoutError):
        await hub.send_command(
            "aa:bb:cc:dd:ee:01",
            ColorCommand(color=RGB(r=0, g=0, b=0)),
            timeout=0.05,
        )


@pytest.mark.asyncio
async def test_send_command_unknown_mac() -> None:
    hub = Hub()
    with pytest.raises(NoWranglerForDeviceError):
        await hub.send_command(
            "zz:zz:zz:zz:zz:zz",
            ColorCommand(color=RGB(r=0, g=0, b=0)),
        )


@pytest.mark.asyncio
async def test_get_state_resolves_when_snapshot_arrives() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    sent: list[str] = []
    conn.socket.send_text = AsyncMock(side_effect=sent.append)

    task = asyncio.create_task(hub.get_state("aa:bb:cc:dd:ee:01"))
    await asyncio.sleep(0)

    payload = _json.loads(sent[-1])
    request_id = payload["request_id"]

    hub.resolve_response(
        "pi-a",
        StateSnapshot(
            request_id=request_id,
            mac="aa:bb:cc:dd:ee:01",
            state={"on": True, "bri": 80},
        ),
    )
    result = await task
    assert result == {"on": True, "bri": 80}


@pytest.mark.asyncio
async def test_apply_devices_handles_ownership_conflict() -> None:
    hub = Hub()
    a = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    b = _conn("pi-b", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.2")])
    await hub.attach(a)
    await hub.attach(b)

    device = hub.find_device("aa:bb:cc:dd:ee:01")
    assert device is not None
    assert str(device.ip) == "10.0.6.2"


@pytest.mark.asyncio
async def test_apply_devices_updates_on_devices_changed() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    new_dev = _dev("aa:bb:cc:dd:ee:01", "10.0.6.9")
    msg = DevicesChanged(devices=[new_dev])
    hub.apply_devices("pi-a", msg.devices)

    found = hub.find_device("aa:bb:cc:dd:ee:01")
    assert str(found.ip) == "10.0.6.9"


@pytest.mark.asyncio
async def test_send_rename_resolves_when_result_arrives() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    sent: list[str] = []
    conn.socket.send_text = AsyncMock(side_effect=sent.append)

    task = asyncio.create_task(hub.send_rename("aa:bb:cc:dd:ee:01", "NewName"))
    await asyncio.sleep(0)

    payload = _json.loads(sent[-1])
    request_id = payload["request_id"]

    renamed_dev = _dev("aa:bb:cc:dd:ee:01", "10.0.6.1")
    hub.resolve_response(
        "pi-a",
        SetDeviceNameResult(request_id=request_id, device=renamed_dev),
    )
    result = await task
    assert result.mac == "aa:bb:cc:dd:ee:01"


@pytest.mark.asyncio
async def test_send_rename_times_out() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    conn.socket.send_text = AsyncMock()
    await hub.attach(conn)

    with pytest.raises(WranglerTimeoutError):
        await hub.send_rename("aa:bb:cc:dd:ee:01", "NewName", timeout=0.05)


def test_hello_message_used_to_build_connection() -> None:
    hello = Hello(wrangler_id="pi-x", wrangler_version="0.1.0", devices=[])
    assert hello.wrangler_id == "pi-x"
