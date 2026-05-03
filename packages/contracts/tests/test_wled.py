"""Tests for wrangled_contracts.wled."""

from datetime import UTC, datetime
from ipaddress import IPv4Address

import pytest
from pydantic import ValidationError

from wrangled_contracts import WledDevice, WledMatrix


def test_wled_matrix_accepts_positive_dimensions() -> None:
    matrix = WledMatrix(width=16, height=16)
    assert matrix.width == 16
    assert matrix.height == 16


def test_wled_matrix_rejects_zero_width() -> None:
    with pytest.raises(ValidationError):
        WledMatrix(width=0, height=16)


def test_wled_matrix_rejects_negative_height() -> None:
    with pytest.raises(ValidationError):
        WledMatrix(width=16, height=-1)


def _base_device_kwargs() -> dict:
    return {
        "ip": IPv4Address("10.0.6.207"),
        "name": "WLED-Matrix",
        "mac": "aa:bb:cc:dd:ee:ff",
        "version": "0.15.0",
        "led_count": 256,
        "matrix": WledMatrix(width=16, height=16),
        "udp_port": 21324,
        "raw_info": {"leds": {"count": 256}},
        "discovered_via": "mdns",
        "discovered_at": datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    }


def test_wled_device_roundtrip() -> None:
    device = WledDevice(**_base_device_kwargs())
    assert device.ip == IPv4Address("10.0.6.207")
    assert device.matrix is not None
    assert device.matrix.width == 16


def test_wled_device_without_matrix_is_allowed() -> None:
    kwargs = _base_device_kwargs()
    kwargs["matrix"] = None
    kwargs["led_count"] = 60
    device = WledDevice(**kwargs)
    assert device.matrix is None


def test_wled_device_mac_is_lowercased() -> None:
    kwargs = _base_device_kwargs()
    kwargs["mac"] = "AA:BB:CC:DD:EE:FF"
    device = WledDevice(**kwargs)
    assert device.mac == "aa:bb:cc:dd:ee:ff"


def test_wled_device_mac_without_colons_is_canonicalized() -> None:
    kwargs = _base_device_kwargs()
    kwargs["mac"] = "AABBCCDDEEFF"
    device = WledDevice(**kwargs)
    assert device.mac == "aa:bb:cc:dd:ee:ff"


def test_wled_device_rejects_invalid_mac() -> None:
    kwargs = _base_device_kwargs()
    kwargs["mac"] = "not-a-mac"
    with pytest.raises(ValidationError):
        WledDevice(**kwargs)


def test_wled_device_discovered_via_is_constrained() -> None:
    kwargs = _base_device_kwargs()
    kwargs["discovered_via"] = "smoke-signal"
    with pytest.raises(ValidationError):
        WledDevice(**kwargs)
