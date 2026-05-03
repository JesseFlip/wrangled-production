"""Tests for wrangler.hub_client."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest
import websockets
from wrangled_contracts import PushResult, WledDevice

from wrangler.hub_client import HubClient
from wrangler.server.registry import Registry


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


async def _fake_server(host: str, port: int, handler):
    return await websockets.serve(handler, host, port)


@pytest.mark.asyncio
async def test_hub_client_sends_hello_on_connect(unused_tcp_port: int) -> None:
    port = unused_tcp_port
    first_message: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

    async def handler(ws):
        raw = await ws.recv()
        data = json.loads(raw)
        if not first_message.done():
            first_message.set_result(data)
        await ws.send(json.dumps({"kind": "welcome", "server_version": "test"}))
        await asyncio.sleep(0.2)

    server = await _fake_server("127.0.0.1", port, handler)
    try:
        registry = Registry(
            scanner=AsyncMock(return_value=[_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")]),
        )
        registry.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1"))
        client = HubClient(
            api_url=f"ws://127.0.0.1:{port}/ws",
            auth_token=None,
            wrangler_id="pi-test",
            registry=registry,
        )
        task = asyncio.create_task(client.run())
        hello = await asyncio.wait_for(first_message, timeout=2.0)
        assert hello["kind"] == "hello"
        assert hello["wrangler_id"] == "pi-test"
        assert len(hello["devices"]) == 1
        task.cancel()
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_hub_client_responds_to_command(unused_tcp_port: int) -> None:
    port = unused_tcp_port
    response: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

    async def handler(ws):
        await ws.recv()  # Hello
        await ws.send(json.dumps({"kind": "welcome", "server_version": "test"}))
        await ws.send(
            json.dumps(
                {
                    "kind": "command",
                    "request_id": "req-1",
                    "mac": "aa:bb:cc:dd:ee:01",
                    "command": {"kind": "color", "color": {"r": 1, "g": 2, "b": 3}},
                }
            )
        )
        raw = await ws.recv()
        if not response.done():
            response.set_result(json.loads(raw))
        await asyncio.sleep(0.1)

    server = await _fake_server("127.0.0.1", port, handler)
    try:
        registry = Registry(scanner=AsyncMock())
        registry.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1"))

        with patch(
            "wrangler.hub_client.push_command",
            AsyncMock(return_value=PushResult(ok=True, status=200)),
        ):
            client = HubClient(
                api_url=f"ws://127.0.0.1:{port}/ws",
                auth_token=None,
                wrangler_id="pi-test",
                registry=registry,
            )
            task = asyncio.create_task(client.run())
            result = await asyncio.wait_for(response, timeout=2.0)
        assert result["kind"] == "command_result"
        assert result["request_id"] == "req-1"
        assert result["result"]["ok"] is True
        task.cancel()
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_hub_client_handles_set_device_name(unused_tcp_port: int) -> None:
    port = unused_tcp_port
    response: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

    async def handler(ws):
        await ws.recv()  # Hello
        await ws.send(json.dumps({"kind": "welcome", "server_version": "test"}))
        await ws.send(
            json.dumps(
                {
                    "kind": "set_device_name",
                    "request_id": "req-rename",
                    "mac": "aa:bb:cc:dd:ee:01",
                    "name": "NewName",
                }
            )
        )
        raw = await ws.recv()
        if not response.done():
            response.set_result(json.loads(raw))
        await asyncio.sleep(0.1)

    server = await _fake_server("127.0.0.1", port, handler)
    try:
        registry = Registry(scanner=AsyncMock())
        dev = _dev("aa:bb:cc:dd:ee:01", "10.0.6.1")
        registry.put(dev)
        refreshed = _dev("aa:bb:cc:dd:ee:01", "10.0.6.1")

        with (
            patch("wrangler.hub_client.set_name", AsyncMock(return_value=None)),
            patch(
                "wrangler.hub_client.probe_device",
                AsyncMock(return_value=refreshed),
            ),
        ):
            client = HubClient(
                api_url=f"ws://127.0.0.1:{port}/ws",
                auth_token=None,
                wrangler_id="pi-test",
                registry=registry,
            )
            task = asyncio.create_task(client.run())
            result = await asyncio.wait_for(response, timeout=2.0)
        assert result["kind"] == "set_device_name_result"
        assert result["request_id"] == "req-rename"
        assert result["device"] is not None
        assert result["error"] is None
        task.cancel()
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_hub_client_sends_pong_to_ping(unused_tcp_port: int) -> None:
    port = unused_tcp_port
    saw_pong: asyncio.Future[bool] = asyncio.get_event_loop().create_future()

    async def handler(ws):
        await ws.recv()  # Hello
        await ws.send(json.dumps({"kind": "welcome", "server_version": "test"}))
        await ws.send(json.dumps({"kind": "ping"}))
        raw = await ws.recv()
        if not saw_pong.done():
            saw_pong.set_result(json.loads(raw)["kind"] == "pong")
        await asyncio.sleep(0.1)

    server = await _fake_server("127.0.0.1", port, handler)
    try:
        client = HubClient(
            api_url=f"ws://127.0.0.1:{port}/ws",
            auth_token=None,
            wrangler_id="pi-test",
            registry=Registry(scanner=AsyncMock()),
        )
        task = asyncio.create_task(client.run())
        assert await asyncio.wait_for(saw_pong, timeout=2.0) is True
        task.cancel()
    finally:
        server.close()
        await server.wait_closed()
