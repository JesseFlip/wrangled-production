"""Pydantic models describing WLED devices and their topology."""

from __future__ import annotations

import re
from datetime import datetime  # noqa: TC003
from ipaddress import IPv4Address  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WledMatrix(BaseModel):
    """Dimensions of a WLED 2D matrix, in LED count."""

    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0, description="Columns of LEDs.")
    height: int = Field(gt=0, description="Rows of LEDs.")


_MAC_CLEAN_RE = re.compile(r"[^0-9a-fA-F]")
_MAC_HEX_RE = re.compile(r"^[0-9a-f]{12}$")


class WledDevice(BaseModel):
    """A WLED device discovered on the local network."""

    model_config = ConfigDict(frozen=False)

    ip: IPv4Address
    name: str
    mac: str = Field(description="Canonical lowercase colon-separated MAC.")
    version: str
    led_count: int = Field(gt=0)
    matrix: WledMatrix | None = None
    udp_port: int | None = None
    raw_info: dict = Field(default_factory=dict, repr=False, exclude=True)
    discovered_via: Literal["mdns", "sweep"]
    discovered_at: datetime

    @field_validator("mac", mode="before")
    @classmethod
    def _canonicalize_mac(cls, value: object) -> str:
        if not isinstance(value, str):
            msg = "mac must be a string"
            raise TypeError(msg)
        cleaned = _MAC_CLEAN_RE.sub("", value).lower()
        if not _MAC_HEX_RE.match(cleaned):
            msg = f"invalid MAC address: {value!r}"
            raise ValueError(msg)
        return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))
