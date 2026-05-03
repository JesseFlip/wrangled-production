"""Tests for wrangler.scanner.sweep."""

from __future__ import annotations

from ipaddress import IPv4Network

import httpx
import pytest
import respx

from wrangler.scanner.sweep import sweep_subnet


@pytest.mark.asyncio
@respx.mock
async def test_sweep_finds_single_wled(wled_info_v0_15: dict) -> None:
    # 10.0.6.0/29 hosts are .1-.6; mock .3 as the WLED device, all others 404.
    # respx resolves first-match, so specific route must be registered before regex fallback.
    respx.get("http://10.0.6.3/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    respx.get(url__regex=r"http://10\.0\.6\.\d+/json/info").mock(
        return_value=httpx.Response(404),
    )
    devices = await sweep_subnet(
        IPv4Network("10.0.6.0/29"),
        timeout=0.5,
        concurrency=8,
    )
    assert len(devices) == 1
    assert str(devices[0].ip) == "10.0.6.3"


@pytest.mark.asyncio
@respx.mock
async def test_sweep_dedupes_by_mac(wled_info_v0_15: dict) -> None:
    # Two IPs respond with the same MAC — should dedupe to one device.
    # Specific routes registered before regex fallback (first-match resolution).
    respx.get("http://10.0.6.1/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    # Second IP responds with the same MAC — should dedupe.
    respx.get("http://10.0.6.2/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    respx.get(url__regex=r"http://10\.0\.6\.\d+/json/info").mock(
        return_value=httpx.Response(404),
    )
    devices = await sweep_subnet(IPv4Network("10.0.6.0/29"), timeout=0.5, concurrency=4)
    assert len(devices) == 1


@pytest.mark.asyncio
@respx.mock
async def test_sweep_handles_empty_subnet() -> None:
    respx.get(url__regex=r"http://10\.0\.6\.\d+/json/info").mock(
        return_value=httpx.Response(404),
    )
    devices = await sweep_subnet(IPv4Network("10.0.6.0/29"), timeout=0.5, concurrency=4)
    assert devices == []
