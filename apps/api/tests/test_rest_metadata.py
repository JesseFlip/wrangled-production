"""Tests for GET /api/effects, /api/presets, /api/emoji metadata endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_effects_includes_originals_and_pytexas_pack(client: TestClient) -> None:
    response = client.get("/api/effects")
    assert response.status_code == 200
    effects = set(response.json()["effects"])
    assert effects >= {"solid", "fire", "rainbow", "plasma", "blink"}
    assert len(effects) >= 14


def test_presets_includes_originals_and_pytexas_pack(client: TestClient) -> None:
    response = client.get("/api/presets")
    assert response.status_code == 200
    presets = set(response.json()["presets"])
    assert presets >= {"pytexas", "party", "chill", "snake_attack", "howdy"}
    assert len(presets) >= 13


def test_emoji_has_fire(client: TestClient) -> None:
    response = client.get("/api/emoji")
    assert response.status_code == 200
    data = response.json()
    assert "emoji" in data
    assert "🔥" in data["emoji"]
    entry = data["emoji"]["🔥"]
    # Jesse's format: {label, command} objects
    if isinstance(entry, dict):
        assert entry["label"] == "fire"
    else:
        assert entry == "fire"
