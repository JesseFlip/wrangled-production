"""Shared pytest fixtures for api tests."""

from __future__ import annotations

import socket

import pytest


@pytest.fixture
def unused_tcp_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
