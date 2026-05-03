"""End-to-end: real api + real HubClient (with mocked pusher) round-trip."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import uvicorn
from wrangled_contracts import PushResult, WledDevice
from wrangler.hub_client import HubClient
from wrangler.server.registry import Registry

from api.server import create_app


def _dev() -> WledDevice:
    return WledDevice(
        ip=IPv4Address("10.0.6.207"),
        name="WLED-Matrix",
        mac="aa:bb:cc:dd:ee:ff",
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_post_command_round_trips_to_wrangler(unused_tcp_port: int) -> None:
    port = unused_tcp_port
    app = create_app()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Wait for the uvicorn server to boot.
    for _ in range(100):
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"http://127.0.0.1:{port}/healthz")
                if r.status_code == 200:
                    break
        except Exception:  # noqa: BLE001, S110
            pass
        await asyncio.sleep(0.05)

    try:
        registry = Registry(scanner=AsyncMock(return_value=[_dev()]))
        registry.put(_dev())

        with patch(
            "wrangler.hub_client.push_command",
            AsyncMock(return_value=PushResult(ok=True, status=200)),
        ):
            hub_client = HubClient(
                api_url=f"ws://127.0.0.1:{port}/ws",
                auth_token=None,
                wrangler_id="pi-e2e",
                registry=registry,
            )
            run_task = asyncio.create_task(hub_client.run())

            # Wait for wrangler to register.
            for _ in range(100):
                async with httpx.AsyncClient() as c:
                    r = await c.get(f"http://127.0.0.1:{port}/api/wranglers")
                    if r.status_code == 200 and len(r.json()) == 1:
                        break
                await asyncio.sleep(0.05)

            async with httpx.AsyncClient() as c:
                resp = await c.post(
                    f"http://127.0.0.1:{port}/api/devices/aa:bb:cc:dd:ee:ff/commands",
                    json={"kind": "color", "color": {"r": 0, "g": 0, "b": 255}},
                    timeout=5.0,
                )

            assert resp.status_code == 200
            assert resp.json()["ok"] is True

            run_task.cancel()
    finally:
        server.should_exit = True
        await server_task
