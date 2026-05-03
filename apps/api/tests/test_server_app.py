"""Tests for api.server.app."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api.server import create_app

_STATIC = Path(__file__).resolve().parent.parent / "static" / "dashboard"


def test_healthz_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["wranglers"] == 0


def test_root_reflects_ui_build_state() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    if _STATIC.is_dir():
        assert response.status_code == 200
    else:
        assert response.status_code == 404
