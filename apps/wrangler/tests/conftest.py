"""Shared pytest fixtures for wrangler tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def wled_info_v0_15() -> dict:
    return json.loads((FIXTURES / "wled_info_v0_15.json").read_text())
