"""Tests for metadata endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from wrangler.server import create_app


def test_get_effects_returns_curated_list() -> None:
    client = TestClient(create_app(initial_scan=False))
    response = client.get("/api/effects")
    assert response.status_code == 200
    data = response.json()
    effects = set(data["effects"])
    # Original 10 + Jesse's 4 PyTexas additions
    assert effects >= {"solid", "fire", "rainbow", "matrix", "sparkle"}
    assert effects >= {"plasma", "metaballs", "wavingcell", "blink"}
    assert len(effects) >= 14


def test_get_presets_returns_all() -> None:
    client = TestClient(create_app(initial_scan=False))
    response = client.get("/api/presets")
    assert response.status_code == 200
    presets = set(response.json()["presets"])
    assert presets >= {"pytexas", "party", "chill"}
    assert presets >= {"snake_attack", "howdy"}
    assert len(presets) >= 32


def test_get_emoji_returns_mapping() -> None:
    client = TestClient(create_app(initial_scan=False))
    response = client.get("/api/emoji")
    assert response.status_code == 200
    data = response.json()["emoji"]
    assert data["🔥"] == "fire"
    assert data["🌈"] == "rainbow"
    assert data["💙"] == "color(0,0,255)"
    assert data["🖤"] == "power(off)"
