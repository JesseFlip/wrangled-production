"""HTTP probe: fetch /json/info from a candidate IP and parse into a WledDevice."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from ipaddress import IPv4Address  # noqa: TC003
from typing import Literal

import httpx
from pydantic import ValidationError
from wrangled_contracts import WledDevice, WledMatrix

logger = logging.getLogger(__name__)


async def probe_device(
    client: httpx.AsyncClient,
    ip: IPv4Address,
    *,
    source: Literal["mdns", "sweep"],
    timeout: float = 2.0,  # noqa: ASYNC109
) -> WledDevice | None:
    """Probe a single IP. Return a WledDevice or None if not a responsive WLED."""
    url = f"http://{ip}/json/info"
    try:
        response = await client.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        logger.debug("probe %s: transport error: %s", ip, exc)
        return None

    if response.status_code != httpx.codes.OK:
        logger.debug("probe %s: status %s", ip, response.status_code)
        return None

    try:
        info = response.json()
    except ValueError:
        logger.debug("probe %s: non-JSON body", ip)
        return None

    if not isinstance(info, dict) or "leds" not in info or "mac" not in info:
        logger.debug("probe %s: not a WLED info response", ip)
        return None

    return _info_to_device(info, ip=ip, source=source)


def _info_to_device(
    info: dict,
    *,
    ip: IPv4Address,
    source: Literal["mdns", "sweep"],
) -> WledDevice | None:
    leds = info.get("leds") or {}
    matrix_raw = leds.get("matrix") if isinstance(leds, dict) else None
    matrix = None
    if isinstance(matrix_raw, dict) and "w" in matrix_raw and "h" in matrix_raw:
        try:
            matrix = WledMatrix(width=int(matrix_raw["w"]), height=int(matrix_raw["h"]))
        except (ValueError, ValidationError) as exc:
            logger.debug("probe %s: bad matrix: %s", ip, exc)
            matrix = None

    try:
        return WledDevice(
            ip=ip,
            name=str(info.get("name") or f"WLED-{ip}"),
            mac=str(info["mac"]),
            version=str(info.get("ver") or "unknown"),
            led_count=int(leds.get("count", 0)) or 1,
            matrix=matrix,
            udp_port=_maybe_int(info.get("udpport")),
            raw_info=info,
            discovered_via=source,
            discovered_at=datetime.now(tz=UTC),
        )
    except (ValueError, ValidationError) as exc:
        logger.debug("probe %s: failed validation: %s", ip, exc)
        return None


def _maybe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
