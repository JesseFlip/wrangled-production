"""HTTP helpers for reading live state and setting the WLED device name."""

from __future__ import annotations

import json
import logging

import httpx
from wrangled_contracts import WledDevice  # noqa: TC002

logger = logging.getLogger(__name__)


class WledUnreachableError(RuntimeError):
    """Raised when a WLED device does not respond to a read or cfg write."""


async def fetch_state(
    client: httpx.AsyncClient,
    device: WledDevice,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> dict:
    """GET /json/state from the device. Raise WledUnreachableError on failure."""
    url = f"http://{device.ip}/json/state"
    try:
        response = await client.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        logger.debug("fetch_state %s: %s", device.ip, exc)
        msg = f"could not reach {device.ip}: {exc}"
        raise WledUnreachableError(msg) from exc

    if response.status_code != httpx.codes.OK:
        msg = f"{device.ip} returned {response.status_code}"
        raise WledUnreachableError(msg)

    try:
        return response.json()
    except ValueError as exc:
        msg = f"{device.ip} returned non-JSON body"
        raise WledUnreachableError(msg) from exc


async def set_name(
    client: httpx.AsyncClient,
    device: WledDevice,
    new_name: str,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> None:
    """POST to /json/cfg to change the device name on WLED itself."""
    url = f"http://{device.ip}/json/cfg"
    body = {"id": {"name": new_name}}
    try:
        response = await client.post(
            url,
            content=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        msg = f"could not reach {device.ip}: {exc}"
        raise WledUnreachableError(msg) from exc

    if response.status_code != httpx.codes.OK:
        msg = f"{device.ip} returned {response.status_code}"
        raise WledUnreachableError(msg)
