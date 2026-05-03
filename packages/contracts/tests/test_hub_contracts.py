"""Tests for wrangled_contracts.hub (WebSocket protocol envelopes)."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import cast

import pytest
from pydantic import TypeAdapter, ValidationError

from wrangled_contracts import (
    RGB,
    ApiMessage,
    ColorCommand,
    CommandResult,
    DevicesChanged,
    GetState,
    Hello,
    Ping,
    Pong,
    PushResult,
    RelayCommand,
    Rescan,
    SetDeviceName,
    SetDeviceNameResult,
    StateSnapshot,
    Welcome,
    WledDevice,
    WranglerMessage,
)

_WRANGLER = TypeAdapter(WranglerMessage)
_API = TypeAdapter(ApiMessage)


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
        discovered_at=datetime(2026, 4, 13, tzinfo=UTC),
    )


def test_hello_roundtrip() -> None:
    msg = Hello(wrangler_id="pi-venue", wrangler_version="0.1.0", devices=[_dev()])
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, Hello)
    assert parsed.wrangler_id == "pi-venue"
    assert len(parsed.devices) == 1


def test_devices_changed_roundtrip() -> None:
    msg = DevicesChanged(devices=[_dev()])
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, DevicesChanged)


def test_command_result_roundtrip() -> None:
    msg = CommandResult(request_id="abc", result=PushResult(ok=True, status=200))
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert cast("CommandResult", parsed).request_id == "abc"
    assert cast("CommandResult", parsed).result.ok is True


def test_state_snapshot_roundtrip() -> None:
    msg = StateSnapshot(request_id="xyz", mac="aa:bb:cc:dd:ee:ff", state={"on": True, "bri": 80})
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert cast("StateSnapshot", parsed).state == {"on": True, "bri": 80}


def test_state_snapshot_with_error() -> None:
    msg = StateSnapshot(request_id="xyz", mac="aa:bb:cc:dd:ee:ff", state=None, error="unreachable")
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert cast("StateSnapshot", parsed).error == "unreachable"


def test_pong_roundtrip() -> None:
    parsed = _WRANGLER.validate_python(Pong().model_dump(mode="json"))
    assert isinstance(parsed, Pong)


def test_welcome_roundtrip() -> None:
    parsed = _API.validate_python(Welcome(server_version="0.1.0").model_dump(mode="json"))
    assert isinstance(parsed, Welcome)


def test_relay_command_roundtrip() -> None:
    msg = RelayCommand(
        request_id="r1",
        mac="aa:bb:cc:dd:ee:ff",
        command=ColorCommand(color=RGB(r=0, g=0, b=255)),
    )
    parsed = _API.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, RelayCommand)
    assert isinstance(parsed.command, ColorCommand)
    assert parsed.command.color == RGB(r=0, g=0, b=255)


def test_get_state_roundtrip() -> None:
    parsed = _API.validate_python(
        GetState(request_id="g1", mac="aa:bb:cc:dd:ee:ff").model_dump(mode="json"),
    )
    assert isinstance(parsed, GetState)


def test_rescan_roundtrip() -> None:
    parsed = _API.validate_python(Rescan().model_dump(mode="json"))
    assert isinstance(parsed, Rescan)


def test_ping_roundtrip() -> None:
    parsed = _API.validate_python(Ping().model_dump(mode="json"))
    assert isinstance(parsed, Ping)


def test_set_device_name_roundtrip() -> None:
    msg = SetDeviceName(request_id="r1", mac="aa:bb:cc:dd:ee:ff", name="NewName")
    parsed = _API.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, SetDeviceName)
    assert parsed.request_id == "r1"
    assert parsed.name == "NewName"


def test_set_device_name_result_roundtrip() -> None:
    msg = SetDeviceNameResult(request_id="r1", device=_dev())
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, SetDeviceNameResult)
    assert parsed.request_id == "r1"
    assert parsed.device is not None
    assert parsed.device.name == "WLED-Matrix"


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        _WRANGLER.validate_python({"kind": "bogus"})
    with pytest.raises(ValidationError):
        _API.validate_python({"kind": "bogus"})
