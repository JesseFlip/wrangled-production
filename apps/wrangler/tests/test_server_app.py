"""Tests for wrangler.server.app."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from wrangler.server import create_app

# Path that `app.py` uses when resolving the static dir.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "wrangler-ui"


def test_healthz_returns_ok() -> None:
    app = create_app(initial_scan=False)
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_root_reflects_ui_build_state() -> None:
    """When the UI dist exists, `/` serves it (200). Otherwise, `/` is 404.

    Both are valid outcomes — assert we graceful-handle each.
    """
    app = create_app(initial_scan=False)
    client = TestClient(app)
    response = client.get("/")
    if _STATIC_DIR.is_dir():
        assert response.status_code == 200
    else:
        assert response.status_code == 404
