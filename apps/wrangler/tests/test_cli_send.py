"""Tests for wrangler.cli `send` subcommand."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest
from wrangled_contracts import (
    RGB,
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
    PresetCommand,
    TextCommand,
    WledDevice,
)

from wrangler.cli import main
from wrangler.pusher import PushResult


def _fake_device() -> WledDevice:
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


@pytest.fixture
def capture_push() -> tuple[AsyncMock, list[Command]]:
    sent: list[Command] = []

    async def _capture(_client, _device, command, **_kwargs):
        sent.append(command)
        return PushResult(ok=True, status=200)

    return AsyncMock(side_effect=_capture), sent


def _patch_device_and_push(push_mock: AsyncMock):
    return (
        patch("wrangler.cli._resolve_device", AsyncMock(return_value=_fake_device())),
        patch("wrangler.cli.push_command", push_mock),
    )


def test_send_color_named(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "color", "red"])
    assert exit_code == 0
    assert sent == [ColorCommand(color=RGB(r=255, g=0, b=0))]


def test_send_color_hex_with_brightness(
    capture_push: tuple[AsyncMock, list[Command]],
) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(
            ["send", "--ip", "10.0.6.207", "color", "#ff00aa", "--brightness", "120"],
        )
    assert exit_code == 0
    assert sent == [ColorCommand(color=RGB(r=255, g=0, b=170), brightness=120)]


def test_send_brightness(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "brightness", "80"])
    assert exit_code == 0
    assert sent == [BrightnessCommand(brightness=80)]


def test_send_power_off(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "power", "off"])
    assert exit_code == 0
    assert sent == [PowerCommand(on=False)]


def test_send_power_on(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "power", "on"])
    assert exit_code == 0
    assert sent == [PowerCommand(on=True)]


def test_send_reports_push_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fail = AsyncMock(return_value=PushResult(ok=False, status=500, error="boom"))
    patches = _patch_device_and_push(fail)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "power", "off"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "500" in captured.err or "boom" in captured.err


def test_send_effect_minimal(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "effect", "fire"])
    assert exit_code == 0
    assert sent == [EffectCommand(name="fire")]


def test_send_effect_with_flags(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(
            [
                "send",
                "--ip",
                "10.0.6.207",
                "effect",
                "rainbow",
                "--speed",
                "200",
                "--intensity",
                "150",
                "--color",
                "orange",
                "--brightness",
                "180",
            ],
        )
    assert exit_code == 0
    assert sent == [
        EffectCommand(
            name="rainbow",
            speed=200,
            intensity=150,
            color=RGB(r=255, g=100, b=0),
            brightness=180,
        ),
    ]


def test_send_text_minimal(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "text", "hi"])
    assert exit_code == 0
    assert len(sent) == 1
    assert sent[0].text == "hi"


def test_send_text_with_flags(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(
            [
                "send",
                "--ip",
                "10.0.6.207",
                "text",
                "Hello PyTexas",
                "--color",
                "blue",
                "--speed",
                "160",
                "--brightness",
                "150",
            ],
        )
    assert exit_code == 0
    assert sent == [
        TextCommand(
            text="Hello PyTexas",
            color=RGB(r=0, g=0, b=255),
            speed=160,
            brightness=150,
        ),
    ]


def test_send_text_rejects_too_long(capsys: pytest.CaptureFixture[str]) -> None:
    push = AsyncMock()
    patches = _patch_device_and_push(push)
    long_text = "x" * 201  # Jesse bumped max to 200
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "text", long_text])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "text" in captured.err.lower()
    push.assert_not_awaited()


def test_send_preset_pytexas(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "preset", "pytexas"])
    assert exit_code == 0
    assert sent == [PresetCommand(name="pytexas")]


def test_send_emoji_fire(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "emoji", "🔥"])
    assert exit_code == 0
    assert sent == [EffectCommand(name="fire")]


def test_send_emoji_unknown_errors(capsys: pytest.CaptureFixture[str]) -> None:
    push = AsyncMock()
    patches = _patch_device_and_push(push)
    with patches[0], patches[1]:
        exit_code = main(["send", "--ip", "10.0.6.207", "emoji", "🦑"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "emoji" in captured.err.lower()
    push.assert_not_awaited()


def _two_devices() -> list[WledDevice]:
    base = {
        "version": "0.15.0",
        "led_count": 256,
        "matrix": None,
        "udp_port": 21324,
        "raw_info": {},
        "discovered_via": "mdns",
        "discovered_at": datetime.now(tz=UTC),
    }
    return [
        WledDevice(ip=IPv4Address("10.0.6.207"), name="A", mac="aa:bb:cc:dd:ee:01", **base),
        WledDevice(ip=IPv4Address("10.0.6.208"), name="B", mac="aa:bb:cc:dd:ee:02", **base),
    ]


def test_ambiguous_discovery_fails_with_helpful_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    push = AsyncMock()
    scan_mock = AsyncMock(return_value=_two_devices())
    with (
        patch("wrangler.cli.scan", scan_mock),
        patch("wrangler.cli.push_command", push),
    ):
        exit_code = main(["send", "color", "red"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--ip" in captured.err or "multiple" in captured.err.lower()
    push.assert_not_awaited()


def test_name_filter_selects_one(capture_push: tuple[AsyncMock, list[Command]]) -> None:
    push, sent = capture_push
    scan_mock = AsyncMock(return_value=_two_devices())
    with (
        patch("wrangler.cli.scan", scan_mock),
        patch("wrangler.cli.push_command", push),
    ):
        exit_code = main(["send", "--name", "B", "color", "red"])
    assert exit_code == 0
    assert sent == [ColorCommand(color=RGB(r=255, g=0, b=0))]
