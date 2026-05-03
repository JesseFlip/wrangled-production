"""Tests for wrangler.cli."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest
from wrangled_contracts import WledDevice, WledMatrix

from wrangler.cli import main


def _device() -> WledDevice:
    return WledDevice(
        ip=IPv4Address("10.0.6.207"),
        name="WLED-Matrix",
        mac="aa:bb:cc:dd:ee:ff",
        version="0.15.0",
        led_count=256,
        matrix=WledMatrix(width=16, height=16),
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime(2026, 4, 13, tzinfo=UTC),
    )


@pytest.fixture
def fake_scan() -> AsyncMock:
    return AsyncMock(return_value=[_device()])


def test_cli_scan_table_output(
    fake_scan: AsyncMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("wrangler.cli.scan", fake_scan):
        exit_code = main(["scan"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "10.0.6.207" in captured.out
    assert "WLED-Matrix" in captured.out
    assert "16x16" in captured.out


def test_cli_scan_json_output(
    fake_scan: AsyncMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("wrangler.cli.scan", fake_scan):
        exit_code = main(["scan", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload[0]["ip"] == "10.0.6.207"


def test_cli_scan_empty_is_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("wrangler.cli.scan", AsyncMock(return_value=[])):
        exit_code = main(["scan"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 devices" in captured.out


def test_cli_scan_force_sweep_flag_sets_option() -> None:
    captured_opts = {}

    async def _capture(opts):
        captured_opts["opts"] = opts
        return []

    with patch("wrangler.cli.scan", side_effect=_capture):
        main(["scan", "--sweep"])
    assert captured_opts["opts"].sweep is True


def test_cli_scan_no_mdns_flag_sets_option() -> None:
    captured_opts = {}

    async def _capture(opts):
        captured_opts["opts"] = opts
        return []

    with patch("wrangler.cli.scan", side_effect=_capture):
        main(["scan", "--no-mdns"])
    assert captured_opts["opts"].use_mdns is False


def test_cli_scan_subnet_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_opts = {}

    async def _capture(opts):
        captured_opts["opts"] = opts
        return []

    with patch("wrangler.cli.scan", side_effect=_capture):
        main(["scan", "--subnet", "10.0.6.0/24"])
    assert str(captured_opts["opts"].sweep_subnet) == "10.0.6.0/24"
    capsys.readouterr()
