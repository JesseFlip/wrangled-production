"""Tests for the /ws endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import create_app


def _hello_payload() -> dict:
    return {
        "kind": "hello",
        "wrangler_id": "pi-test",
        "wrangler_version": "0.1.0",
        "devices": [],
    }


def test_ws_connects_and_receives_welcome_without_auth() -> None:
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello_payload())
        welcome = ws.receive_json()
        assert welcome["kind"] == "welcome"
        assert "server_version" in welcome


def test_ws_requires_token_when_configured() -> None:
    app = create_app(auth_token="secret")  # noqa: S106
    client = TestClient(app)
    with pytest.raises(Exception), client.websocket_connect("/ws"):  # noqa: B017, PT011
        pass

    with client.websocket_connect("/ws?token=secret") as ws:
        ws.send_json(_hello_payload())
        assert ws.receive_json()["kind"] == "welcome"


def test_ws_registers_devices_in_hub() -> None:
    app = create_app()
    client = TestClient(app)
    dev = {
        "ip": "10.0.6.207",
        "name": "WLED-Matrix",
        "mac": "aa:bb:cc:dd:ee:ff",
        "version": "0.15.0",
        "led_count": 256,
        "matrix": None,
        "udp_port": 21324,
        "discovered_via": "mdns",
        "discovered_at": "2026-04-13T12:00:00+00:00",
    }
    with client.websocket_connect("/ws") as ws:
        payload = _hello_payload()
        payload["devices"] = [dev]
        ws.send_json(payload)
        ws.receive_json()  # welcome
        hub = app.state.hub
        assert hub.find_device("aa:bb:cc:dd:ee:ff") is not None


def test_ws_rejects_first_message_not_hello() -> None:
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"kind": "pong"})
        with pytest.raises(Exception):  # noqa: B017, PT011
            ws.receive_json()
