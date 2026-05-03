"""Tests for wrangler.server.wled_client."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address

import httpx
import pytest
import respx
from wrangled_contracts import WledDevice

from wrangler.server.wled_client import WledUnreachableError, fetch_state, set_name


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
@respx.mock
async def test_fetch_state_returns_parsed_body() -> None:
    payload = {"on": True, "bri": 80, "seg": [{"fx": 149, "col": [[255, 80, 0]]}]}
    respx.get("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json=payload),
    )
    async with httpx.AsyncClient() as client:
        state = await fetch_state(client, _dev())
    assert state == payload


@pytest.mark.asyncio
@respx.mock
async def test_fetch_state_raises_on_non_200() -> None:
    respx.get("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(WledUnreachableError):
            await fetch_state(client, _dev())


@pytest.mark.asyncio
@respx.mock
async def test_fetch_state_raises_on_timeout() -> None:
    respx.get("http://10.0.6.207/json/state").mock(side_effect=httpx.ReadTimeout)
    async with httpx.AsyncClient() as client:
        with pytest.raises(WledUnreachableError):
            await fetch_state(client, _dev())


@pytest.mark.asyncio
@respx.mock
async def test_set_name_posts_to_json_cfg() -> None:
    route = respx.post("http://10.0.6.207/json/cfg").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        await set_name(client, _dev(), "Stage-Left")
    assert route.called
    body = route.calls.last.request.read()
    assert b'"Stage-Left"' in body
    assert b'"id"' in body


@pytest.mark.asyncio
@respx.mock
async def test_set_name_raises_on_failure() -> None:
    respx.post("http://10.0.6.207/json/cfg").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(WledUnreachableError):
            await set_name(client, _dev(), "x")
