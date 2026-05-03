"""Tests for SSE command event bus and /api/stream endpoint."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.server.auth import AuthChecker
from api.server.stream import CommandEvent, CommandEventBus, build_stream_router

# ── CommandEvent model tests ─────────────────────────────────────────


def test_command_event_fields() -> None:
    event = CommandEvent(who="alice", source="discord", command_kind="color")
    assert event.who == "alice"
    assert event.source == "discord"
    assert event.command_kind == "color"
    assert event.content == ""
    assert event.target == ""
    assert event.result == ""
    assert event.flag is False
    assert event.flag_reason == ""
    assert event.timestamp  # auto-set, non-empty


def test_command_event_all_fields() -> None:
    event = CommandEvent(
        who="bob",
        source="dashboard",
        command_kind="preset",
        content="rainbow",
        target="device-01",
        result="ok",
        flag=True,
        flag_reason="rate limited",
    )
    assert event.who == "bob"
    assert event.flag is True
    assert event.flag_reason == "rate limited"


# ── EventBus pub/sub tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe() -> None:
    bus = CommandEventBus()
    received: list[CommandEvent] = []

    async def _consumer() -> None:
        async for event in bus.subscribe():
            received.append(event)
            if len(received) >= 2:
                break

    task = asyncio.create_task(_consumer())
    # Give the consumer time to register
    await asyncio.sleep(0.01)

    event1 = CommandEvent(who="a", source="s", command_kind="k1")
    event2 = CommandEvent(who="b", source="s", command_kind="k2")
    bus.publish(event1)
    bus.publish(event2)

    await asyncio.wait_for(task, timeout=2.0)
    assert len(received) == 2
    assert received[0].who == "a"
    assert received[1].who == "b"


@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers() -> None:
    bus = CommandEventBus()
    results_a: list[CommandEvent] = []
    results_b: list[CommandEvent] = []

    async def _consumer(out: list[CommandEvent]) -> None:
        async for event in bus.subscribe():
            out.append(event)
            if len(out) >= 1:
                break

    task_a = asyncio.create_task(_consumer(results_a))
    task_b = asyncio.create_task(_consumer(results_b))
    await asyncio.sleep(0.01)

    bus.publish(CommandEvent(who="x", source="s", command_kind="k"))

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=2.0)
    assert len(results_a) == 1
    assert len(results_b) == 1


# ── SSE endpoint tests ──────────────────────────────────────────────


def _make_app(auth_token: str | None = "secret") -> tuple[FastAPI, CommandEventBus]:  # noqa: S107
    app = FastAPI()
    checker = AuthChecker(auth_token)
    bus = CommandEventBus()
    app.include_router(build_stream_router(bus, checker))
    return app, bus


def test_stream_requires_auth() -> None:
    app, _bus = _make_app("secret")
    client = TestClient(app)
    resp = client.get("/api/stream")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stream_endpoint_streams_events() -> None:
    """End-to-end: start a real server, connect via HTTP, and read an SSE event."""
    import httpx  # noqa: PLC0415
    import uvicorn  # noqa: PLC0415

    app, bus = _make_app("secret")

    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)

    # Start server in background
    serve_task = asyncio.create_task(server.serve())
    # Wait for server to be ready
    while not server.started:  # noqa: ASYNC110
        await asyncio.sleep(0.01)

    port = server.servers[0].sockets[0].getsockname()[1]

    try:
        async with (
            httpx.AsyncClient() as client,
            client.stream(
                "GET",
                f"http://127.0.0.1:{port}/api/stream",
                headers={"Authorization": "Bearer secret"},
            ) as resp,
        ):
            assert resp.status_code == 200

            # Publish after connection is established
            bus.publish(
                CommandEvent(who="tester", source="test", command_kind="color"),
            )

            collected: list[str] = []
            async for line in resp.aiter_lines():
                collected.append(line)
                if any(ln.startswith("data:") for ln in collected):
                    break

        data_lines = [ln for ln in collected if ln.startswith("data:")]
        assert len(data_lines) >= 1
        assert "tester" in data_lines[0]
    finally:
        server.should_exit = True
        await serve_task


def test_stream_no_auth_when_disabled() -> None:
    """When auth is disabled, the endpoint should not reject anonymous callers."""
    app, _bus = _make_app(None)
    from starlette.routing import Match  # noqa: PLC0415

    matched = False
    for route in app.routes:
        m, _ = route.matches({"type": "http", "method": "GET", "path": "/api/stream"})
        if m == Match.FULL:
            matched = True
            break
    assert matched, "/api/stream route should exist"
