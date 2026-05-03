"""Tests for REST endpoints routed through the Hub."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from wrangled_contracts import (
    CommandResult,
    PushResult,
    SetDeviceNameResult,
    StateSnapshot,
    WledDevice,
)

from api.server import create_app
from api.server.connection import WranglerConnection


def _dev(mac: str = "aa:bb:cc:dd:ee:ff", ip: str = "10.0.6.207") -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name="WLED-Matrix",
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


async def _attach_fake(hub, wrangler_id: str, devices: list[WledDevice]):
    conn = WranglerConnection(
        wrangler_id=wrangler_id,
        socket=AsyncMock(),
        wrangler_version="0.1.0",
    )
    conn.apply_devices(devices)
    await hub.attach(conn)
    return conn


@pytest.fixture
def app_with_one():
    app = create_app()
    asyncio.get_event_loop().run_until_complete(
        _attach_fake(app.state.hub, "pi-a", [_dev()]),
    )
    return app


def test_list_devices(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.get("/api/devices")
    assert response.status_code == 200
    assert len(response.json()["devices"]) == 1


def test_get_device(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.get("/api/devices/aa:bb:cc:dd:ee:ff")
    assert response.status_code == 200


def test_get_device_404(app_with_one) -> None:
    client = TestClient(app_with_one)
    assert client.get("/api/devices/zz:zz:zz:zz:zz:zz").status_code == 404


def test_get_state(app_with_one) -> None:
    hub = app_with_one.state.hub
    conn = hub._conns["pi-a"]  # noqa: SLF001

    async def fake_send(raw: str) -> None:
        req_id = json.loads(raw)["request_id"]
        hub.resolve_response(
            "pi-a",
            StateSnapshot(
                request_id=req_id, mac="aa:bb:cc:dd:ee:ff", state={"on": True, "bri": 80}
            ),
        )

    conn.socket.send_text = AsyncMock(side_effect=fake_send)
    client = TestClient(app_with_one)
    response = client.get("/api/devices/aa:bb:cc:dd:ee:ff/state")
    assert response.status_code == 200
    assert response.json()["state"] == {"on": True, "bri": 80}


def test_post_command(app_with_one) -> None:
    hub = app_with_one.state.hub
    conn = hub._conns["pi-a"]  # noqa: SLF001

    async def fake_send(raw: str) -> None:
        req_id = json.loads(raw)["request_id"]
        hub.resolve_response(
            "pi-a",
            CommandResult(request_id=req_id, result=PushResult(ok=True, status=200)),
        )

    conn.socket.send_text = AsyncMock(side_effect=fake_send)
    client = TestClient(app_with_one)
    response = client.post(
        "/api/devices/aa:bb:cc:dd:ee:ff/commands",
        json={"kind": "color", "color": {"r": 10, "g": 20, "b": 30}},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_post_command_unknown_mac(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.post(
        "/api/devices/zz:zz:zz:zz:zz:zz/commands",
        json={"kind": "power", "on": False},
    )
    assert response.status_code == 404


def test_put_name_succeeds(app_with_one) -> None:
    hub = app_with_one.state.hub
    conn = hub._conns["pi-a"]  # noqa: SLF001

    async def fake_send(raw: str) -> None:
        req_id = json.loads(raw)["request_id"]
        hub.resolve_response(
            "pi-a",
            SetDeviceNameResult(request_id=req_id, device=_dev()),
        )

    conn.socket.send_text = AsyncMock(side_effect=fake_send)
    client = TestClient(app_with_one)
    response = client.put(
        "/api/devices/aa:bb:cc:dd:ee:ff/name",
        json={"name": "NewName"},
    )
    assert response.status_code == 200
    assert response.json()["mac"] == "aa:bb:cc:dd:ee:ff"


def test_put_name_404_unknown_mac(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.put(
        "/api/devices/zz:zz:zz:zz:zz:zz/name",
        json={"name": "NewName"},
    )
    assert response.status_code == 404


def test_wranglers_summary(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.get("/api/wranglers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["wrangler_id"] == "pi-a"
    assert data[0]["device_count"] == 1
