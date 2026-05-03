"""Public scanner API: mDNS-first discovery with sweep fallback."""

from __future__ import annotations

from collections.abc import Iterable  # noqa: TC003
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network  # noqa: TC003

import httpx
from wrangled_contracts import WledDevice  # noqa: TC002

from wrangler.scanner.mdns import discover_via_mdns
from wrangler.scanner.netinfo import detect_default_subnet
from wrangler.scanner.probe import probe_device
from wrangler.scanner.sweep import sweep_hosts

__all__ = [
    "ScanOptions",
    "detect_default_subnet",
    "discover_via_mdns",
    "probe_device",
    "scan",
    "sweep_hosts",
]


@dataclass(frozen=True)
class ScanOptions:
    """Configuration for a scan.

    sweep:
        None  → fallback: sweep only if mDNS finds nothing (default).
        True  → always sweep, in addition to mDNS (unless use_mdns=False).
        False → never sweep.
    """

    use_mdns: bool = True
    mdns_timeout: float = 3.0
    sweep: bool | None = None
    sweep_subnet: IPv4Network | None = None
    probe_timeout: float = 2.0
    probe_concurrency: int = 32
    include: Iterable[IPv4Address] = field(default_factory=tuple)


async def scan(opts: ScanOptions | None = None) -> list[WledDevice]:
    """Discover WLEDs on the LAN. Returns a deduped list sorted by IP."""
    opts = opts or ScanOptions()
    found_by_mac: dict[str, WledDevice] = {}

    mdns_candidates: set[IPv4Address] = set()
    if opts.use_mdns:
        mdns_candidates = await discover_via_mdns(timeout=opts.mdns_timeout)

    if mdns_candidates:
        async with httpx.AsyncClient() as client:
            for ip in mdns_candidates:
                device = await probe_device(
                    client,
                    ip,
                    source="mdns",
                    timeout=opts.probe_timeout,
                )
                if device is not None:
                    found_by_mac.setdefault(device.mac, device)

    should_sweep = opts.sweep is True or (opts.sweep is None and not found_by_mac)
    if should_sweep:
        subnet = opts.sweep_subnet or detect_default_subnet()
        sweep_results = await sweep_hosts(
            subnet.hosts(),
            timeout=opts.probe_timeout,
            concurrency=opts.probe_concurrency,
        )
        for device in sweep_results:
            found_by_mac.setdefault(device.mac, device)

    return sorted(found_by_mac.values(), key=lambda d: int(d.ip))
