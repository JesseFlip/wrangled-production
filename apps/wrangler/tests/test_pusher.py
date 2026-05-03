"""Tests for wrangler.pusher."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address

import httpx
import pytest
import respx
from wrangled_contracts import (
    RGB,
    BrightnessCommand,
    ColorCommand,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    TextCommand,
    WledDevice,
)

from wrangler.pusher import (
    PushResult,
    _build_command_body,
    push_command,
)


def test_build_color_produces_valid_body() -> None:
    body = _build_command_body(ColorCommand(color=RGB(r=10, g=20, b=30), brightness=100))
    assert body["on"] is True
    assert body["bri"] == 100
    assert body["seg"][0]["col"] == [[10, 20, 30], [0, 0, 0], [0, 0, 0]]


def test_build_brightness_produces_bri() -> None:
    body = _build_command_body(BrightnessCommand(brightness=50))
    assert body["bri"] == 50


def test_build_power_on() -> None:
    body = _build_command_body(PowerCommand(on=True))
    assert body["on"] is True


def test_build_power_off() -> None:
    body = _build_command_body(PowerCommand(on=False))
    assert body["on"] is False


def test_build_effect_produces_fx_id() -> None:
    body = _build_command_body(EffectCommand(name="rainbow", speed=200, intensity=150, brightness=180))
    assert body["on"] is True
    assert body["bri"] == 180
    seg = body["seg"][0]
    assert "fx" in seg


def test_build_text_produces_scrolling() -> None:
    body = _build_command_body(TextCommand(text="Hello", color=RGB(r=0, g=0, b=255), speed=160))
    seg = body["seg"][0]
    assert body["on"] is True
    assert seg["fx"] == 122
    assert seg["n"] == "Hello"


def _fake_device(ip: str = "10.0.6.207") -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
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
async def test_push_color_happy_path() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            ColorCommand(color=RGB(r=10, g=20, b=30), brightness=100),
        )
    assert result == PushResult(ok=True, status=200)
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_push_brightness_happy_path() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), BrightnessCommand(brightness=50))
    assert result.ok is True
    assert route.calls.last.request.read() == b'{"bri": 50}'


@pytest.mark.asyncio
@respx.mock
async def test_push_power_off_happy_path() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PowerCommand(on=False))
    assert result.ok is True
    assert route.calls.last.request.read() == b'{"on": false}'


@pytest.mark.asyncio
@respx.mock
async def test_push_effect_happy_path() -> None:
    respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            EffectCommand(name="fire", speed=200),
        )
    assert result.ok is True


@pytest.mark.asyncio
@respx.mock
async def test_push_text_happy_path() -> None:
    respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            TextCommand(text="hi", color=RGB(r=0, g=0, b=255)),
        )
    assert result.ok is True


@pytest.mark.asyncio
@respx.mock
async def test_push_returns_error_on_timeout() -> None:
    respx.post("http://10.0.6.207/json/state").mock(side_effect=httpx.ReadTimeout)
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            ColorCommand(color=RGB(r=0, g=0, b=0)),
        )
    assert result.ok is False
    assert result.status is None
    assert result.error
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
@respx.mock
async def test_push_returns_error_on_non_200() -> None:
    respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(500, text="oops"),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(
            client,
            _fake_device(),
            ColorCommand(color=RGB(r=0, g=0, b=0)),
        )
    assert result.ok is False
    assert result.status == 500


@pytest.mark.asyncio
@respx.mock
async def test_push_preset_pytexas_posts() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PresetCommand(name="pytexas"))
    assert result.ok is True
    assert route.call_count >= 1  # Jesse changed pytexas to 1 command


@pytest.mark.asyncio
@respx.mock
async def test_push_preset_party_posts_once() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PresetCommand(name="party"))
    assert result.ok is True
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_push_preset_fails_on_error() -> None:
    route = respx.post("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    async with httpx.AsyncClient() as client:
        result = await push_command(client, _fake_device(), PresetCommand(name="chill"))
    assert result.ok is False
    assert result.status == 500
    assert route.call_count >= 1  # Jesse consolidated presets into single POST
