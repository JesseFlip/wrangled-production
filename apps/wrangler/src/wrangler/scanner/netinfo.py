"""Detect the local /24 subnet we should sweep."""

from __future__ import annotations

import socket
from ipaddress import IPv4Address, IPv4Network


class NoSubnetDetectedError(RuntimeError):
    """Raised when we cannot determine a local IPv4 subnet to sweep."""


def _connect_probe() -> str | None:
    """Use a connected UDP socket to learn which local IPv4 address we'd use outbound.

    Does not send packets; only asks the kernel for the source address that would
    be chosen when routing to a public address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addr: str = sock.getsockname()[0]
    except OSError:
        return None
    return addr


def detect_default_subnet() -> IPv4Network:
    """Return the /24 surrounding the kernel's default outbound IPv4 source address."""
    addr = _connect_probe()
    if not addr:
        msg = "could not detect a local IPv4 address; pass --subnet explicitly"
        raise NoSubnetDetectedError(msg)
    ip = IPv4Address(addr)
    return IPv4Network(f"{ip}/24", strict=False)
