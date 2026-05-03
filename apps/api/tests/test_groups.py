"""Tests for device group store and CRUD routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.auth import AuthChecker
from api.server.groups import DeviceGroupStore, build_groups_router

AUTH_HEADERS = {"Authorization": "Bearer secret"}


def _make_client() -> TestClient:
    app = FastAPI()
    store = DeviceGroupStore()
    checker = AuthChecker("secret")
    app.include_router(build_groups_router(store, checker))
    return TestClient(app)


def test_list_groups_includes_all_by_default() -> None:
    client = _make_client()
    resp = client.get("/api/groups", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    groups = resp.json()["groups"]
    names = [g["name"] for g in groups]
    assert "all" in names


def test_create_and_list_group() -> None:
    client = _make_client()
    # Create a group
    resp = client.post(
        "/api/groups",
        json={"name": "stage", "macs": ["aa:bb:cc:dd:ee:ff"]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "stage"
    assert resp.json()["macs"] == ["aa:bb:cc:dd:ee:ff"]

    # Verify it appears in the list
    resp = client.get("/api/groups", headers=AUTH_HEADERS)
    names = [g["name"] for g in resp.json()["groups"]]
    assert "stage" in names
    assert "all" in names


def test_delete_group() -> None:
    client = _make_client()
    # Create then delete
    client.post(
        "/api/groups",
        json={"name": "temp", "macs": []},
        headers=AUTH_HEADERS,
    )
    resp = client.delete("/api/groups/temp", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify gone
    resp = client.get("/api/groups", headers=AUTH_HEADERS)
    names = [g["name"] for g in resp.json()["groups"]]
    assert "temp" not in names


def test_cannot_delete_all_group() -> None:
    client = _make_client()
    resp = client.delete("/api/groups/all", headers=AUTH_HEADERS)
    assert resp.status_code == 400
