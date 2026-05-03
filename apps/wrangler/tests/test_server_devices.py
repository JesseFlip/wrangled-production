"""Tests for the devices/scan endpoints in wrangler.server.devices."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from wrangled_contracts import WledDevice

from wrangler.pusher import PushResult
from wrangler.server import create_app
from wrangler.server.registry import Registry
from wrangler.server.wled_client import WledUnreachableError


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


@pytest.fixture
def registry_with_one() -> Registry:
    r = Registry(scanner=AsyncMock(return_value=[_dev()]))
    r.put(_dev())
    return r


@pytest.fixture
def app_with_registry(registry_with_one: Registry):
    return create_app(initial_scan=False, registry=registry_with_one)


# --- Task 4: list / get / scan ---


def test_get_devices_returns_list(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["mac"] == "aa:bb:cc:dd:ee:ff"


def test_get_device_by_mac_returns_device(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices/aa:bb:cc:dd:ee:ff")
    assert response.status_code == 200
    assert response.json()["mac"] == "aa:bb:cc:dd:ee:ff"


def test_get_device_by_mac_404(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices/zz:zz:zz:zz:zz:zz")
    assert response.status_code == 404


def test_post_scan_invokes_registry_scan() -> None:
    scanner = AsyncMock(return_value=[_dev("11:22:33:44:55:66", "10.0.6.10")])
    registry = Registry(scanner=scanner)
    app = create_app(initial_scan=False, registry=registry)
    client = TestClient(app)
    response = client.post("/api/scan")
    assert response.status_code == 200
    data = response.json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["mac"] == "11:22:33:44:55:66"
    scanner.assert_awaited_once()


# --- Task 5: state ---


def test_get_state_returns_live_body(app_with_registry) -> None:
    payload = {"on": True, "bri": 80, "seg": [{"fx": 149}]}
    with patch(
        "wrangler.server.devices.fetch_state",
        AsyncMock(return_value=payload),
    ):
        client = TestClient(app_with_registry)
        response = client.get("/api/devices/aa:bb:cc:dd:ee:ff/state")
    assert response.status_code == 200
    assert response.json() == payload


def test_get_state_returns_502_when_wled_down(app_with_registry) -> None:
    with patch(
        "wrangler.server.devices.fetch_state",
        AsyncMock(side_effect=WledUnreachableError("dead")),
    ):
        client = TestClient(app_with_registry)
        response = client.get("/api/devices/aa:bb:cc:dd:ee:ff/state")
    assert response.status_code == 502


def test_get_state_404_for_unknown_mac(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices/zz:zz:zz:zz:zz:zz/state")
    assert response.status_code == 404


# --- Task 6: commands ---


def test_post_command_color_ok(app_with_registry) -> None:
    with patch(
        "wrangler.server.devices.push_command",
        AsyncMock(return_value=PushResult(ok=True, status=200)),
    ):
        client = TestClient(app_with_registry)
        response = client.post(
            "/api/devices/aa:bb:cc:dd:ee:ff/commands",
            json={"kind": "color", "color": {"r": 255, "g": 0, "b": 0}},
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": 200, "error": None}


def test_post_command_422_on_invalid_body(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.post(
        "/api/devices/aa:bb:cc:dd:ee:ff/commands",
        json={"kind": "color"},  # missing color
    )
    assert response.status_code == 422


def test_post_command_404_unknown_mac(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.post(
        "/api/devices/zz:zz:zz:zz:zz:zz/commands",
        json={"kind": "power", "on": False},
    )
    assert response.status_code == 404


def test_post_command_reports_push_failure(app_with_registry) -> None:
    with patch(
        "wrangler.server.devices.push_command",
        AsyncMock(return_value=PushResult(ok=False, status=500, error="boom")),
    ):
        client = TestClient(app_with_registry)
        response = client.post(
            "/api/devices/aa:bb:cc:dd:ee:ff/commands",
            json={"kind": "power", "on": True},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == 500


# --- Task 7: name ---


def test_put_name_updates_device(app_with_registry, registry_with_one) -> None:
    renamed_data = _dev().model_dump()
    renamed_data["name"] = "Stage-Left"
    updated = WledDevice.model_validate(renamed_data)

    with (
        patch("wrangler.server.devices.set_name", AsyncMock()),
        patch("wrangler.server.devices.probe_device", AsyncMock(return_value=updated)),
    ):
        client = TestClient(app_with_registry)
        response = client.put(
            "/api/devices/aa:bb:cc:dd:ee:ff/name",
            json={"name": "Stage-Left"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Stage-Left"
    assert registry_with_one.get("aa:bb:cc:dd:ee:ff").name == "Stage-Left"


def test_put_name_404_unknown_mac(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.put(
        "/api/devices/zz:zz:zz:zz:zz:zz/name",
        json={"name": "x"},
    )
    assert response.status_code == 404


def test_put_name_502_when_wled_down(app_with_registry) -> None:
    with patch(
        "wrangler.server.devices.set_name",
        AsyncMock(side_effect=WledUnreachableError("dead")),
    ):
        client = TestClient(app_with_registry)
        response = client.put(
            "/api/devices/aa:bb:cc:dd:ee:ff/name",
            json={"name": "x"},
        )
    assert response.status_code == 502


def test_put_name_rejects_empty(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.put(
        "/api/devices/aa:bb:cc:dd:ee:ff/name",
        json={"name": ""},
    )
    assert response.status_code == 422
