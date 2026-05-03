"""mDNS-based WLED discovery using python-zeroconf."""

from __future__ import annotations

import asyncio
import logging
from ipaddress import IPv4Address

from zeroconf import ServiceBrowser, Zeroconf

logger = logging.getLogger(__name__)

_WLED_SERVICE = "_wled._tcp.local."


class _WledListener:
    def __init__(self) -> None:
        self.addresses: set[IPv4Address] = set()

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        info = zc.get_service_info(service_type, name, timeout=1000)
        if info is None:
            logger.debug("mdns: no info for %s", name)
            return
        for addr in info.parsed_addresses():
            try:
                self.addresses.add(IPv4Address(addr))
            except ValueError:
                logger.debug("mdns: non-ipv4 address %s from %s", addr, name)

    def update_service(self, *_args: object, **_kwargs: object) -> None:  # pragma: no cover
        pass

    def remove_service(self, *_args: object, **_kwargs: object) -> None:  # pragma: no cover
        pass


async def discover_via_mdns(*, timeout: float = 3.0) -> set[IPv4Address]:  # noqa: ASYNC109
    """Browse the LAN for `_wled._tcp` services for `timeout` seconds.

    Never raises: a zeroconf bind failure yields an empty set.
    """
    try:
        zc = Zeroconf()
    except OSError as exc:
        logger.warning("mdns: zeroconf bind failed: %s", exc)
        return set()

    listener = _WledListener()
    browser = ServiceBrowser(zc, _WLED_SERVICE, listener)
    try:
        await asyncio.sleep(timeout)
    finally:
        browser.cancel()
        zc.close()
    return listener.addresses
