"""Tests for wrangler.scanner.probe."""

from __future__ import annotations

from ipaddress import IPv4Address

import httpx
import pytest
import respx

from wrangler.scanner.probe import probe_device


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_parses_v0_15_info(wled_info_v0_15: dict) -> None:
    respx.get("http://10.0.6.207/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.207"), source="mdns")

    assert device is not None
    assert device.name == "WLED-Matrix"
    assert device.mac == "aa:bb:cc:dd:ee:ff"
    assert device.version == "0.15.0"
    assert device.led_count == 256
    assert device.matrix is not None
    assert device.matrix.width == 16
    assert device.matrix.height == 16
    assert device.udp_port == 21324
    assert device.discovered_via == "mdns"


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_returns_none_on_timeout() -> None:
    respx.get("http://10.0.6.99/json/info").mock(side_effect=httpx.ReadTimeout)
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.99"), source="sweep")
    assert device is None


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_returns_none_on_non_200() -> None:
    respx.get("http://10.0.6.50/json/info").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.50"), source="sweep")
    assert device is None


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_returns_none_on_non_wled_json() -> None:
    respx.get("http://10.0.6.42/json/info").mock(
        return_value=httpx.Response(200, json={"hello": "router"}),
    )
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.42"), source="sweep")
    assert device is None


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_handles_missing_matrix(wled_info_v0_15: dict) -> None:
    info = dict(wled_info_v0_15)
    info["leds"] = {**info["leds"]}
    info["leds"].pop("matrix")
    respx.get("http://10.0.6.10/json/info").mock(
        return_value=httpx.Response(200, json=info),
    )
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.10"), source="sweep")
    assert device is not None
    assert device.matrix is None
