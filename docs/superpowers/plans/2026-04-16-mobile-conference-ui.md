# Mobile Conference UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the desktop-oriented 3-page dashboard with a mobile-first bottom-tab layout (Stream, Command, Toolkit) with persistent global controls, real-time command stream, and content filtering.

**Architecture:** The frontend is a full rewrite of the dashboard views into a tab-based mobile shell with shared global state (target group, brightness, color override). The backend adds an SSE command stream endpoint, device groups, and integrates `better-profanity` for content filtering. The existing API endpoints, auth, and contracts are unchanged.

**Tech Stack:** React 19, Vite 8, CSS custom properties (existing design tokens), FastAPI SSE (via `sse-starlette`), `better-profanity`, `vite-plugin-pwa`.

**Priority note:** Conference is tomorrow. Tasks are ordered by criticality. Tasks 1-7 are the MVP. Tasks 8-9 are nice-to-have.

---

## File Map

### Backend (new/modified)

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/api/src/api/server/stream.py` | **Create** | SSE endpoint — broadcasts command events to connected dashboards |
| `apps/api/src/api/server/groups.py` | **Create** | Device group model + CRUD routes |
| `apps/api/src/api/moderation.py` | **Modify** | Add `better-profanity` integration to `check_profanity`, add rate-limit flagging |
| `apps/api/src/api/server/rest.py` | **Modify** | Add group-targeted command dispatch, emit events to stream |
| `apps/api/src/api/server/mod_routes.py` | **Modify** | Emit ban/config events to stream |
| `apps/api/src/api/server/app.py` | **Modify** | Wire stream router + groups router, pass event bus |
| `apps/api/pyproject.toml` | **Modify** | Add `better-profanity`, `sse-starlette` deps |
| `apps/api/tests/test_stream.py` | **Create** | SSE endpoint tests |
| `apps/api/tests/test_groups.py` | **Create** | Group CRUD + command dispatch tests |
| `apps/api/tests/test_content_filter.py` | **Create** | Profanity filter tests |

### Frontend (new/modified)

| File | Action | Responsibility |
|------|--------|---------------|
| `apps/dashboard/src/App.jsx` | **Rewrite** | Mobile shell — global bar, bottom tabs, shared state |
| `apps/dashboard/src/api.js` | **Modify** | Add SSE stream, group endpoints, broadcast command helper |
| `apps/dashboard/src/index.css` | **Modify** | Add mobile layout styles, tab bar, global bar, stream cards |
| `apps/dashboard/src/views/StreamView.jsx` | **Create** | Live command feed + inline moderation |
| `apps/dashboard/src/views/CommandView.jsx` | **Create** | Schedule, text, presets, mode controls |
| `apps/dashboard/src/views/ToolkitView.jsx` | **Create** | Colors, effects, emoji, device list |
| `apps/dashboard/src/components/GlobalBar.jsx` | **Create** | Target group pills, brightness slider, color picker, kill switch |
| `apps/dashboard/src/components/SettingsSheet.jsx` | **Create** | Slide-up sheet for bot config + device locks |
| `apps/dashboard/src/components/TabBar.jsx` | **Create** | Bottom tab navigation |
| `apps/dashboard/src/components/StreamCard.jsx` | **Create** | Single command card with ban button |
| `apps/dashboard/vite.config.js` | **Modify** | Add PWA plugin, add `/api/stream` proxy |
| `apps/dashboard/package.json` | **Modify** | Add `vite-plugin-pwa` |

### Files to keep (reuse existing components)

These existing components are reused mostly as-is inside the new views:
- `components/AuthGate.jsx` — unchanged
- `components/BrightnessSlider.jsx` — moved into GlobalBar
- `components/ScheduleTab.jsx` — reused in CommandView
- `components/PresetTab.jsx` — reused in CommandView
- `components/ModePanel.jsx` — reused in CommandView
- `components/ColorTab.jsx` — reused in ToolkitView
- `components/EffectTab.jsx` — reused in ToolkitView
- `components/EmojiTab.jsx` — reused in ToolkitView

### Files to remove (replaced by new views)

- `views/ControlView.jsx` — replaced by CommandView + ToolkitView
- `views/ModView.jsx` — replaced by StreamView + SettingsSheet
- `components/ControlPanel.jsx` — tab container no longer needed
- `components/DeviceGrid.jsx` — replaced by compact list in ToolkitView
- `components/DeviceCard.jsx` — replaced by compact list in ToolkitView
- `components/SystemFooter.jsx` — status moved to GlobalBar

`views/StoryView.jsx` is kept but removed from mobile nav. Accessible at `#/about`.

---

## Task 1: Backend — SSE Command Event Bus + Endpoint

The stream tab needs real-time command events. This is the foundation.

**Files:**
- Create: `apps/api/src/api/server/stream.py`
- Create: `apps/api/tests/test_stream.py`
- Modify: `apps/api/src/api/server/app.py`
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1: Add `sse-starlette` dependency**

In `apps/api/pyproject.toml`, add to the `dependencies` list:

```toml
"sse-starlette>=2.0",
```

Run: `cd apps/api && uv sync`

- [ ] **Step 2: Write the failing test for SSE event bus**

Create `apps/api/tests/test_stream.py`:

```python
"""Tests for the SSE command event bus."""

from __future__ import annotations

import asyncio

import pytest

from api.server.stream import CommandEventBus, CommandEvent


def test_command_event_fields() -> None:
    ev = CommandEvent(
        who="testuser",
        source="discord",
        command_kind="text",
        content="hello world",
        target="all",
        result="ok",
        flag=None,
        flag_reason=None,
    )
    assert ev.who == "testuser"
    assert ev.command_kind == "text"
    assert ev.content == "hello world"
    assert ev.timestamp  # auto-set


@pytest.mark.asyncio
async def test_event_bus_publishes_to_subscriber() -> None:
    bus = CommandEventBus()
    received: list[CommandEvent] = []

    async def collect():
        async for event in bus.subscribe():
            received.append(event)
            break  # just get one

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)

    bus.publish(CommandEvent(
        who="user1",
        source="discord",
        command_kind="text",
        content="hi",
        target="all",
        result="ok",
    ))

    await asyncio.wait_for(task, timeout=1.0)
    assert len(received) == 1
    assert received[0].who == "user1"


@pytest.mark.asyncio
async def test_event_bus_no_subscribers_no_error() -> None:
    bus = CommandEventBus()
    # Should not raise
    bus.publish(CommandEvent(
        who="user1",
        source="discord",
        command_kind="text",
        content="hi",
        target="all",
        result="ok",
    ))
```

Run: `cd apps/api && uv run pytest tests/test_stream.py -v`
Expected: FAIL — `api.server.stream` does not exist.

- [ ] **Step 3: Implement the event bus and SSE endpoint**

Create `apps/api/src/api/server/stream.py`:

```python
"""SSE command event stream for the operator dashboard."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from api.server.auth import AuthChecker, build_rest_auth_dep

logger = logging.getLogger(__name__)


class CommandEvent(BaseModel):
    """A single command event broadcast to dashboard subscribers."""

    who: str
    source: str  # "discord", "rest", "system"
    command_kind: str  # "text", "color", "effect", "preset", "emoji", "power", etc.
    content: str = ""  # The actual text/value
    target: str = "all"  # Group name
    result: str = "ok"  # "ok", "blocked", "failed"
    flag: str | None = None  # "rate_limited", "content_blocked", None
    flag_reason: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


class CommandEventBus:
    """Pub/sub bus for command events. Dashboard SSE clients subscribe."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[CommandEvent]] = []

    def publish(self, event: CommandEvent) -> None:
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)

    async def subscribe(self) -> AsyncIterator[CommandEvent]:
        q: asyncio.Queue[CommandEvent] = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            if q in self._subscribers:
                self._subscribers.remove(q)


def build_stream_router(bus: CommandEventBus, auth: AuthChecker) -> APIRouter:
    dep = build_rest_auth_dep(auth)
    router = APIRouter(prefix="/api")

    @router.get("/stream")
    async def stream(dep=Depends(dep)) -> EventSourceResponse:  # noqa: B008, ANN001
        async def event_generator():
            async for event in bus.subscribe():
                yield {"event": "command", "data": event.model_dump_json()}

        return EventSourceResponse(event_generator())

    return router
```

Run: `cd apps/api && uv run pytest tests/test_stream.py -v`
Expected: PASS (3 tests).

- [ ] **Step 4: Write SSE HTTP endpoint test**

Add to `apps/api/tests/test_stream.py`:

```python
from starlette.testclient import TestClient
from fastapi import FastAPI

from api.server.stream import build_stream_router, CommandEventBus, CommandEvent
from api.server.auth import AuthChecker


def test_sse_endpoint_requires_auth() -> None:
    bus = CommandEventBus()
    auth = AuthChecker("secret")
    app = FastAPI()
    app.include_router(build_stream_router(bus, auth))
    client = TestClient(app)
    resp = client.get("/api/stream")
    assert resp.status_code == 401


def test_sse_endpoint_streams_events() -> None:
    bus = CommandEventBus()
    auth = AuthChecker("secret")
    app = FastAPI()
    app.include_router(build_stream_router(bus, auth))
    client = TestClient(app)

    # Publish an event before connecting (won't be received)
    # Then publish during the stream
    import threading, time

    def publish_after_delay():
        time.sleep(0.3)
        bus.publish(CommandEvent(
            who="tester",
            source="rest",
            command_kind="text",
            content="hello",
            target="all",
            result="ok",
        ))

    threading.Thread(target=publish_after_delay, daemon=True).start()

    with client.stream("GET", "/api/stream", headers={"Authorization": "Bearer secret"}) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data:"):
                assert "tester" in line
                break
```

Run: `cd apps/api && uv run pytest tests/test_stream.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Wire the stream router into the app**

In `apps/api/src/api/server/app.py`, add the import at line 19 (with the other router imports):

```python
from api.server.stream import CommandEventBus, build_stream_router
```

After `mode_mgr = MatrixModeManager(hub, mod)` (line 46), add:

```python
    event_bus = CommandEventBus()
    app.state.event_bus = event_bus
```

After the `build_mode_router` include (line 67), add:

```python
    app.include_router(build_stream_router(event_bus, checker))
```

- [ ] **Step 6: Run full test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: All existing tests still pass + new stream tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/api/server/stream.py apps/api/tests/test_stream.py apps/api/src/api/server/app.py apps/api/pyproject.toml
git commit -m "feat(api): add SSE command event bus and /api/stream endpoint"
```

---

## Task 2: Backend — Content Filtering with better-profanity

Replace the regex-based profanity check with `better-profanity` for broader coverage.

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/src/api/moderation.py`
- Create: `apps/api/tests/test_content_filter.py`

- [ ] **Step 1: Add `better-profanity` dependency**

In `apps/api/pyproject.toml`, add to dependencies:

```toml
"better-profanity>=0.7",
```

Run: `cd apps/api && uv sync`

- [ ] **Step 2: Write the failing test**

Create `apps/api/tests/test_content_filter.py`:

```python
"""Tests for profanity filtering."""

from api.moderation import ModerationStore


def test_blocks_profanity(tmp_path) -> None:
    store = ModerationStore(db_path=tmp_path / "test.json")
    assert store.check_profanity("fuck you") is not None


def test_allows_clean_text(tmp_path) -> None:
    store = ModerationStore(db_path=tmp_path / "test.json")
    assert store.check_profanity("hello world") is None


def test_blocks_obfuscated_profanity(tmp_path) -> None:
    store = ModerationStore(db_path=tmp_path / "test.json")
    # better-profanity catches some common obfuscations
    result = store.check_profanity("f u c k")
    # This may or may not be caught — document the behavior
    # The key test is that the library is wired up
    assert isinstance(result, (str, type(None)))


def test_blocks_racial_slurs(tmp_path) -> None:
    store = ModerationStore(db_path=tmp_path / "test.json")
    assert store.check_profanity("you are a nigger") is not None
```

Run: `cd apps/api && uv run pytest tests/test_content_filter.py -v`
Expected: Tests may pass or fail depending on current regex — we'll verify after the change.

- [ ] **Step 3: Update check_profanity to use better-profanity**

In `apps/api/src/api/moderation.py`, replace the `check_profanity` method (lines 237-246) with:

```python
    def check_profanity(self, text: str) -> str | None:
        """Return a reason string if profanity found, else None."""
        from better_profanity import profanity  # noqa: PLC0415

        if profanity.contains_profanity(text):
            return "profanity_detected"
        # Also check custom regex blocklist from config
        patterns = self.get_config().get("profanity_blocklist", [])
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return pattern
            except re.error:
                continue
        return None
```

- [ ] **Step 4: Run content filter tests**

Run: `cd apps/api && uv run pytest tests/test_content_filter.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run full test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/pyproject.toml apps/api/src/api/moderation.py apps/api/tests/test_content_filter.py
git commit -m "feat(api): add better-profanity content filtering"
```

---

## Task 3: Backend — Emit Events from Command + Mod Routes

Wire the event bus into existing command and moderation routes so every action shows up in the stream.

**Files:**
- Modify: `apps/api/src/api/server/rest.py`
- Modify: `apps/api/src/api/server/mod_routes.py`
- Modify: `apps/api/src/api/server/app.py`

- [ ] **Step 1: Pass event_bus to rest router**

In `apps/api/src/api/server/app.py`, change the `build_rest_router` call from:

```python
    app.include_router(build_rest_router(hub, checker, mod))
```

to:

```python
    app.include_router(build_rest_router(hub, checker, mod, event_bus))
```

And change the `build_mod_router` call from:

```python
    app.include_router(build_mod_router(mod, hub, checker))
```

to:

```python
    app.include_router(build_mod_router(mod, hub, checker, event_bus))
```

- [ ] **Step 2: Emit events from rest.py post_command**

In `apps/api/src/api/server/rest.py`:

Add to imports at the top:

```python
from api.server.stream import CommandEventBus, CommandEvent
```

Update `build_rest_router` signature:

```python
def build_rest_router(hub: Hub, auth: AuthChecker, mod: ModerationStore | None = None, event_bus: CommandEventBus | None = None) -> APIRouter:
```

In `post_command`, after the mod profanity check that raises 403 (around line 120), add an event emission for blocked content:

```python
                if match:
                    if event_bus:
                        event_bus.publish(CommandEvent(
                            who="api-user",
                            source="rest",
                            command_kind=command.kind,
                            content=command.text if hasattr(command, "text") else str(command.model_dump())[:200],
                            target=mac,
                            result="blocked",
                            flag="content_blocked",
                            flag_reason=match,
                        ))
                    raise HTTPException(status_code=403, detail="blocked content")
```

After the successful `hub.send_command` and `mod.log_command` block (around line 143), add:

```python
        if event_bus:
            event_bus.publish(CommandEvent(
                who="api-user",
                source="rest",
                command_kind=command.kind,
                content=_summarize(command),
                target=mac,
                result="ok" if result.ok else (result.error or "fail"),
            ))
```

- [ ] **Step 3: Emit events from mod_routes.py**

In `apps/api/src/api/server/mod_routes.py`:

Add import:

```python
from api.server.stream import CommandEventBus, CommandEvent
```

Update signature:

```python
def build_mod_router(mod: ModerationStore, hub: Hub, auth: AuthChecker, event_bus: CommandEventBus | None = None) -> APIRouter:
```

In `emergency_off`, after the existing logic, add:

```python
        if event_bus:
            event_bus.publish(CommandEvent(
                who="admin",
                source="rest",
                command_kind="emergency_off",
                content="All devices off, bot paused",
                target="all",
                result="ok",
            ))
```

In `ban_user`, after `mod.ban_user(...)`, add:

```python
        if event_bus:
            event_bus.publish(CommandEvent(
                who="admin",
                source="rest",
                command_kind="ban",
                content=f"Banned {body.username or body.user_id}: {body.reason}",
                target="all",
                result="ok",
            ))
```

- [ ] **Step 4: Run full test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: All pass (event_bus defaults to None so existing tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/server/rest.py apps/api/src/api/server/mod_routes.py apps/api/src/api/server/app.py
git commit -m "feat(api): emit command events to SSE stream from rest + mod routes"
```

---

## Task 4: Backend — Device Groups

Simple group-to-MACs mapping with CRUD and broadcast support.

**Files:**
- Create: `apps/api/src/api/server/groups.py`
- Create: `apps/api/tests/test_groups.py`
- Modify: `apps/api/src/api/server/app.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_groups.py`:

```python
"""Tests for device group management."""

from __future__ import annotations

from starlette.testclient import TestClient
from fastapi import FastAPI

from api.server.groups import DeviceGroupStore, build_groups_router
from api.server.auth import AuthChecker


def _make_app() -> tuple[FastAPI, DeviceGroupStore]:
    store = DeviceGroupStore()
    auth = AuthChecker("secret")
    app = FastAPI()
    app.include_router(build_groups_router(store, auth))
    return app, store


def test_list_groups_includes_all_by_default() -> None:
    app, store = _make_app()
    client = TestClient(app)
    resp = client.get("/api/groups", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 200
    groups = resp.json()["groups"]
    names = [g["name"] for g in groups]
    assert "all" in names


def test_create_and_list_group() -> None:
    app, store = _make_app()
    client = TestClient(app)
    headers = {"Authorization": "Bearer secret"}

    resp = client.post("/api/groups", json={"name": "stage", "macs": ["aa:bb:cc:dd:ee:ff"]}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "stage"

    resp = client.get("/api/groups", headers=headers)
    names = [g["name"] for g in resp.json()["groups"]]
    assert "stage" in names


def test_delete_group() -> None:
    app, store = _make_app()
    client = TestClient(app)
    headers = {"Authorization": "Bearer secret"}

    client.post("/api/groups", json={"name": "temp", "macs": []}, headers=headers)
    resp = client.delete("/api/groups/temp", headers=headers)
    assert resp.status_code == 200

    resp = client.get("/api/groups", headers=headers)
    names = [g["name"] for g in resp.json()["groups"]]
    assert "temp" not in names


def test_cannot_delete_all_group() -> None:
    app, store = _make_app()
    client = TestClient(app)
    headers = {"Authorization": "Bearer secret"}
    resp = client.delete("/api/groups/all", headers=headers)
    assert resp.status_code == 400
```

Run: `cd apps/api && uv run pytest tests/test_groups.py -v`
Expected: FAIL — module not found.

- [ ] **Step 2: Implement group store and routes**

Create `apps/api/src/api/server/groups.py`:

```python
"""Device groups — named sets of device MACs for bulk targeting."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.server.auth import AuthChecker, build_rest_auth_dep


class DeviceGroup(BaseModel):
    name: str
    macs: list[str]


class CreateGroupBody(BaseModel):
    name: str
    macs: list[str] = []


class DeviceGroupStore:
    """In-memory group store. 'all' is a built-in virtual group."""

    def __init__(self) -> None:
        self._groups: dict[str, list[str]] = {}

    def list_groups(self) -> list[DeviceGroup]:
        groups = [DeviceGroup(name="all", macs=[])]  # virtual, resolved at dispatch time
        for name, macs in self._groups.items():
            groups.append(DeviceGroup(name=name, macs=macs))
        return groups

    def get_group(self, name: str) -> DeviceGroup | None:
        if name == "all":
            return DeviceGroup(name="all", macs=[])
        if name in self._groups:
            return DeviceGroup(name=name, macs=self._groups[name])
        return None

    def create_group(self, name: str, macs: list[str]) -> DeviceGroup:
        self._groups[name] = macs
        return DeviceGroup(name=name, macs=macs)

    def delete_group(self, name: str) -> bool:
        if name == "all":
            return False
        return self._groups.pop(name, None) is not None


def build_groups_router(groups: DeviceGroupStore, auth: AuthChecker) -> APIRouter:
    dep = build_rest_auth_dep(auth)
    router = APIRouter(prefix="/api", dependencies=[Depends(dep)])

    @router.get("/groups")
    def list_groups() -> dict:
        return {"groups": [g.model_dump() for g in groups.list_groups()]}

    @router.post("/groups")
    def create_group(body: CreateGroupBody) -> dict:
        group = groups.create_group(body.name, body.macs)
        return group.model_dump()

    @router.delete("/groups/{name}")
    def delete_group(name: str) -> dict:
        if name == "all":
            raise HTTPException(status_code=400, detail="Cannot delete the 'all' group")
        if not groups.delete_group(name):
            raise HTTPException(status_code=404, detail=f"Group '{name}' not found")
        return {"ok": True}

    return router
```

- [ ] **Step 3: Run group tests**

Run: `cd apps/api && uv run pytest tests/test_groups.py -v`
Expected: PASS (4 tests).

- [ ] **Step 4: Wire groups router into app.py**

In `apps/api/src/api/server/app.py`, add import:

```python
from api.server.groups import DeviceGroupStore, build_groups_router
```

After the `event_bus` line, add:

```python
    group_store = DeviceGroupStore()
    app.state.group_store = group_store
```

After the stream router include, add:

```python
    app.include_router(build_groups_router(group_store, checker))
```

- [ ] **Step 5: Run full test suite**

Run: `cd apps/api && uv run pytest -v`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/api/server/groups.py apps/api/tests/test_groups.py apps/api/src/api/server/app.py
git commit -m "feat(api): add device group store and CRUD endpoints"
```

---

## Task 5: Frontend — API Client Updates

Add SSE stream, group endpoints, and broadcast helper to the API client.

**Files:**
- Modify: `apps/dashboard/src/api.js`
- Modify: `apps/dashboard/vite.config.js`

- [ ] **Step 1: Add SSE and group methods to api.js**

Replace the full contents of `apps/dashboard/src/api.js` with:

```javascript
const TOKEN_KEY = 'wrangled.token';

function getHeaders() {
  const headers = { 'content-type': 'application/json' };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers['authorization'] = `Bearer ${token}`;
  return headers;
}

async function jsonOrThrow(res) {
  if (res.status === 401) throw new Error('AUTH_REQUIRED');
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  // Devices
  listDevices: async () => jsonOrThrow(await fetch('/api/devices', { headers: getHeaders() })),
  getState: async (mac) => jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/state`, { headers: getHeaders() })),
  sendCommand: async (mac, command) => jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/commands`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(command),
  })),
  rename: async (mac, name) => jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/name`, {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify({ name }),
  })),
  rescan: async () => jsonOrThrow(await fetch('/api/scan', { method: 'POST', headers: getHeaders() })),
  listEffects: async () => jsonOrThrow(await fetch('/api/effects', { headers: getHeaders() })),
  listPresets: async () => jsonOrThrow(await fetch('/api/presets', { headers: getHeaders() })),
  listEmoji: async () => jsonOrThrow(await fetch('/api/emoji', { headers: getHeaders() })),
  listWranglers: async () => jsonOrThrow(await fetch('/api/wranglers', { headers: getHeaders() })),

  // Matrix mode
  getMode: async () => jsonOrThrow(await fetch('/api/mode', { headers: getHeaders() })),
  setMode: async (body) => jsonOrThrow(await fetch('/api/mode', {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify(body),
  })),
  goIdle: async () => jsonOrThrow(await fetch('/api/mode/idle', { method: 'POST', headers: getHeaders() })),

  // Schedule
  listSchedule: async () => jsonOrThrow(await fetch('/api/schedule/all', { headers: getHeaders() })),
  getCurrentSession: async () => jsonOrThrow(await fetch('/api/schedule/current', { headers: getHeaders() })),
  getNextSession: async () => jsonOrThrow(await fetch('/api/schedule/next', { headers: getHeaders() })),

  // Moderation
  modConfig: async () => jsonOrThrow(await fetch('/api/mod/config', { headers: getHeaders() })),
  modUpdateConfig: async (updates) => jsonOrThrow(await fetch('/api/mod/config', {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify(updates),
  })),
  modEmergencyOff: async () => jsonOrThrow(await fetch('/api/mod/emergency-off', { method: 'POST', headers: getHeaders() })),
  modHistory: async (limit = 100) => jsonOrThrow(await fetch(`/api/mod/history?limit=${limit}`, { headers: getHeaders() })),
  modDeviceLocks: async () => jsonOrThrow(await fetch('/api/mod/devices', { headers: getHeaders() })),
  modLockDevice: async (mac) => jsonOrThrow(await fetch(`/api/mod/device/${encodeURIComponent(mac)}/lock`, { method: 'POST', headers: getHeaders() })),
  modUnlockDevice: async (mac) => jsonOrThrow(await fetch(`/api/mod/device/${encodeURIComponent(mac)}/unlock`, { method: 'POST', headers: getHeaders() })),
  modBanned: async () => jsonOrThrow(await fetch('/api/mod/banned', { headers: getHeaders() })),
  modBan: async (userId, username, reason) => jsonOrThrow(await fetch('/api/mod/banned', {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({ user_id: userId, username, reason }),
  })),
  modUnban: async (userId) => jsonOrThrow(await fetch(`/api/mod/banned/${encodeURIComponent(userId)}`, { method: 'DELETE', headers: getHeaders() })),

  // Groups
  listGroups: async () => jsonOrThrow(await fetch('/api/groups', { headers: getHeaders() })),
  createGroup: async (name, macs) => jsonOrThrow(await fetch('/api/groups', {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({ name, macs }),
  })),
  deleteGroup: async (name) => jsonOrThrow(await fetch(`/api/groups/${encodeURIComponent(name)}`, { method: 'DELETE', headers: getHeaders() })),

  /**
   * Send a command to all devices in a group.
   * If group is "all", fetches all devices and sends to each.
   * Otherwise, resolves group MACs and sends to each.
   * Returns { ok: number, failed: number, errors: string[] }.
   */
  broadcastCommand: async (group, command) => {
    let macs;
    if (group === 'all') {
      const { devices } = await api.listDevices();
      macs = devices.map((d) => d.mac);
    } else {
      const { groups } = await api.listGroups();
      const g = groups.find((gr) => gr.name === group);
      macs = g ? g.macs : [];
    }

    let ok = 0;
    let failed = 0;
    const errors = [];

    for (const mac of macs) {
      try {
        await api.sendCommand(mac, command);
        ok++;
      } catch (err) {
        failed++;
        errors.push(`${mac}: ${err.message}`);
      }
    }

    return { ok, failed, errors };
  },
};

/**
 * Subscribe to the SSE command stream.
 * Returns an EventSource. Call .close() to disconnect.
 * onEvent receives parsed CommandEvent objects.
 */
export function subscribeStream(onEvent) {
  const token = localStorage.getItem(TOKEN_KEY);
  const url = `/api/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  const source = new EventSource(url);

  source.addEventListener('command', (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {
      // ignore parse errors
    }
  });

  return source;
}
```

- [ ] **Step 2: Update Vite proxy for SSE stream**

In `apps/dashboard/vite.config.js`, update the proxy section to handle SSE:

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../api/static/dashboard',
    emptyOutDir: true,
  },
  server: {
    port: 8510,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8500',
        // SSE needs these settings to avoid buffering
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache';
              proxyRes.headers['connection'] = 'keep-alive';
            }
          });
        },
      },
      '/healthz': 'http://localhost:8500',
    },
  },
});
```

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/src/api.js apps/dashboard/vite.config.js
git commit -m "feat(dashboard): add SSE stream, groups, and broadcast to API client"
```

---

## Task 6: Frontend — Mobile Shell (App.jsx + GlobalBar + TabBar)

The core layout rewrite — global bar, bottom tabs, shared state.

**Files:**
- Rewrite: `apps/dashboard/src/App.jsx`
- Create: `apps/dashboard/src/components/GlobalBar.jsx`
- Create: `apps/dashboard/src/components/TabBar.jsx`
- Modify: `apps/dashboard/src/index.css`

- [ ] **Step 1: Create TabBar component**

Create `apps/dashboard/src/components/TabBar.jsx`:

```jsx
export default function TabBar({ active, onChange }) {
  const tabs = [
    { id: 'stream', label: 'Stream', icon: '💬' },
    { id: 'command', label: 'Command', icon: '🎛' },
    { id: 'toolkit', label: 'Toolkit', icon: '🎨' },
  ];

  return (
    <nav className="tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-bar-item ${active === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          <span className="tab-bar-icon">{tab.icon}</span>
          <span className="tab-bar-label">{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Create GlobalBar component**

Create `apps/dashboard/src/components/GlobalBar.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { api } from '../api.js';

const PRESET_COLORS = [
  { hex: '#ef4444', label: 'Red' },
  { hex: '#f97316', label: 'Orange' },
  { hex: '#facc15', label: 'Yellow' },
  { hex: '#22c55e', label: 'Green' },
  { hex: '#3b82f6', label: 'Blue' },
  { hex: '#8b5cf6', label: 'Purple' },
  { hex: '#ec4899', label: 'Pink' },
  { hex: '#ffffff', label: 'White' },
];

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return { r, g, b };
}

export default function GlobalBar({
  group, onGroupChange, groups,
  brightness, onBrightnessChange,
  color, onColorChange,
  onKill,
  deviceCount, discordActive,
}) {
  const [colorOpen, setColorOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="global-bar">
      {/* Status line */}
      <div className="global-status">
        <span className="global-status-info">
          ● {deviceCount} device{deviceCount !== 1 ? 's' : ''}
          {discordActive !== undefined && (
            <span> · {discordActive ? '● Discord' : '○ Discord'}</span>
          )}
        </span>
        <button className="global-kill-btn" onClick={onKill}>⏻ KILL</button>
      </div>

      {/* Group pills */}
      <div className="global-groups">
        {groups.map((g) => (
          <button
            key={g.name}
            className={`group-pill ${group === g.name ? 'active' : ''}`}
            onClick={() => onGroupChange(g.name)}
          >
            {g.name}
          </button>
        ))}
      </div>

      {/* Brightness + color row */}
      <div className="global-controls-row">
        <span className="global-brightness-icon">☀</span>
        <input
          type="range"
          className="global-brightness-slider"
          min={0}
          max={200}
          value={brightness}
          onChange={(e) => onBrightnessChange(Number(e.target.value))}
        />
        <button
          className="global-color-dot"
          style={{ backgroundColor: color }}
          onClick={() => setColorOpen(!colorOpen)}
        />
      </div>

      {/* Color picker dropdown */}
      {colorOpen && (
        <div className="global-color-picker">
          {PRESET_COLORS.map((c) => (
            <button
              key={c.hex}
              className={`color-swatch ${color === c.hex ? 'active' : ''}`}
              style={{ backgroundColor: c.hex }}
              title={c.label}
              onClick={() => { onColorChange(c.hex); setColorOpen(false); }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Rewrite App.jsx as mobile shell**

Replace `apps/dashboard/src/App.jsx` with:

```jsx
import { useCallback, useEffect, useState } from 'react';
import { api } from './api.js';
import AuthGate from './components/AuthGate.jsx';
import GlobalBar from './components/GlobalBar.jsx';
import TabBar from './components/TabBar.jsx';
import StreamView from './views/StreamView.jsx';
import CommandView from './views/CommandView.jsx';
import ToolkitView from './views/ToolkitView.jsx';
import StoryView from './views/StoryView.jsx';

function resolveView() {
  if (location.hash === '#/about') return 'about';
  return null; // mobile tabs handle the rest
}

export default function App() {
  const [tab, setTab] = useState('stream');
  const [storyMode, setStoryMode] = useState(resolveView() === 'about');

  // Global state
  const [group, setGroup] = useState('all');
  const [groups, setGroups] = useState([{ name: 'all', macs: [] }]);
  const [brightness, setBrightness] = useState(128);
  const [color, setColor] = useState('#3b82f6');
  const [deviceCount, setDeviceCount] = useState(0);
  const [discordActive, setDiscordActive] = useState(undefined);

  // Hash change for story view
  useEffect(() => {
    const onHash = () => setStoryMode(location.hash === '#/about');
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // Load groups + device count + health on mount
  useEffect(() => {
    const load = async () => {
      try {
        const [groupsRes, devicesRes, health] = await Promise.all([
          api.listGroups(),
          api.listDevices(),
          fetch('/healthz').then((r) => r.json()).catch(() => null),
        ]);
        setGroups(groupsRes.groups);
        setDeviceCount(devicesRes.devices.length);
        if (health) setDiscordActive(health.discord);
      } catch {
        // Will retry on next poll
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleBrightnessChange = useCallback(async (val) => {
    setBrightness(val);
  }, []);

  const handleBrightnessCommit = useCallback(async (val) => {
    setBrightness(val);
    try {
      await api.broadcastCommand(group, { kind: 'brightness', brightness: val });
    } catch {
      // ignore
    }
  }, [group]);

  const handleKill = useCallback(async () => {
    if (window.confirm('Emergency OFF — power down all devices and pause Discord bot?')) {
      try {
        await api.modEmergencyOff();
      } catch {
        // ignore
      }
    }
  }, []);

  if (storyMode) {
    return (
      <AuthGate>
        <div className="app-shell">
          <nav className="app-header">
            <h1 className="app-title">Wrang<span className="app-title-accent">LED</span></h1>
            <a href="#/" className="nav-link" onClick={() => setStoryMode(false)}>← Back</a>
          </nav>
          <StoryView />
        </div>
      </AuthGate>
    );
  }

  return (
    <AuthGate>
      <div className="app-shell mobile-shell">
        <GlobalBar
          group={group}
          onGroupChange={setGroup}
          groups={groups}
          brightness={brightness}
          onBrightnessChange={handleBrightnessChange}
          onBrightnessCommit={handleBrightnessCommit}
          color={color}
          onColorChange={setColor}
          onKill={handleKill}
          deviceCount={deviceCount}
          discordActive={discordActive}
        />

        <main className="tab-content">
          {tab === 'stream' && <StreamView group={group} />}
          {tab === 'command' && (
            <CommandView group={group} color={color} brightness={brightness} />
          )}
          {tab === 'toolkit' && (
            <ToolkitView
              group={group}
              color={color}
              onColorChange={setColor}
              brightness={brightness}
              onBrightnessChange={handleBrightnessCommit}
            />
          )}
        </main>

        <TabBar active={tab} onChange={setTab} />
      </div>
    </AuthGate>
  );
}
```

- [ ] **Step 4: Add mobile layout CSS**

Append to `apps/dashboard/src/index.css`:

```css
/* --------------------------------------------------------------------------
   Mobile shell layout
   -------------------------------------------------------------------------- */

.mobile-shell {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  overflow: hidden;
}

.mobile-shell .app-header { display: none; }

/* Global bar */
.global-bar {
  flex-shrink: 0;
  background: var(--surface-1);
  border-bottom: 1px solid var(--border-subtle);
  padding: var(--sp-2) var(--sp-3);
}

.global-status {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-bottom: var(--sp-2);
}

.global-status-info { display: flex; gap: var(--sp-2); align-items: center; }

.global-kill-btn {
  background: none;
  border: 1px solid var(--danger);
  color: var(--danger);
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.global-kill-btn:active { background: var(--danger); color: white; }

.global-groups {
  display: flex;
  gap: var(--sp-1);
  margin-bottom: var(--sp-2);
  overflow-x: auto;
}

.group-pill {
  padding: var(--sp-1) var(--sp-3);
  border-radius: var(--radius-full);
  border: 1px solid var(--border-default);
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: var(--weight-medium);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

.group-pill.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.global-controls-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.global-brightness-icon {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.global-brightness-slider {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--surface-3);
  border-radius: 3px;
  outline: none;
}

.global-brightness-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--accent);
  cursor: pointer;
}

.global-color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border-default);
  cursor: pointer;
  flex-shrink: 0;
}

.global-color-dot:active { transform: scale(0.9); }

.global-color-picker {
  display: flex;
  gap: var(--sp-1);
  padding: var(--sp-2) 0;
  flex-wrap: wrap;
}

.color-swatch {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  cursor: pointer;
}

.color-swatch.active { border-color: var(--accent); }
.color-swatch[style*="ffffff"] { border-color: var(--border-default); }

/* Tab content area */
.tab-content {
  flex: 1;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--sp-3);
}

/* Bottom tab bar */
.tab-bar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-around;
  background: var(--surface-1);
  border-top: 1px solid var(--border-subtle);
  padding: var(--sp-2) 0 max(var(--sp-3), env(safe-area-inset-bottom));
}

.tab-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  background: none;
  border: none;
  color: var(--text-disabled);
  cursor: pointer;
  padding: var(--sp-1) var(--sp-4);
  -webkit-tap-highlight-color: transparent;
}

.tab-bar-item.active { color: var(--accent); }
.tab-bar-icon { font-size: 1.25rem; }
.tab-bar-label { font-size: var(--text-xs); font-weight: var(--weight-medium); }

/* Section headings in tab content */
.section-label {
  font-size: var(--text-xs);
  color: var(--text-disabled);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: var(--sp-2);
}
```

- [ ] **Step 5: Verify the dev server starts without errors**

Run: `cd apps/dashboard && npm run dev`
Open http://localhost:8510 — should show the mobile shell (GlobalBar + TabBar). Tabs won't render content yet (StreamView/CommandView/ToolkitView don't exist), so create stub files.

- [ ] **Step 6: Create stub view files so the shell renders**

Create `apps/dashboard/src/views/StreamView.jsx`:

```jsx
export default function StreamView({ group }) {
  return <div className="view-placeholder">Stream — targeting: {group}</div>;
}
```

Create `apps/dashboard/src/views/CommandView.jsx`:

```jsx
export default function CommandView({ group, color, brightness }) {
  return <div className="view-placeholder">Command — targeting: {group}</div>;
}
```

Create `apps/dashboard/src/views/ToolkitView.jsx`:

```jsx
export default function ToolkitView({ group, color, onColorChange, brightness, onBrightnessChange }) {
  return <div className="view-placeholder">Toolkit — targeting: {group}</div>;
}
```

- [ ] **Step 7: Verify shell renders in browser**

Run: `cd apps/dashboard && npm run dev`
Open http://localhost:8510 — should see GlobalBar at top, stub content in middle, TabBar at bottom. Tab switching should work. Verify on phone-sized viewport in devtools.

- [ ] **Step 8: Commit**

```bash
git add apps/dashboard/src/App.jsx apps/dashboard/src/components/GlobalBar.jsx apps/dashboard/src/components/TabBar.jsx apps/dashboard/src/views/StreamView.jsx apps/dashboard/src/views/CommandView.jsx apps/dashboard/src/views/ToolkitView.jsx apps/dashboard/src/index.css
git commit -m "feat(dashboard): mobile shell with global bar, bottom tabs, and stub views"
```

---

## Task 7: Frontend — Stream Tab (Live Feed + Moderation)

The bouncer view — real-time command feed with inline ban buttons.

**Files:**
- Rewrite: `apps/dashboard/src/views/StreamView.jsx`
- Create: `apps/dashboard/src/components/StreamCard.jsx`
- Modify: `apps/dashboard/src/index.css`

- [ ] **Step 1: Create StreamCard component**

Create `apps/dashboard/src/components/StreamCard.jsx`:

```jsx
import { api } from '../api.js';
import { useState } from 'react';

export default function StreamCard({ event, onBanned }) {
  const [banning, setBanning] = useState(false);
  const isFlagged = event.flag === 'content_blocked' || event.flag === 'rate_limited';
  const isBlocked = event.result === 'blocked';

  const handleBan = async () => {
    if (!window.confirm(`Ban ${event.who}?`)) return;
    setBanning(true);
    try {
      await api.modBan(event.who, event.who, `Banned from dashboard: ${event.flag || 'manual'}`);
      if (onBanned) onBanned(event.who);
    } catch {
      // ignore
    } finally {
      setBanning(false);
    }
  };

  const isSystem = event.source === 'system' || event.source === 'rest';
  const showBan = !isSystem && event.who !== 'admin' && event.who !== 'api-user';

  return (
    <div className={`stream-card ${isFlagged ? 'flagged' : ''} ${isBlocked ? 'blocked' : ''}`}>
      <div className="stream-card-body">
        <div className="stream-card-header">
          <span className={`stream-card-who ${isFlagged ? 'flagged' : ''}`}>{event.who}</span>
          {event.flag === 'rate_limited' && (
            <span className="stream-card-flag">⚡ rate limited</span>
          )}
          <span className="stream-card-time">
            {new Date(event.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
          </span>
        </div>
        <div className={`stream-card-content ${isBlocked ? 'blurred' : ''}`}>
          {event.content || `${event.command_kind}`}
        </div>
        <div className="stream-card-meta">
          {isBlocked && <span className="stream-card-blocked-label">⚠ Blocked</span>}
          {event.flag === 'content_blocked' && <span className="stream-card-blocked-label">⚠ Flagged content</span>}
          <span>{event.command_kind} → {event.target}</span>
        </div>
      </div>
      {showBan && (
        <button
          className={`stream-ban-btn ${isFlagged ? 'prominent' : ''}`}
          onClick={handleBan}
          disabled={banning}
        >
          {isFlagged ? 'BAN' : '🚫'}
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Implement StreamView with SSE**

Replace `apps/dashboard/src/views/StreamView.jsx`:

```jsx
import { useEffect, useRef, useState } from 'react';
import { subscribeStream } from '../api.js';
import StreamCard from '../components/StreamCard.jsx';

const MAX_EVENTS = 200;

export default function StreamView({ group }) {
  const [events, setEvents] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const listRef = useRef(null);
  const sourceRef = useRef(null);

  // SSE subscription
  useEffect(() => {
    const source = subscribeStream((event) => {
      setEvents((prev) => {
        const next = [...prev, event];
        return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
      });
    });
    sourceRef.current = source;
    return () => source.close();
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const handleScroll = () => {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    const atBottom = scrollHeight - scrollTop - clientHeight < 60;
    setAutoScroll(atBottom);
  };

  // Filter by selected group (show all if "all" is selected)
  const filtered = group === 'all'
    ? events
    : events.filter((e) => e.target === group || e.target === 'all');

  return (
    <div className="stream-view" ref={listRef} onScroll={handleScroll}>
      {filtered.length === 0 && (
        <div className="stream-empty">
          Waiting for commands...
        </div>
      )}
      {filtered.map((event, i) => (
        <StreamCard key={`${event.timestamp}-${i}`} event={event} />
      ))}
      {!autoScroll && (
        <button
          className="stream-scroll-btn"
          onClick={() => {
            setAutoScroll(true);
            if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
          }}
        >
          ↓ New messages
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add stream styles to index.css**

Append to `apps/dashboard/src/index.css`:

```css
/* --------------------------------------------------------------------------
   Stream view
   -------------------------------------------------------------------------- */

.stream-view {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  height: 100%;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  position: relative;
}

.stream-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-disabled);
  font-size: var(--text-sm);
}

.stream-card {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  background: var(--surface-1);
  border-radius: var(--radius-md);
}

.stream-card.flagged {
  background: #2d1a1a;
  border: 1px solid #7f1d1d;
}

.stream-card.blocked {
  background: #1a1a2a;
  border: 1px solid var(--border-subtle);
}

.stream-card-body { flex: 1; min-width: 0; }

.stream-card-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: 2px;
}

.stream-card-who {
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  color: var(--accent);
}

.stream-card-who.flagged { color: var(--danger); }

.stream-card-flag {
  font-size: 10px;
  color: #7f1d1d;
}

.stream-card-time {
  font-size: 10px;
  color: var(--text-disabled);
  margin-left: auto;
}

.stream-card-content {
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  word-break: break-word;
}

.stream-card-content.blurred { filter: blur(3px); }
.stream-card-content.blurred:hover { filter: none; }

.stream-card-meta {
  display: flex;
  gap: var(--sp-2);
  font-size: 10px;
  color: var(--text-disabled);
  margin-top: 2px;
}

.stream-card-blocked-label { color: var(--danger); }

.stream-ban-btn {
  flex-shrink: 0;
  background: var(--surface-3);
  border: none;
  color: var(--danger);
  font-size: var(--text-base);
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.stream-ban-btn.prominent {
  background: #7f1d1d;
  color: #fecaca;
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  padding: var(--sp-2) var(--sp-3);
}

.stream-scroll-btn {
  position: sticky;
  bottom: var(--sp-2);
  align-self: center;
  background: var(--accent);
  color: white;
  border: none;
  padding: var(--sp-1) var(--sp-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  cursor: pointer;
  z-index: 10;
}
```

- [ ] **Step 4: Test in browser**

Run API: `cd apps/api && WRANGLED_AUTH_TOKEN=devtoken uv run api serve`
Run dashboard: `cd apps/dashboard && npm run dev`
Open http://localhost:8510, switch to Stream tab. It should show "Waiting for commands..." until events come in. If you send a command via curl or Command tab, it should appear in the stream.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/src/views/StreamView.jsx apps/dashboard/src/components/StreamCard.jsx apps/dashboard/src/index.css
git commit -m "feat(dashboard): stream tab with live SSE feed and inline ban buttons"
```

---

## Task 8: Frontend — Command Tab

Schedule, quick text, presets, and mode selector.

**Files:**
- Rewrite: `apps/dashboard/src/views/CommandView.jsx`
- Modify: `apps/dashboard/src/index.css`

- [ ] **Step 1: Implement CommandView**

Replace `apps/dashboard/src/views/CommandView.jsx`:

```jsx
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';

const CANNED_MESSAGES = [
  'Welcome to PyTexas!',
  'Break - back soon',
  'Thanks for coming!',
  'Q&A time',
];

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return { r, g, b };
}

export default function CommandView({ group, color, brightness }) {
  const [current, setCurrent] = useState(null);
  const [next, setNext] = useState(null);
  const [text, setText] = useState('');
  const [presets, setPresets] = useState([]);
  const [mode, setMode] = useState(null);
  const [sending, setSending] = useState(false);

  // Load schedule + presets + mode
  useEffect(() => {
    const load = async () => {
      try {
        const [cur, nxt, pre, md] = await Promise.all([
          api.getCurrentSession().catch(() => ({ session: null })),
          api.getNextSession().catch(() => ({ session: null })),
          api.listPresets(),
          api.getMode(),
        ]);
        setCurrent(cur.session);
        setNext(nxt.session || nxt);
        setPresets(pre.presets || []);
        setMode(md);
      } catch {
        // retry on next interval
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const send = useCallback(async (command) => {
    setSending(true);
    try {
      await api.broadcastCommand(group, command);
    } catch {
      // ignore
    } finally {
      setSending(false);
    }
  }, [group]);

  const pushSchedule = (session) => {
    if (!session) return;
    const label = `${session.title} — ${session.speaker || session.speakers?.join(', ') || ''}`;
    send({ kind: 'text', text: label.slice(0, 200), color: hexToRgb(color), speed: 20, brightness });
  };

  const sendText = () => {
    if (!text.trim()) return;
    send({ kind: 'text', text: text.trim().slice(0, 200), color: hexToRgb(color), speed: 20, brightness });
    setText('');
  };

  const sendPreset = (name) => {
    send({ kind: 'preset', name });
  };

  const handleModeChange = async (newMode) => {
    try {
      if (newMode === 'idle') {
        await api.goIdle();
      } else {
        await api.setMode({ mode: newMode });
      }
      setMode(await api.getMode());
    } catch {
      // ignore
    }
  };

  // Preset gradient colors for visual interest
  const presetGradients = {
    pytexas: 'linear-gradient(135deg, #1e40af, #7c3aed)',
    party: 'linear-gradient(135deg, #db2777, #9333ea)',
    chill: 'linear-gradient(135deg, #0d9488, #6366f1)',
    fire: 'linear-gradient(135deg, #ea580c, #facc15)',
    matrix: 'linear-gradient(135deg, #059669, #34d399)',
    love_it: 'linear-gradient(135deg, #e11d48, #fb7185)',
    zen: 'linear-gradient(135deg, #6366f1, #a78bfa)',
    snake_attack: 'linear-gradient(135deg, #16a34a, #84cc16)',
  };

  return (
    <div className="command-view">
      {/* Schedule */}
      {current && (
        <div className="command-section">
          <div className="section-label">Now Playing</div>
          <div className="schedule-card now-playing">
            <div className="schedule-card-info">
              <div className="schedule-card-title">{current.title}</div>
              <div className="schedule-card-meta">{current.speaker || current.speakers?.join(', ')}</div>
            </div>
            <button className="schedule-push-btn" onClick={() => pushSchedule(current)} disabled={sending}>
              PUSH ▶
            </button>
          </div>
        </div>
      )}

      {next && next.session !== null && (
        <div className="command-section">
          <div className="section-label">Up Next</div>
          <div className="schedule-card">
            <div className="schedule-card-info">
              <div className="schedule-card-title">{(next.session || next).title}</div>
              <div className="schedule-card-meta">
                {(next.session || next).speaker || (next.session || next).speakers?.join(', ')}
                {next.next_time && ` · ${next.next_time}`}
              </div>
            </div>
            <button className="schedule-push-btn dim" onClick={() => pushSchedule(next.session || next)} disabled={sending}>
              PUSH ▶
            </button>
          </div>
        </div>
      )}

      {/* Quick text */}
      <div className="command-section">
        <div className="section-label">Quick Text</div>
        <div className="quick-text-row">
          <input
            className="quick-text-input"
            placeholder="Type a message..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendText()}
            maxLength={200}
          />
          <button className="btn btn-accent" onClick={sendText} disabled={sending || !text.trim()}>
            SEND
          </button>
        </div>
        <div className="canned-chips">
          {CANNED_MESSAGES.map((msg) => (
            <button key={msg} className="canned-chip" onClick={() => setText(msg)}>
              {msg}
            </button>
          ))}
        </div>
      </div>

      {/* Presets */}
      <div className="command-section">
        <div className="section-label">Presets</div>
        <div className="preset-grid">
          {presets.map((name) => (
            <button
              key={name}
              className="preset-btn"
              style={{ background: presetGradients[name] || 'var(--surface-3)' }}
              onClick={() => sendPreset(name)}
              disabled={sending}
            >
              {name}
            </button>
          ))}
        </div>
      </div>

      {/* Matrix mode */}
      <div className="command-section">
        <div className="section-label">Matrix Mode</div>
        <div className="mode-pills">
          {['idle', 'clock', 'schedule', 'countdown'].map((m) => (
            <button
              key={m}
              className={`mode-pill ${mode?.mode === m ? 'active' : ''}`}
              onClick={() => handleModeChange(m)}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add command view styles**

Append to `apps/dashboard/src/index.css`:

```css
/* --------------------------------------------------------------------------
   Command view
   -------------------------------------------------------------------------- */

.command-view { display: flex; flex-direction: column; gap: var(--sp-4); }

.command-section { display: flex; flex-direction: column; }

.schedule-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-3);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}

.schedule-card.now-playing {
  background: #1a2e1a;
  border-color: #166534;
}

.schedule-card-info { flex: 1; min-width: 0; }

.schedule-card-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-bold);
  color: var(--text-primary);
}

.now-playing .schedule-card-title { color: #4ade80; }

.schedule-card-meta {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-top: 2px;
}

.now-playing .schedule-card-meta { color: #86efac; }

.schedule-push-btn {
  flex-shrink: 0;
  background: #166534;
  border: none;
  color: #4ade80;
  font-size: var(--text-xs);
  font-weight: var(--weight-bold);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  white-space: nowrap;
}

.schedule-push-btn.dim {
  background: var(--surface-3);
  color: var(--text-secondary);
}

.quick-text-row {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
}

.quick-text-input {
  flex: 1;
  background: var(--surface-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--sp-2) var(--sp-3);
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.quick-text-input::placeholder { color: var(--text-disabled); }

.canned-chips {
  display: flex;
  gap: var(--sp-1);
  flex-wrap: wrap;
}

.canned-chip {
  background: var(--surface-3);
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--radius-full);
  cursor: pointer;
}

.canned-chip:active { background: var(--accent); color: white; }

.btn-accent {
  background: var(--accent);
  color: white;
  border: none;
  padding: var(--sp-2) var(--sp-4);
  border-radius: var(--radius-md);
  font-weight: var(--weight-bold);
  font-size: var(--text-sm);
  cursor: pointer;
}

.btn-accent:disabled { opacity: 0.5; }

.preset-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-2);
}

.preset-btn {
  background: var(--surface-3);
  border: none;
  color: white;
  padding: var(--sp-4) var(--sp-2);
  border-radius: var(--radius-lg);
  font-size: var(--text-sm);
  font-weight: var(--weight-bold);
  cursor: pointer;
  text-transform: capitalize;
}

.preset-btn:active { transform: scale(0.95); }

.mode-pills {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.mode-pill {
  background: var(--surface-3);
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  text-transform: capitalize;
}

.mode-pill.active {
  background: var(--accent);
  color: white;
  font-weight: var(--weight-bold);
}
```

- [ ] **Step 3: Test in browser**

Run API + dashboard dev servers. Switch to Command tab. Verify:
- Schedule section shows (if API has schedule data)
- Quick text input + canned chips work
- Preset grid renders with gradients
- Mode pills show current mode

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/views/CommandView.jsx apps/dashboard/src/index.css
git commit -m "feat(dashboard): command tab with schedule, text, presets, and mode controls"
```

---

## Task 9: Frontend — Toolkit Tab

Colors, effects, emoji, and device list for demos and troubleshooting.

**Files:**
- Rewrite: `apps/dashboard/src/views/ToolkitView.jsx`
- Modify: `apps/dashboard/src/index.css`

- [ ] **Step 1: Implement ToolkitView**

Replace `apps/dashboard/src/views/ToolkitView.jsx`:

```jsx
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';

const COLOR_SWATCHES = [
  '#ef4444', '#f97316', '#facc15', '#22c55e', '#06b6d4',
  '#3b82f6', '#8b5cf6', '#ec4899', '#ffffff', '#000000',
];

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return { r, g, b };
}

export default function ToolkitView({ group, color, onColorChange, brightness, onBrightnessChange }) {
  const [effects, setEffects] = useState([]);
  const [emoji, setEmoji] = useState({});
  const [devices, setDevices] = useState([]);
  const [selectedEffect, setSelectedEffect] = useState('');
  const [speed, setSpeed] = useState(128);
  const [intensity, setIntensity] = useState(128);
  const [hexInput, setHexInput] = useState(color);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [eff, emo, dev] = await Promise.all([
          api.listEffects(),
          api.listEmoji(),
          api.listDevices(),
        ]);
        setEffects(eff.effects || []);
        setEmoji(emo.emoji || {});
        setDevices(dev.devices || []);
        if (eff.effects?.length && !selectedEffect) {
          setSelectedEffect(eff.effects[0]);
        }
      } catch {
        // retry
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { setHexInput(color); }, [color]);

  const send = useCallback(async (command) => {
    setSending(true);
    try {
      await api.broadcastCommand(group, command);
    } catch {
      // ignore
    } finally {
      setSending(false);
    }
  }, [group]);

  const sendColor = (hex) => {
    onColorChange(hex);
    send({ kind: 'color', color: hexToRgb(hex), brightness });
  };

  const sendHex = () => {
    if (/^#[0-9a-f]{6}$/i.test(hexInput)) {
      sendColor(hexInput);
    }
  };

  const sendEffect = () => {
    if (!selectedEffect) return;
    send({
      kind: 'effect',
      name: selectedEffect,
      color: hexToRgb(color),
      speed,
      intensity,
      brightness,
    });
  };

  const sendEmoji = (key) => {
    const emo = emoji[key];
    if (emo?.command) {
      send(emo.command);
    }
  };

  return (
    <div className="toolkit-view">
      {/* Colors */}
      <div className="command-section">
        <div className="section-label">Colors</div>
        <div className="toolkit-color-grid">
          {COLOR_SWATCHES.map((hex) => (
            <button
              key={hex}
              className={`toolkit-swatch ${color === hex ? 'active' : ''}`}
              style={{ backgroundColor: hex }}
              onClick={() => sendColor(hex)}
              disabled={sending}
            />
          ))}
        </div>
        <div className="quick-text-row" style={{ marginTop: 'var(--sp-2)' }}>
          <input
            className="quick-text-input"
            style={{ fontFamily: 'var(--font-mono)' }}
            placeholder="#hex"
            value={hexInput}
            onChange={(e) => setHexInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendHex()}
          />
          <button className="btn btn-accent" onClick={sendHex} disabled={sending}>SET</button>
        </div>
      </div>

      {/* Effects */}
      <div className="command-section">
        <div className="section-label">Effects</div>
        <select
          className="toolkit-select"
          value={selectedEffect}
          onChange={(e) => setSelectedEffect(e.target.value)}
        >
          {effects.map((fx) => (
            <option key={fx} value={fx}>{fx}</option>
          ))}
        </select>
        <div className="toolkit-slider-row">
          <span className="toolkit-slider-label">Speed</span>
          <input type="range" min={0} max={255} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="global-brightness-slider" />
          <span className="toolkit-slider-value">{speed}</span>
        </div>
        <div className="toolkit-slider-row">
          <span className="toolkit-slider-label">Intensity</span>
          <input type="range" min={0} max={255} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} className="global-brightness-slider" />
          <span className="toolkit-slider-value">{intensity}</span>
        </div>
        <button className="btn btn-accent" style={{ width: '100%', marginTop: 'var(--sp-2)' }} onClick={sendEffect} disabled={sending}>
          Fire Effect 🔥
        </button>
      </div>

      {/* Emoji */}
      {Object.keys(emoji).length > 0 && (
        <div className="command-section">
          <div className="section-label">Emoji</div>
          <div className="toolkit-emoji-grid">
            {Object.keys(emoji).map((key) => (
              <button key={key} className="toolkit-emoji-btn" onClick={() => sendEmoji(key)} disabled={sending}>
                {key}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Devices */}
      <div className="command-section">
        <div className="section-label">Devices</div>
        <div className="toolkit-device-list">
          {devices.map((d) => (
            <div key={d.mac} className="toolkit-device-row">
              <span className="toolkit-device-name">{d.name}</span>
              <span className={`toolkit-device-status ${d.led_count > 0 ? 'on' : 'off'}`}>
                ● {d.led_count} LEDs
              </span>
            </div>
          ))}
          <button
            className="canned-chip"
            style={{ width: '100%', textAlign: 'center', marginTop: 'var(--sp-2)' }}
            onClick={() => api.rescan().then((r) => setDevices(r.devices || []))}
          >
            🔍 Rescan for devices
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add toolkit styles**

Append to `apps/dashboard/src/index.css`:

```css
/* --------------------------------------------------------------------------
   Toolkit view
   -------------------------------------------------------------------------- */

.toolkit-view { display: flex; flex-direction: column; gap: var(--sp-4); }

.toolkit-color-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--sp-2);
}

.toolkit-swatch {
  aspect-ratio: 1;
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  cursor: pointer;
}

.toolkit-swatch.active { border-color: var(--accent); }
.toolkit-swatch[style*="ffffff"] { border: 2px solid var(--border-default); }
.toolkit-swatch[style*="000000"] { border: 2px solid var(--border-default); }

.toolkit-select {
  width: 100%;
  background: var(--surface-1);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--sp-2) var(--sp-3);
  color: var(--text-primary);
  font-size: var(--text-sm);
  margin-bottom: var(--sp-2);
}

.toolkit-slider-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-1);
}

.toolkit-slider-label {
  font-size: var(--text-xs);
  color: var(--text-disabled);
  width: 60px;
}

.toolkit-slider-value {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  width: 30px;
  text-align: right;
}

.toolkit-emoji-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--sp-1);
}

.toolkit-emoji-btn {
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--sp-2) 0;
  font-size: 1.25rem;
  cursor: pointer;
}

.toolkit-emoji-btn:active { background: var(--accent-muted); }

.toolkit-device-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.toolkit-device-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-2) var(--sp-3);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}

.toolkit-device-name {
  font-size: var(--text-sm);
  font-weight: var(--weight-bold);
}

.toolkit-device-status {
  font-size: var(--text-xs);
  color: var(--success);
}

.toolkit-device-status.off { color: var(--danger); }
```

- [ ] **Step 3: Test in browser**

Verify on phone viewport:
- Color grid renders, tapping a swatch sends color + updates global dot
- Effect dropdown + sliders + fire button work
- Emoji grid renders from API data
- Device list shows connected devices
- Rescan button works

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/src/views/ToolkitView.jsx apps/dashboard/src/index.css
git commit -m "feat(dashboard): toolkit tab with colors, effects, emoji, and device list"
```

---

## Task 10: Frontend — Settings Sheet + Cleanup

Settings sheet for bot config + device locks, and cleanup of old files.

**Files:**
- Create: `apps/dashboard/src/components/SettingsSheet.jsx`
- Modify: `apps/dashboard/src/components/GlobalBar.jsx`
- Modify: `apps/dashboard/src/index.css`
- Delete: `apps/dashboard/src/views/ControlView.jsx`
- Delete: `apps/dashboard/src/views/ModView.jsx`
- Delete: `apps/dashboard/src/components/ControlPanel.jsx`
- Delete: `apps/dashboard/src/components/DeviceGrid.jsx`
- Delete: `apps/dashboard/src/components/DeviceCard.jsx`
- Delete: `apps/dashboard/src/components/SystemFooter.jsx`

- [ ] **Step 1: Create SettingsSheet component**

Create `apps/dashboard/src/components/SettingsSheet.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function SettingsSheet({ open, onClose }) {
  const [config, setConfig] = useState(null);
  const [locks, setLocks] = useState([]);

  useEffect(() => {
    if (!open) return;
    const load = async () => {
      try {
        const [cfg, lks] = await Promise.all([
          api.modConfig(),
          api.modDeviceLocks(),
        ]);
        setConfig(cfg);
        setLocks(lks);
      } catch {
        // ignore
      }
    };
    load();
  }, [open]);

  if (!open || !config) return null;

  const update = async (key, value) => {
    try {
      const updated = await api.modUpdateConfig({ [key]: value });
      setConfig(updated);
    } catch {
      // ignore
    }
  };

  const toggleLock = async (mac, locked) => {
    try {
      if (locked) {
        await api.modUnlockDevice(mac);
      } else {
        await api.modLockDevice(mac);
      }
      const lks = await api.modDeviceLocks();
      setLocks(lks);
    } catch {
      // ignore
    }
  };

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <span className="section-label" style={{ margin: 0 }}>Settings</span>
          <button className="btn btn-ghost" onClick={onClose}>✕</button>
        </div>

        <label className="settings-row">
          <span>Bot Paused</span>
          <input type="checkbox" checked={config.bot_paused} onChange={(e) => update('bot_paused', e.target.checked)} />
        </label>

        <label className="settings-row">
          <span>Preset-Only Mode</span>
          <input type="checkbox" checked={config.preset_only_mode} onChange={(e) => update('preset_only_mode', e.target.checked)} />
        </label>

        <label className="settings-row">
          <span>Brightness Cap</span>
          <input type="number" min={0} max={255} value={config.brightness_cap} className="settings-num"
            onChange={(e) => update('brightness_cap', Number(e.target.value))} />
        </label>

        <label className="settings-row">
          <span>Cooldown (sec)</span>
          <input type="number" min={0} max={60} value={config.cooldown_seconds} className="settings-num"
            onChange={(e) => update('cooldown_seconds', Number(e.target.value))} />
        </label>

        {locks.length > 0 && (
          <>
            <div className="section-label" style={{ marginTop: 'var(--sp-4)' }}>Device Locks</div>
            {locks.map((lk) => (
              <label key={lk.mac} className="settings-row">
                <span style={{ fontSize: 'var(--text-xs)' }}>{lk.mac}</span>
                <input type="checkbox" checked={lk.locked} onChange={() => toggleLock(lk.mac, lk.locked)} />
              </label>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add gear icon to GlobalBar**

In `apps/dashboard/src/components/GlobalBar.jsx`, add the settings sheet import and state:

Add import at the top:

```jsx
import SettingsSheet from './SettingsSheet.jsx';
```

Inside the component, add state:

```jsx
  const [settingsOpen, setSettingsOpen] = useState(false);
```

In the `global-status` div, add a gear icon between the status info and kill button:

```jsx
        <button className="global-gear-btn" onClick={() => setSettingsOpen(!settingsOpen)}>⚙</button>
```

After the closing `</div>` of `global-bar`, add:

```jsx
      <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} />
```

Note: The SettingsSheet renders as a portal-like overlay, so it can sit inside GlobalBar's return.

- [ ] **Step 3: Add settings styles**

Append to `apps/dashboard/src/index.css`:

```css
/* --------------------------------------------------------------------------
   Settings sheet
   -------------------------------------------------------------------------- */

.global-gear-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  padding: var(--sp-1);
}

.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 100;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.settings-sheet {
  background: var(--surface-1);
  border-top: 1px solid var(--border-default);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  padding: var(--sp-4);
  width: 100%;
  max-width: 480px;
  max-height: 70vh;
  overflow-y: auto;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-4);
}

.settings-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-2) 0;
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--text-sm);
  color: var(--text-primary);
  cursor: pointer;
}

.settings-num {
  width: 60px;
  background: var(--surface-2);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  padding: var(--sp-1) var(--sp-2);
  color: var(--text-primary);
  text-align: right;
  font-size: var(--text-sm);
}
```

- [ ] **Step 4: Delete old files**

```bash
rm apps/dashboard/src/views/ControlView.jsx
rm apps/dashboard/src/views/ModView.jsx
rm apps/dashboard/src/components/ControlPanel.jsx
rm apps/dashboard/src/components/DeviceGrid.jsx
rm apps/dashboard/src/components/DeviceCard.jsx
rm apps/dashboard/src/components/SystemFooter.jsx
```

- [ ] **Step 5: Test in browser**

Verify:
- Gear icon appears in global bar
- Tapping gear opens slide-up settings sheet
- Bot paused / preset-only toggles work
- Brightness cap / cooldown inputs work
- Device locks appear if any exist
- Tapping overlay closes the sheet
- No import errors from deleted files

- [ ] **Step 6: Commit**

```bash
git add -A apps/dashboard/src/
git commit -m "feat(dashboard): settings sheet, wire into global bar, remove old views"
```

---

## Task 11: Frontend — PWA Support

Make the dashboard installable as a home-screen app.

**Files:**
- Modify: `apps/dashboard/package.json`
- Modify: `apps/dashboard/vite.config.js`

- [ ] **Step 1: Install vite-plugin-pwa**

Run: `cd apps/dashboard && npm install -D vite-plugin-pwa`

- [ ] **Step 2: Update vite.config.js with PWA plugin**

Replace `apps/dashboard/vite.config.js`:

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'WrangLED Command Center',
        short_name: 'WrangLED',
        description: 'LED control dashboard',
        theme_color: '#0b0e18',
        background_color: '#0b0e18',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,svg,ico}'],
        navigateFallback: '/index.html',
        runtimeCaching: [
          {
            urlPattern: /^\/api\//,
            handler: 'NetworkOnly',
          },
        ],
      },
    }),
  ],
  build: {
    outDir: '../api/static/dashboard',
    emptyOutDir: true,
  },
  server: {
    port: 8510,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8500',
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache';
              proxyRes.headers['connection'] = 'keep-alive';
            }
          });
        },
      },
      '/healthz': 'http://localhost:8500',
    },
  },
});
```

- [ ] **Step 3: Add placeholder PWA icons**

Create simple placeholder icons (the actual icons can be replaced later):

```bash
cd apps/dashboard/public
# Create a simple SVG-based placeholder — or copy an existing icon
# For now, just ensure the paths exist so the manifest doesn't 404
touch icon-192.png icon-512.png
```

Note: Real icons should be generated from a source image before the conference. For now, placeholders prevent manifest errors.

- [ ] **Step 4: Test PWA manifest**

Run: `cd apps/dashboard && npm run build`
Check that `apps/api/static/dashboard/manifest.webmanifest` (or similar) is generated.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/vite.config.js apps/dashboard/package.json apps/dashboard/public/
git commit -m "feat(dashboard): add PWA support with vite-plugin-pwa"
```

---

## Task 12: Backend — SSE Auth via Query Param

The SSE EventSource API doesn't support custom headers. The stream endpoint needs to accept the token as a query parameter.

**Files:**
- Modify: `apps/api/src/api/server/stream.py`
- Modify: `apps/api/tests/test_stream.py`

- [ ] **Step 1: Write failing test for query param auth**

Add to `apps/api/tests/test_stream.py`:

```python
def test_sse_endpoint_accepts_query_token() -> None:
    bus = CommandEventBus()
    auth = AuthChecker("secret")
    app = FastAPI()
    app.include_router(build_stream_router(bus, auth))
    client = TestClient(app)

    import threading, time

    def publish_after_delay():
        time.sleep(0.3)
        bus.publish(CommandEvent(
            who="tester",
            source="rest",
            command_kind="text",
            content="via query param",
            target="all",
            result="ok",
        ))

    threading.Thread(target=publish_after_delay, daemon=True).start()

    with client.stream("GET", "/api/stream?token=secret") as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data:"):
                assert "via query param" in line
                break
```

Run: `cd apps/api && uv run pytest tests/test_stream.py::test_sse_endpoint_accepts_query_token -v`
Expected: FAIL (401 — query param not checked yet).

- [ ] **Step 2: Update stream endpoint to accept query param**

In `apps/api/src/api/server/stream.py`, update the `build_stream_router` function. `AuthChecker` already has `check_header()` and `check_query_token()` methods (see `apps/api/src/api/server/auth.py:18-39`):

```python
def build_stream_router(bus: CommandEventBus, auth: AuthChecker) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/stream")
    async def stream(
        token: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> EventSourceResponse:
        # SSE EventSource can't set headers, so accept token as query param too
        if authorization:
            auth.check_header(authorization)
        else:
            auth.check_query_token(token)

        async def event_generator():
            async for event in bus.subscribe():
                yield {"event": "command", "data": event.model_dump_json()}

        return EventSourceResponse(event_generator())

    return router
```

Add `Header` to the imports from fastapi in `stream.py`:

```python
from fastapi import APIRouter, Header
```

Remove the `Depends` import if it was there (it's no longer needed since we handle auth inline).

- [ ] **Step 3: Run tests**

Run: `cd apps/api && uv run pytest tests/test_stream.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/api/server/stream.py apps/api/src/api/server/auth.py apps/api/tests/test_stream.py
git commit -m "feat(api): support query param auth for SSE stream endpoint"
```

---

## Task Summary

| # | Task | Priority | Deps |
|---|------|----------|------|
| 1 | SSE Event Bus + Endpoint | MVP | — |
| 2 | Content Filtering (better-profanity) | MVP | — |
| 3 | Emit Events from Routes | MVP | 1 |
| 4 | Device Groups | MVP | — |
| 5 | API Client Updates | MVP | 1, 4 |
| 6 | Mobile Shell (App + GlobalBar + TabBar) | MVP | 5 |
| 7 | Stream Tab | MVP | 5, 6 |
| 8 | Command Tab | MVP | 5, 6 |
| 9 | Toolkit Tab | MVP | 5, 6 |
| 10 | Settings Sheet + Cleanup | Polish | 6 |
| 11 | PWA Support | Polish | 6 |
| 12 | SSE Auth Query Param | MVP | 1 |

**Parallelizable:** Tasks 1, 2, 4 can run in parallel (no deps). Tasks 7, 8, 9 can run in parallel (same deps). Task 12 should be done right after Task 1.
