"""Tests for wrangler.scanner.netinfo."""

from __future__ import annotations

from ipaddress import IPv4Network
from unittest.mock import patch

import pytest

from wrangler.scanner.netinfo import NoSubnetDetectedError, detect_default_subnet


def test_detect_default_subnet_returns_24() -> None:
    with patch("wrangler.scanner.netinfo._connect_probe", return_value="10.0.6.42"):
        subnet = detect_default_subnet()
    assert subnet == IPv4Network("10.0.6.0/24")


def test_detect_default_subnet_raises_on_failure() -> None:
    with (
        patch("wrangler.scanner.netinfo._connect_probe", return_value=None),
        pytest.raises(NoSubnetDetectedError),
    ):
        detect_default_subnet()
