"""Tests for wrangler.scanner.mdns."""

from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import MagicMock, patch

import pytest

from wrangler.scanner.mdns import discover_via_mdns


class _FakeInfo:
    def __init__(self, addresses: list[bytes]) -> None:
        self.addresses = addresses

    def parsed_addresses(self) -> list[str]:
        return [IPv4Address(int.from_bytes(a, "big")).compressed for a in self.addresses]


@pytest.mark.asyncio
async def test_discover_via_mdns_returns_ips() -> None:
    fake_info = _FakeInfo([IPv4Address("10.0.6.207").packed])
    fake_zeroconf = MagicMock()
    fake_zeroconf.get_service_info.return_value = fake_info

    class _FakeBrowser:
        def __init__(self, zc, service_type, listener) -> None:
            listener.add_service(zc, service_type, "WLED-Matrix._wled._tcp.local.")

        def cancel(self) -> None:
            pass

    with (
        patch("wrangler.scanner.mdns.Zeroconf", return_value=fake_zeroconf),
        patch("wrangler.scanner.mdns.ServiceBrowser", _FakeBrowser),
    ):
        ips = await discover_via_mdns(timeout=0.1)

    assert IPv4Address("10.0.6.207") in ips


@pytest.mark.asyncio
async def test_discover_via_mdns_empty_on_timeout() -> None:
    fake_zeroconf = MagicMock()

    class _NoopBrowser:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def cancel(self) -> None:
            pass

    with (
        patch("wrangler.scanner.mdns.Zeroconf", return_value=fake_zeroconf),
        patch("wrangler.scanner.mdns.ServiceBrowser", _NoopBrowser),
    ):
        ips = await discover_via_mdns(timeout=0.05)

    assert ips == set()
