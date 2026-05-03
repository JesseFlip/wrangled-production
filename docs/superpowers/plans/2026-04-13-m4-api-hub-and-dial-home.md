# M4: `apps/api` Hub + Wrangler Dial-Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the central `apps/api` FastAPI hub on port 8500 plus a `hub_client` module in `apps/wrangler` that dials home over WebSocket, so any REST caller can relay Commands to any connected wrangler.

**Architecture:** Multi-wrangler hub (wranglers identified by hostname, pre-shared-key auth via `WRANGLED_AUTH_TOKEN`). Pydantic-discriminated JSON messages over WSS. `Hub` class owns `dict[wrangler_id, WranglerConnection]` and `dict[mac, wrangler_id]`, correlating request/response pairs through `asyncio.Future`s. Wrangler's `HubClient` is an optional background task started by `wrangler serve` when `WRANGLED_API_URL` is set.

**Tech Stack:** FastAPI, uvicorn, `websockets` (via FastAPI's WS support + `starlette.testclient`), pydantic v2. No new non-stdlib deps beyond `fastapi`/`uvicorn` already available.

Spec: `docs/superpowers/specs/2026-04-13-m4-api-hub-and-dial-home-design.md`.

## File Structure

```
packages/contracts/
├── src/wrangled_contracts/
│   ├── __init__.py                       # MODIFY: export hub types
│   └── hub.py                            # CREATE: WS protocol envelopes
└── tests/test_hub_contracts.py           # CREATE

apps/api/                                  # ENTIRE NEW APP
├── pyproject.toml                        # CREATE
├── CLAUDE.md                             # CREATE
├── src/api/
│   ├── __init__.py                       # CREATE
│   ├── __main__.py                       # CREATE
│   ├── cli.py                            # CREATE
│   ├── settings.py                       # CREATE
│   └── server/
│       ├── __init__.py                   # CREATE — exports create_app
│       ├── app.py                        # CREATE — FastAPI factory
│       ├── auth.py                       # CREATE — bearer dep
│       ├── connection.py                 # CREATE — WranglerConnection
│       ├── hub.py                        # CREATE — Hub class
│       ├── rest.py                       # CREATE — REST router
│       └── ws.py                         # CREATE — /ws endpoint
├── static/dashboard/                     # build output — gitignored
└── tests/
    ├── test_server_app.py                # CREATE
    ├── test_auth.py                      # CREATE
    ├── test_hub.py                       # CREATE
    ├── test_ws_handshake.py              # CREATE
    ├── test_rest_routing.py              # CREATE
    └── test_end_to_end.py                # CREATE

apps/wrangler/
├── src/wrangler/
│   ├── settings.py                       # MODIFY: add auth_token, wrangler_id
│   ├── hub_client.py                     # CREATE
│   └── server/
│       ├── app.py                        # MODIFY: boot HubClient on startup
│       └── registry.py                   # MODIFY: add on_changed observer hook
└── tests/
    ├── test_server_registry.py           # MODIFY: cover observer hook
    └── test_hub_client.py                # CREATE

build.sh                                   # MODIFY: add `api` build + sync
dev.sh                                     # MODIFY: add api on :8500
.gitignore                                 # MODIFY: ignore apps/api/static/dashboard/
```

---

## Task 1: WS protocol envelopes in `packages/contracts/`

**Files:**
- Create: `packages/contracts/src/wrangled_contracts/hub.py`
- Modify: `packages/contracts/src/wrangled_contracts/__init__.py`
- Create: `packages/contracts/tests/test_hub_contracts.py`

- [ ] **Step 1: Failing tests**

`packages/contracts/tests/test_hub_contracts.py`:

```python
"""Tests for wrangled_contracts.hub (WebSocket protocol envelopes)."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import cast

import pytest
from pydantic import TypeAdapter, ValidationError

from wrangled_contracts import (
    RGB,
    ApiMessage,
    ColorCommand,
    CommandResult,
    DevicesChanged,
    GetState,
    Hello,
    Ping,
    Pong,
    PushResult,
    RelayCommand,
    Rescan,
    StateSnapshot,
    Welcome,
    WledDevice,
    WranglerMessage,
)

_WRANGLER = TypeAdapter(WranglerMessage)
_API = TypeAdapter(ApiMessage)


def _dev() -> WledDevice:
    return WledDevice(
        ip=IPv4Address("10.0.6.207"),
        name="WLED-Matrix",
        mac="aa:bb:cc:dd:ee:ff",
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime(2026, 4, 13, tzinfo=UTC),
    )


def test_hello_roundtrip() -> None:
    msg = Hello(wrangler_id="pi-venue", wrangler_version="0.1.0", devices=[_dev()])
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, Hello)
    assert parsed.wrangler_id == "pi-venue"
    assert len(parsed.devices) == 1


def test_devices_changed_roundtrip() -> None:
    msg = DevicesChanged(devices=[_dev()])
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, DevicesChanged)


def test_command_result_roundtrip() -> None:
    msg = CommandResult(
        request_id="abc",
        result=PushResult(ok=True, status=200),
    )
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert cast(CommandResult, parsed).request_id == "abc"
    assert cast(CommandResult, parsed).result.ok is True


def test_state_snapshot_roundtrip() -> None:
    msg = StateSnapshot(
        request_id="xyz",
        mac="aa:bb:cc:dd:ee:ff",
        state={"on": True, "bri": 80},
    )
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert cast(StateSnapshot, parsed).state == {"on": True, "bri": 80}


def test_state_snapshot_with_error() -> None:
    msg = StateSnapshot(
        request_id="xyz",
        mac="aa:bb:cc:dd:ee:ff",
        state=None,
        error="unreachable",
    )
    parsed = _WRANGLER.validate_python(msg.model_dump(mode="json"))
    assert cast(StateSnapshot, parsed).error == "unreachable"


def test_pong_roundtrip() -> None:
    parsed = _WRANGLER.validate_python(Pong().model_dump(mode="json"))
    assert isinstance(parsed, Pong)


def test_welcome_roundtrip() -> None:
    parsed = _API.validate_python(
        Welcome(server_version="0.1.0").model_dump(mode="json"),
    )
    assert isinstance(parsed, Welcome)


def test_relay_command_roundtrip() -> None:
    msg = RelayCommand(
        request_id="r1",
        mac="aa:bb:cc:dd:ee:ff",
        command=ColorCommand(color=RGB(r=0, g=0, b=255)),
    )
    parsed = _API.validate_python(msg.model_dump(mode="json"))
    assert isinstance(parsed, RelayCommand)
    assert isinstance(parsed.command, ColorCommand)
    assert parsed.command.color == RGB(r=0, g=0, b=255)


def test_get_state_roundtrip() -> None:
    parsed = _API.validate_python(
        GetState(request_id="g1", mac="aa:bb:cc:dd:ee:ff").model_dump(mode="json"),
    )
    assert isinstance(parsed, GetState)


def test_rescan_roundtrip() -> None:
    parsed = _API.validate_python(Rescan().model_dump(mode="json"))
    assert isinstance(parsed, Rescan)


def test_ping_roundtrip() -> None:
    parsed = _API.validate_python(Ping().model_dump(mode="json"))
    assert isinstance(parsed, Ping)


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        _WRANGLER.validate_python({"kind": "bogus"})
    with pytest.raises(ValidationError):
        _API.validate_python({"kind": "bogus"})
```

- [ ] **Step 2: Run — verify fail**

```bash
cd packages/contracts
uv run pytest tests/test_hub_contracts.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement**

`packages/contracts/src/wrangled_contracts/hub.py`:

```python
"""WebSocket protocol envelopes for wrangler ↔ api traffic.

Both directions use a discriminated union keyed on "kind". JSON on the wire,
one message per WS frame. Request/response correlation uses a uuid4
`request_id` generated by api.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from wrangled_contracts.commands import Command
from wrangled_contracts.wled import WledDevice


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


# ------------------------------------------------------------------ #
# PushResult is needed at runtime for CommandResult to resolve types.
# It lives in apps/wrangler/pusher.py today — to keep contracts as the
# single source of truth for cross-process types, we redefine the
# schema here and re-export. wrangler imports it from here, too.
# ------------------------------------------------------------------ #


class PushResult(_Frozen):
    """Outcome of a single command push to a WLED device."""

    ok: bool
    status: int | None = None
    error: str | None = None


# ------------------------------------------------------------------ #
# Wrangler → api
# ------------------------------------------------------------------ #


class Hello(_Frozen):
    kind: Literal["hello"] = "hello"
    wrangler_id: str = Field(min_length=1, max_length=64)
    wrangler_version: str
    devices: list[WledDevice]


class DevicesChanged(_Frozen):
    kind: Literal["devices_changed"] = "devices_changed"
    devices: list[WledDevice]


class CommandResult(_Frozen):
    kind: Literal["command_result"] = "command_result"
    request_id: str
    result: PushResult


class StateSnapshot(_Frozen):
    kind: Literal["state_snapshot"] = "state_snapshot"
    request_id: str
    mac: str
    state: dict | None = None
    error: str | None = None


class Pong(_Frozen):
    kind: Literal["pong"] = "pong"


WranglerMessage = Annotated[
    Hello | DevicesChanged | CommandResult | StateSnapshot | Pong,
    Field(discriminator="kind"),
]


# ------------------------------------------------------------------ #
# api → wrangler
# ------------------------------------------------------------------ #


class Welcome(_Frozen):
    kind: Literal["welcome"] = "welcome"
    server_version: str


class RelayCommand(_Frozen):
    kind: Literal["command"] = "command"
    request_id: str
    mac: str
    command: Command


class GetState(_Frozen):
    kind: Literal["get_state"] = "get_state"
    request_id: str
    mac: str


class Rescan(_Frozen):
    kind: Literal["rescan"] = "rescan"


class Ping(_Frozen):
    kind: Literal["ping"] = "ping"


ApiMessage = Annotated[
    Welcome | RelayCommand | GetState | Rescan | Ping,
    Field(discriminator="kind"),
]
```

Update `packages/contracts/src/wrangled_contracts/__init__.py`:

```python
"""Shared pydantic models for the WrangLED monorepo."""

from wrangled_contracts.commands import (
    EFFECT_DEFAULTS,
    EFFECT_FX_ID,
    EMOJI_COMMANDS,
    PRESETS,
    RGB,
    BrightnessCommand,
    ColorCommand,
    Command,
    EffectCommand,
    EffectName,
    PowerCommand,
    PresetCommand,
    PresetName,
    TextCommand,
    command_from_emoji,
)
from wrangled_contracts.hub import (
    ApiMessage,
    CommandResult,
    DevicesChanged,
    GetState,
    Hello,
    Ping,
    Pong,
    PushResult,
    RelayCommand,
    Rescan,
    StateSnapshot,
    Welcome,
    WranglerMessage,
)
from wrangled_contracts.wled import WledDevice, WledMatrix

__all__ = [
    "EFFECT_DEFAULTS",
    "EFFECT_FX_ID",
    "EMOJI_COMMANDS",
    "PRESETS",
    "RGB",
    "ApiMessage",
    "BrightnessCommand",
    "ColorCommand",
    "Command",
    "CommandResult",
    "DevicesChanged",
    "EffectCommand",
    "EffectName",
    "GetState",
    "Hello",
    "Ping",
    "Pong",
    "PowerCommand",
    "PresetCommand",
    "PresetName",
    "PushResult",
    "RelayCommand",
    "Rescan",
    "StateSnapshot",
    "TextCommand",
    "Welcome",
    "WledDevice",
    "WledMatrix",
    "WranglerMessage",
    "command_from_emoji",
]
```

- [ ] **Step 4: Update wrangler pusher to import `PushResult` from contracts**

`apps/wrangler/src/wrangler/pusher.py`: replace the local `PushResult` class with a re-export from contracts, since contracts is now the single source of truth.

Replace:

```python
class PushResult(BaseModel):
    """Outcome of a push_command call."""

    ok: bool
    status: int | None = None
    error: str | None = None
```

With:

```python
from wrangled_contracts import PushResult  # re-exported for backward compatibility

__all__ = ["PushResult", "push_command", ...]   # keep existing exports
```

Remove the now-unused `from pydantic import BaseModel` import if that was the only use.

- [ ] **Step 5: Run tests + lint + commit**

```bash
cd packages/contracts
uv run pytest -v
uv run ruff check .
uv run ruff format --check .

cd ../../apps/wrangler
uv sync    # pull new contracts exports
uv run pytest -v
uv run ruff check .
uv run ruff format --check .

cd /home/jvogel/src/personal/wrangled-dashboard
git add packages/contracts apps/wrangler/src/wrangler/pusher.py
git commit -m "feat(contracts): add WS protocol envelopes + hoist PushResult"
```

Expected: all existing tests still pass; new hub-contract tests pass.

---

## Task 2: Scaffold `apps/api/` + /healthz + bearer auth

**Files:**
- Create: `apps/api/pyproject.toml`, `apps/api/CLAUDE.md`
- Create: `apps/api/src/api/__init__.py`, `__main__.py`, `settings.py`
- Create: `apps/api/src/api/server/__init__.py`, `app.py`, `auth.py`
- Create: `apps/api/tests/test_server_app.py`, `test_auth.py`
- Modify: `.gitignore`

- [ ] **Step 1: `apps/api/pyproject.toml`**

```toml
[project]
name = "wrangled-api"
version = "0.1.0"
description = "WrangLED central hub: routes commands to wranglers, serves dashboard"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "wrangled-contracts",
]

[project.scripts]
api = "api.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/api"]

[tool.uv.sources]
wrangled-contracts = { path = "../../packages/contracts", editable = true }

[tool.ruff]
extend = "../../ruff.toml"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "respx>=0.21",
    "ruff>=0.5",
]
```

- [ ] **Step 2: `apps/api/src/api/__init__.py`**

```python
"""WrangLED central hub."""

__version__ = "0.1.0"
```

- [ ] **Step 3: `apps/api/src/api/__main__.py`**

```python
"""Allow `python -m api`."""

import sys

from api.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: `apps/api/src/api/settings.py`**

```python
"""Env-driven configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Runtime settings for the api process."""

    model_config = SettingsConfigDict(env_prefix="WRANGLED_", env_file=".env", extra="ignore")

    auth_token: str | None = None
    host: str = "127.0.0.1"
    port: int = 8500
```

- [ ] **Step 5: `apps/api/src/api/server/auth.py`**

```python
"""Bearer-token auth dependency."""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status


class AuthChecker:
    """Validates Authorization: Bearer <token> when a token is configured."""

    def __init__(self, token: str | None) -> None:
        self._token = token

    @property
    def enabled(self) -> bool:
        return self._token is not None

    def check_header(self, authorization: str | None) -> None:
        if not self.enabled:
            return
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="bearer token required",
            )
        if authorization.removeprefix("Bearer ") != self._token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token",
            )

    def check_query_token(self, token: str | None) -> None:
        if not self.enabled:
            return
        if token != self._token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid token",
            )


def build_rest_auth_dep(checker: AuthChecker):
    """Return a FastAPI dependency that rejects unauthorised REST callers."""

    def _dep(
        request: Request,  # noqa: ARG001 — kept for future logging
        authorization: str | None = Header(default=None),
    ) -> None:
        checker.check_header(authorization)

    return _dep
```

- [ ] **Step 6: `apps/api/src/api/server/app.py`**

```python
"""FastAPI app factory for the wrangled api."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import __version__
from api.server.auth import AuthChecker


def create_app(*, auth_token: str | None = None) -> FastAPI:
    """Build the wrangled api application."""
    app = FastAPI(title="wrangled-api", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    checker = AuthChecker(auth_token)
    app.state.auth_checker = checker

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {"ok": True, "wranglers": 0}

    static_dir = Path(__file__).resolve().parents[3] / "static" / "dashboard"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app
```

- [ ] **Step 7: `apps/api/src/api/server/__init__.py`**

```python
"""WrangLED api server package."""

from api.server.app import create_app

__all__ = ["create_app"]
```

- [ ] **Step 8: `apps/api/tests/test_server_app.py`**

```python
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
    assert response.json() == {"ok": True, "wranglers": 0}


def test_root_reflects_ui_build_state() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    if _STATIC.is_dir():
        assert response.status_code == 200
    else:
        assert response.status_code == 404
```

- [ ] **Step 9: `apps/api/tests/test_auth.py`**

```python
"""Tests for bearer-token auth."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.server.auth import AuthChecker, build_rest_auth_dep


def _app_with(checker: AuthChecker) -> TestClient:
    app = FastAPI()
    dep = build_rest_auth_dep(checker)

    @app.get("/guarded", dependencies=[Depends(dep)])
    def guarded() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_no_token_configured_allows_anonymous() -> None:
    client = _app_with(AuthChecker(None))
    assert client.get("/guarded").status_code == 200


def test_valid_token_accepted() -> None:
    client = _app_with(AuthChecker("secret"))
    response = client.get("/guarded", headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200


def test_missing_token_rejected() -> None:
    client = _app_with(AuthChecker("secret"))
    assert client.get("/guarded").status_code == 401


def test_wrong_token_rejected() -> None:
    client = _app_with(AuthChecker("secret"))
    response = client.get("/guarded", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_check_query_token() -> None:
    checker = AuthChecker("secret")
    checker.check_query_token("secret")  # does not raise
    with pytest.raises(Exception):
        checker.check_query_token("wrong")
```

- [ ] **Step 10: `apps/api/CLAUDE.md`**

```markdown
# apps/api — Central Hub (FastAPI)

## Purpose
The central WrangLED server. Holds WebSocket connections to wranglers that dial home, exposes REST for command senders (dashboard, Discord, curl), and serves the built `apps/dashboard/` as static.

## Run locally

    cd apps/api
    uv sync
    WRANGLED_AUTH_TOKEN=devtoken uv run api serve

## Test

    uv run pytest

## Env vars
- `WRANGLED_AUTH_TOKEN` — pre-shared key. Required on both api and wrangler. Unset = dev mode.
- `WRANGLED_HOST` — bind host (default 127.0.0.1)
- `WRANGLED_PORT` — bind port (default 8500)

## Key modules
- `server/app.py` — FastAPI factory, CORS, static mount
- `server/auth.py` — bearer-token dependency
- `server/hub.py` — WranglerConnection manager + command routing
- `server/ws.py` — `/ws` endpoint
- `server/rest.py` — `/api/*` endpoints
- `cli.py` — argparse CLI (`serve`)
```

- [ ] **Step 11: Update `.gitignore`**

Append:

```
# Built dashboard, served by apps/api
apps/api/static/dashboard/
```

- [ ] **Step 12: Install + verify**

```bash
cd apps/api
uv sync
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

- [ ] **Step 13: Commit**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/api .gitignore
git commit -m "feat(api): scaffold FastAPI app with /healthz + bearer auth"
```

---

## Task 3: `WranglerConnection` + `Hub` class

**Files:**
- Create: `apps/api/src/api/server/connection.py`
- Create: `apps/api/src/api/server/hub.py`
- Create: `apps/api/tests/test_hub.py`

- [ ] **Step 1: Failing tests**

`apps/api/tests/test_hub.py`:

```python
"""Tests for api.server.hub (Hub + routing, no WS yet)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest

from wrangled_contracts import (
    ColorCommand,
    CommandResult,
    DevicesChanged,
    Hello,
    PushResult,
    RGB,
    RelayCommand,
    StateSnapshot,
    WledDevice,
)

from api.server.connection import WranglerConnection
from api.server.hub import Hub, NoWranglerForDeviceError, WranglerTimeoutError


def _dev(mac: str, ip: str) -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name=f"WLED-{ip}",
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


def _conn(wrangler_id: str, devices: list[WledDevice]) -> WranglerConnection:
    conn = WranglerConnection(
        wrangler_id=wrangler_id,
        socket=AsyncMock(),
        wrangler_version="0.1.0",
    )
    conn.apply_devices(devices)
    return conn


@pytest.mark.asyncio
async def test_attach_registers_ownership() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    assert hub.find_device("aa:bb:cc:dd:ee:01") is not None
    assert hub.all_devices() == [conn.devices["aa:bb:cc:dd:ee:01"]]
    assert hub.wranglers_summary()[0]["wrangler_id"] == "pi-a"


@pytest.mark.asyncio
async def test_detach_removes_devices() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)
    await hub.detach("pi-a")

    assert hub.find_device("aa:bb:cc:dd:ee:01") is None
    assert hub.all_devices() == []


@pytest.mark.asyncio
async def test_send_command_resolves_when_result_arrives() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    # Start the send; record the outgoing RelayCommand to grab request_id.
    sent: list[object] = []
    conn.socket.send_text = AsyncMock(side_effect=lambda s: sent.append(s))

    task = asyncio.create_task(
        hub.send_command("aa:bb:cc:dd:ee:01", ColorCommand(color=RGB(r=1, g=2, b=3))),
    )
    await asyncio.sleep(0)   # let the task post the relay

    import json
    payload = json.loads(sent[-1])
    request_id = payload["request_id"]

    hub.resolve_response(
        "pi-a",
        CommandResult(request_id=request_id, result=PushResult(ok=True, status=200)),
    )
    result = await task
    assert result.ok is True


@pytest.mark.asyncio
async def test_send_command_times_out() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    conn.socket.send_text = AsyncMock()
    await hub.attach(conn)

    with pytest.raises(WranglerTimeoutError):
        await hub.send_command(
            "aa:bb:cc:dd:ee:01",
            ColorCommand(color=RGB(r=0, g=0, b=0)),
            timeout=0.05,
        )


@pytest.mark.asyncio
async def test_send_command_unknown_mac() -> None:
    hub = Hub()
    with pytest.raises(NoWranglerForDeviceError):
        await hub.send_command(
            "zz:zz:zz:zz:zz:zz",
            ColorCommand(color=RGB(r=0, g=0, b=0)),
        )


@pytest.mark.asyncio
async def test_get_state_resolves_when_snapshot_arrives() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    sent: list[str] = []
    conn.socket.send_text = AsyncMock(side_effect=lambda s: sent.append(s))

    task = asyncio.create_task(hub.get_state("aa:bb:cc:dd:ee:01"))
    await asyncio.sleep(0)

    import json
    payload = json.loads(sent[-1])
    request_id = payload["request_id"]

    hub.resolve_response(
        "pi-a",
        StateSnapshot(
            request_id=request_id,
            mac="aa:bb:cc:dd:ee:01",
            state={"on": True, "bri": 80},
        ),
    )
    result = await task
    assert result == {"on": True, "bri": 80}


@pytest.mark.asyncio
async def test_apply_devices_handles_ownership_conflict() -> None:
    hub = Hub()
    a = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    b = _conn("pi-b", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.2")])
    await hub.attach(a)
    await hub.attach(b)

    # Newest attach wins.
    device = hub.find_device("aa:bb:cc:dd:ee:01")
    assert device is not None
    assert str(device.ip) == "10.0.6.2"


@pytest.mark.asyncio
async def test_apply_devices_updates_on_devices_changed() -> None:
    hub = Hub()
    conn = _conn("pi-a", [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")])
    await hub.attach(conn)

    new_dev = _dev("aa:bb:cc:dd:ee:01", "10.0.6.9")
    msg = DevicesChanged(devices=[new_dev])
    hub.apply_devices("pi-a", msg.devices)

    found = hub.find_device("aa:bb:cc:dd:ee:01")
    assert str(found.ip) == "10.0.6.9"


def test_hello_message_used_to_build_connection() -> None:
    # Purely structural sanity: a Hello carries what WranglerConnection needs.
    hello = Hello(wrangler_id="pi-x", wrangler_version="0.1.0", devices=[])
    assert hello.wrangler_id == "pi-x"
```

- [ ] **Step 2: Run — verify fail**

```bash
cd apps/api
uv run pytest tests/test_hub.py -v
```

- [ ] **Step 3: Implement `connection.py`**

```python
"""Per-wrangler connection state held by the Hub."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from wrangled_contracts import WledDevice


@dataclass
class WranglerConnection:
    wrangler_id: str
    socket: WebSocket | Any  # Any so tests can inject AsyncMock
    wrangler_version: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    last_pong_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    devices: dict[str, WledDevice] = field(default_factory=dict)
    pending: dict[str, asyncio.Future] = field(default_factory=dict)

    def apply_devices(self, devices: list[WledDevice]) -> None:
        self.devices = {d.mac: d for d in devices}
```

- [ ] **Step 4: Implement `hub.py`**

```python
"""Connection manager + command routing."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from wrangled_contracts import (
    ApiMessage,
    Command,
    CommandResult,
    GetState,
    PushResult,
    RelayCommand,
    Rescan,
    StateSnapshot,
    WledDevice,
    WranglerMessage,
)

from api.server.connection import WranglerConnection

logger = logging.getLogger(__name__)


class NoWranglerForDeviceError(LookupError):
    """Raised when a command targets a MAC that no connected wrangler owns."""


class WranglerTimeoutError(TimeoutError):
    """Raised when a wrangler doesn't respond within the deadline."""


class WranglerDisconnectedError(RuntimeError):
    """Raised when a wrangler disconnects while a request is outstanding."""


async def _send(conn: WranglerConnection, msg: ApiMessage) -> None:
    await conn.socket.send_text(msg.model_dump_json())


class Hub:
    """Holds connections and routes commands."""

    def __init__(self) -> None:
        self._conns: dict[str, WranglerConnection] = {}
        self._ownership: dict[str, str] = {}   # mac → wrangler_id

    # ---------------- lifecycle ----------------

    async def attach(self, conn: WranglerConnection) -> None:
        existing = self._conns.pop(conn.wrangler_id, None)
        if existing is not None:
            logger.warning(
                "attach: wrangler %s reconnected; dropping stale connection",
                conn.wrangler_id,
            )
            self._cancel_pending(existing, reason="replaced by new connection")
        self._conns[conn.wrangler_id] = conn
        self.apply_devices(conn.wrangler_id, list(conn.devices.values()))

    async def detach(self, wrangler_id: str) -> None:
        conn = self._conns.pop(wrangler_id, None)
        if conn is None:
            return
        self._cancel_pending(conn, reason="wrangler disconnected")
        # Purge ownership
        for mac, owner in list(self._ownership.items()):
            if owner == wrangler_id:
                self._ownership.pop(mac, None)

    def _cancel_pending(self, conn: WranglerConnection, *, reason: str) -> None:
        for fut in conn.pending.values():
            if not fut.done():
                fut.set_exception(WranglerDisconnectedError(reason))
        conn.pending.clear()

    # ---------------- device / ownership ----------------

    def apply_devices(self, wrangler_id: str, devices: list[WledDevice]) -> None:
        conn = self._conns.get(wrangler_id)
        if conn is None:
            return
        conn.apply_devices(devices)
        # Re-own every listed MAC on this wrangler; warn on steals.
        for dev in devices:
            current = self._ownership.get(dev.mac)
            if current is not None and current != wrangler_id:
                logger.warning(
                    "device %s now owned by %s (was %s)",
                    dev.mac, wrangler_id, current,
                )
            self._ownership[dev.mac] = wrangler_id

    def find_device(self, mac: str) -> WledDevice | None:
        owner = self._ownership.get(mac)
        if owner is None:
            return None
        conn = self._conns.get(owner)
        return conn.devices.get(mac) if conn else None

    def all_devices(self) -> list[WledDevice]:
        seen: dict[str, WledDevice] = {}
        for conn in self._conns.values():
            for mac, dev in conn.devices.items():
                # Only emit if this wrangler still owns the MAC.
                if self._ownership.get(mac) == conn.wrangler_id:
                    seen[mac] = dev
        return sorted(seen.values(), key=lambda d: int(d.ip))

    def wranglers_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "wrangler_id": c.wrangler_id,
                "wrangler_version": c.wrangler_version,
                "connected_at": c.connected_at.isoformat(),
                "last_pong_at": c.last_pong_at.isoformat(),
                "device_count": len(c.devices),
            }
            for c in self._conns.values()
        ]

    # ---------------- request/response ----------------

    async def send_command(
        self,
        mac: str,
        command: Command,
        *,
        timeout: float = 5.0,
    ) -> PushResult:
        owner_id = self._ownership.get(mac)
        if owner_id is None or owner_id not in self._conns:
            msg = f"no wrangler owns {mac}"
            raise NoWranglerForDeviceError(msg)
        conn = self._conns[owner_id]
        request_id = uuid.uuid4().hex
        future: asyncio.Future[PushResult] = asyncio.get_event_loop().create_future()
        conn.pending[request_id] = future
        await _send(conn, RelayCommand(request_id=request_id, mac=mac, command=command))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            conn.pending.pop(request_id, None)
            msg = f"wrangler {conn.wrangler_id} did not respond within {timeout}s"
            raise WranglerTimeoutError(msg) from exc

    async def get_state(
        self,
        mac: str,
        *,
        timeout: float = 3.0,
    ) -> dict:
        owner_id = self._ownership.get(mac)
        if owner_id is None or owner_id not in self._conns:
            msg = f"no wrangler owns {mac}"
            raise NoWranglerForDeviceError(msg)
        conn = self._conns[owner_id]
        request_id = uuid.uuid4().hex
        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        conn.pending[request_id] = future
        await _send(conn, GetState(request_id=request_id, mac=mac))
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            conn.pending.pop(request_id, None)
            msg = f"wrangler {conn.wrangler_id} did not respond within {timeout}s"
            raise WranglerTimeoutError(msg) from exc

    async def rescan_all(self, *, grace: float = 2.0) -> list[WledDevice]:
        if not self._conns:
            return []
        for conn in list(self._conns.values()):
            await _send(conn, Rescan())
        # Wranglers respond asynchronously with DevicesChanged; give them a moment.
        await asyncio.sleep(grace)
        return self.all_devices()

    # ---------------- inbound message resolution ----------------

    def resolve_response(
        self,
        wrangler_id: str,
        message: WranglerMessage,
    ) -> None:
        conn = self._conns.get(wrangler_id)
        if conn is None:
            return
        if isinstance(message, CommandResult):
            fut = conn.pending.pop(message.request_id, None)
            if fut and not fut.done():
                fut.set_result(message.result)
        elif isinstance(message, StateSnapshot):
            fut = conn.pending.pop(message.request_id, None)
            if fut and not fut.done():
                if message.state is not None:
                    fut.set_result(message.state)
                else:
                    fut.set_exception(
                        RuntimeError(message.error or "wrangler reported unreachable"),
                    )
```

- [ ] **Step 5: Run + lint + commit**

```bash
cd apps/api
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/api
git commit -m "feat(api): Hub + WranglerConnection with request/response routing"
```

---

## Task 4: `/ws` endpoint — handshake + message loop + heartbeat

**Files:**
- Create: `apps/api/src/api/server/ws.py`
- Modify: `apps/api/src/api/server/app.py`
- Create: `apps/api/tests/test_ws_handshake.py`

- [ ] **Step 1: Failing tests**

`apps/api/tests/test_ws_handshake.py`:

```python
"""Tests for the /ws endpoint."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from api.server import create_app


def _hello_payload() -> dict:
    return {
        "kind": "hello",
        "wrangler_id": "pi-test",
        "wrangler_version": "0.1.0",
        "devices": [],
    }


def test_ws_connects_and_receives_welcome_without_auth() -> None:
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(_hello_payload())
        welcome = ws.receive_json()
        assert welcome["kind"] == "welcome"
        assert "server_version" in welcome


def test_ws_requires_token_when_configured() -> None:
    app = create_app(auth_token="secret")
    client = TestClient(app)
    # Missing token — connection rejected before Hello.
    try:
        with client.websocket_connect("/ws"):
            raise AssertionError("connection should have been rejected")
    except Exception:
        pass   # expected

    # Valid token via query param.
    with client.websocket_connect("/ws?token=secret") as ws:
        ws.send_json(_hello_payload())
        assert ws.receive_json()["kind"] == "welcome"


def test_ws_registers_devices_in_hub() -> None:
    app = create_app()
    client = TestClient(app)
    dev = {
        "ip": "10.0.6.207",
        "name": "WLED-Matrix",
        "mac": "aa:bb:cc:dd:ee:ff",
        "version": "0.15.0",
        "led_count": 256,
        "matrix": None,
        "udp_port": 21324,
        "discovered_via": "mdns",
        "discovered_at": "2026-04-13T12:00:00+00:00",
    }
    with client.websocket_connect("/ws") as ws:
        payload = _hello_payload()
        payload["devices"] = [dev]
        ws.send_json(payload)
        ws.receive_json()   # welcome
        # Ask the app's hub directly.
        hub = app.state.hub
        assert hub.find_device("aa:bb:cc:dd:ee:ff") is not None


def test_ws_rejects_first_message_not_hello() -> None:
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"kind": "pong"})
        # Server should close the socket; receive should raise.
        import pytest
        with pytest.raises(Exception):
            ws.receive_json()
```

- [ ] **Step 2: Run — verify fail**

```bash
cd apps/api
uv run pytest tests/test_ws_handshake.py -v
```

- [ ] **Step 3: Implement `ws.py`**

```python
"""/ws endpoint — wrangler dial-home channel."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import TypeAdapter, ValidationError

from wrangled_contracts import (
    Hello,
    Ping,
    Pong,
    Welcome,
    WranglerMessage,
)

from api import __version__
from api.server.auth import AuthChecker
from api.server.connection import WranglerConnection
from api.server.hub import Hub

logger = logging.getLogger(__name__)

_WRANGLER_ADAPTER = TypeAdapter(WranglerMessage)

_HELLO_DEADLINE_SECONDS = 5.0
_PING_INTERVAL_SECONDS = 30.0
_DEAD_AFTER_SECONDS = 70.0


def build_ws_router(hub: Hub, auth: AuthChecker) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket, token: str | None = None) -> None:
        try:
            auth.check_query_token(token)
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()

        # First message must be Hello within _HELLO_DEADLINE_SECONDS.
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=_HELLO_DEADLINE_SECONDS)
        except (asyncio.TimeoutError, WebSocketDisconnect):
            await websocket.close(code=status.WS_1002_PROTOCOL_ERROR)
            return

        try:
            message = _WRANGLER_ADAPTER.validate_json(raw)
        except ValidationError:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        if not isinstance(message, Hello):
            await websocket.close(code=status.WS_1002_PROTOCOL_ERROR)
            return

        conn = WranglerConnection(
            wrangler_id=message.wrangler_id,
            socket=websocket,
            wrangler_version=message.wrangler_version,
        )
        conn.apply_devices(message.devices)
        await hub.attach(conn)
        await websocket.send_text(Welcome(server_version=__version__).model_dump_json())

        heartbeat_task = asyncio.create_task(_heartbeat(websocket, conn))
        try:
            await _main_loop(websocket, conn, hub)
        finally:
            heartbeat_task.cancel()
            await hub.detach(conn.wrangler_id)

    return router


async def _main_loop(websocket: WebSocket, conn: WranglerConnection, hub: Hub) -> None:
    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return
        try:
            message = _WRANGLER_ADAPTER.validate_json(raw)
        except ValidationError as exc:
            logger.debug("ws %s: invalid message: %s", conn.wrangler_id, exc)
            continue

        if isinstance(message, Pong):
            conn.last_pong_at = datetime.now(tz=UTC)
            continue

        # DevicesChanged / CommandResult / StateSnapshot / repeat Hello
        from wrangled_contracts import DevicesChanged

        if isinstance(message, DevicesChanged):
            hub.apply_devices(conn.wrangler_id, message.devices)
            continue
        if isinstance(message, Hello):
            logger.debug("ws %s: ignoring repeat Hello", conn.wrangler_id)
            continue

        # CommandResult / StateSnapshot — resolve pending future
        hub.resolve_response(conn.wrangler_id, message)


async def _heartbeat(websocket: WebSocket, conn: WranglerConnection) -> None:
    while True:
        await asyncio.sleep(_PING_INTERVAL_SECONDS)
        now = datetime.now(tz=UTC)
        if (now - conn.last_pong_at).total_seconds() > _DEAD_AFTER_SECONDS:
            try:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            except Exception:  # noqa: BLE001
                pass
            return
        try:
            await websocket.send_text(Ping().model_dump_json())
        except Exception:   # noqa: BLE001
            return
```

- [ ] **Step 4: Wire router + hub into `app.py`**

Replace `apps/api/src/api/server/app.py`:

```python
"""FastAPI app factory for the wrangled api."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import __version__
from api.server.auth import AuthChecker
from api.server.hub import Hub
from api.server.ws import build_ws_router


def create_app(*, auth_token: str | None = None) -> FastAPI:
    """Build the wrangled api application."""
    app = FastAPI(title="wrangled-api", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    checker = AuthChecker(auth_token)
    hub = Hub()
    app.state.auth_checker = checker
    app.state.hub = hub

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {"ok": True, "wranglers": len(hub.wranglers_summary())}

    app.include_router(build_ws_router(hub, checker))

    static_dir = Path(__file__).resolve().parents[3] / "static" / "dashboard"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app
```

- [ ] **Step 5: Run + lint + commit**

```bash
cd apps/api
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/api
git commit -m "feat(api): add /ws endpoint with Hello handshake + heartbeat"
```

---

## Task 5: REST endpoints

**Files:**
- Create: `apps/api/src/api/server/rest.py`
- Modify: `apps/api/src/api/server/app.py`
- Create: `apps/api/tests/test_rest_routing.py`

- [ ] **Step 1: Failing tests**

`apps/api/tests/test_rest_routing.py`:

```python
"""Tests for REST endpoints routed through the Hub."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from wrangled_contracts import (
    CommandResult,
    PushResult,
    StateSnapshot,
    WledDevice,
)

from api.server import create_app
from api.server.connection import WranglerConnection


def _dev(mac: str = "aa:bb:cc:dd:ee:ff", ip: str = "10.0.6.207") -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name="WLED-Matrix",
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


async def _attach_fake(hub, wrangler_id: str, devices: list[WledDevice]):
    conn = WranglerConnection(
        wrangler_id=wrangler_id,
        socket=AsyncMock(),
        wrangler_version="0.1.0",
    )
    conn.apply_devices(devices)
    await hub.attach(conn)
    return conn


@pytest.fixture
def app_with_one():
    app = create_app()
    asyncio.get_event_loop().run_until_complete(
        _attach_fake(app.state.hub, "pi-a", [_dev()]),
    )
    return app


def test_list_devices(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.get("/api/devices")
    assert response.status_code == 200
    assert len(response.json()["devices"]) == 1


def test_get_device(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.get("/api/devices/aa:bb:cc:dd:ee:ff")
    assert response.status_code == 200


def test_get_device_404(app_with_one) -> None:
    client = TestClient(app_with_one)
    assert client.get("/api/devices/zz:zz:zz:zz:zz:zz").status_code == 404


def test_get_state(app_with_one) -> None:
    hub = app_with_one.state.hub
    conn = hub._conns["pi-a"]

    async def fake_send(raw: str) -> None:
        import json
        req_id = json.loads(raw)["request_id"]
        hub.resolve_response("pi-a", StateSnapshot(
            request_id=req_id, mac="aa:bb:cc:dd:ee:ff", state={"on": True, "bri": 80},
        ))

    conn.socket.send_text = AsyncMock(side_effect=fake_send)
    client = TestClient(app_with_one)
    response = client.get("/api/devices/aa:bb:cc:dd:ee:ff/state")
    assert response.status_code == 200
    assert response.json()["state"] == {"on": True, "bri": 80}


def test_post_command(app_with_one) -> None:
    hub = app_with_one.state.hub
    conn = hub._conns["pi-a"]

    async def fake_send(raw: str) -> None:
        import json
        req_id = json.loads(raw)["request_id"]
        hub.resolve_response("pi-a", CommandResult(
            request_id=req_id, result=PushResult(ok=True, status=200),
        ))

    conn.socket.send_text = AsyncMock(side_effect=fake_send)
    client = TestClient(app_with_one)
    response = client.post(
        "/api/devices/aa:bb:cc:dd:ee:ff/commands",
        json={"kind": "color", "color": {"r": 10, "g": 20, "b": 30}},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_post_command_unknown_mac(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.post(
        "/api/devices/zz:zz:zz:zz:zz:zz/commands",
        json={"kind": "power", "on": False},
    )
    assert response.status_code == 404


def test_wranglers_summary(app_with_one) -> None:
    client = TestClient(app_with_one)
    response = client.get("/api/wranglers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["wrangler_id"] == "pi-a"
    assert data[0]["device_count"] == 1
```

- [ ] **Step 2: Run — verify fail**

- [ ] **Step 3: Implement `rest.py`**

```python
"""REST routes for external callers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from wrangled_contracts import Command, PushResult, WledDevice

from api.server.auth import AuthChecker, build_rest_auth_dep
from api.server.hub import (
    Hub,
    NoWranglerForDeviceError,
    WranglerTimeoutError,
)


def build_rest_router(hub: Hub, auth: AuthChecker) -> APIRouter:
    dep = build_rest_auth_dep(auth)
    router = APIRouter(prefix="/api", dependencies=[Depends(dep)])

    @router.get("/devices")
    def list_devices() -> dict[str, list[WledDevice]]:
        return {"devices": hub.all_devices()}

    @router.get("/devices/{mac}")
    def get_device(mac: str) -> WledDevice:
        device = hub.find_device(mac)
        if device is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        return device

    @router.get("/devices/{mac}/state")
    async def get_state(mac: str) -> dict:
        if hub.find_device(mac) is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        try:
            state = await hub.get_state(mac)
        except NoWranglerForDeviceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WranglerTimeoutError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {"state": state}

    @router.post("/devices/{mac}/commands")
    async def post_command(mac: str, command: Command) -> PushResult:
        if hub.find_device(mac) is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        try:
            return await hub.send_command(mac, command)
        except NoWranglerForDeviceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except WranglerTimeoutError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @router.post("/scan")
    async def run_scan() -> dict[str, list[WledDevice]]:
        devices = await hub.rescan_all()
        return {"devices": devices}

    @router.get("/wranglers")
    def wranglers() -> list[dict]:
        return hub.wranglers_summary()

    return router
```

- [ ] **Step 4: Register router in `app.py`**

In `apps/api/src/api/server/app.py`, add:

```python
from api.server.rest import build_rest_router
```

And after the ws router:

```python
    app.include_router(build_rest_router(hub, checker))
```

- [ ] **Step 5: Run + lint + commit**

```bash
cd apps/api
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/api
git commit -m "feat(api): REST endpoints — devices, state, commands, scan, wranglers"
```

---

## Task 6: `api serve` CLI + static mount assertion

**Files:**
- Create: `apps/api/src/api/cli.py`

- [ ] **Step 1: Implement `cli.py`**

```python
"""Wrangled api command-line interface."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import uvicorn

from api.server import create_app
from api.settings import ApiSettings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api", description="WrangLED central hub.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the api HTTP server.")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument(
        "--no-auth",
        dest="auth_disabled",
        action="store_true",
        help="Force auth disabled regardless of WRANGLED_AUTH_TOKEN.",
    )
    return parser


def _run_serve(args: argparse.Namespace) -> int:
    settings = ApiSettings()
    host = args.host or settings.host
    port = args.port or settings.port
    token = None if args.auth_disabled else settings.auth_token
    app = create_app(auth_token=token)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "serve":
        return _run_serve(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 2: Smoke-run**

```bash
cd apps/api
uv run api serve --help
```
Expected: help lists `--host`, `--port`, `--no-auth`.

- [ ] **Step 3: Full suite + lint + commit**

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/api
git commit -m "feat(api): add 'api serve' CLI wiring uvicorn"
```

---

## Task 7: Wrangler Registry `on_changed` observer hook

**Files:**
- Modify: `apps/wrangler/src/wrangler/server/registry.py`
- Modify: `apps/wrangler/tests/test_server_registry.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_server_registry.py`:

```python
@pytest.mark.asyncio
async def test_registry_notifies_observers_on_scan() -> None:
    fake_scan = AsyncMock(return_value=[_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")])
    r = Registry(scanner=fake_scan)

    events: list[str] = []

    async def observer() -> None:
        events.append("notified")

    r.on_changed(observer)
    await r.scan(ScanOptions(mdns_timeout=0.01))
    assert events == ["notified"]


@pytest.mark.asyncio
async def test_registry_notifies_observers_on_put() -> None:
    r = Registry(scanner=AsyncMock())

    events: list[str] = []

    async def observer() -> None:
        events.append("put")

    r.on_changed(observer)
    r.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A"))
    # put schedules via create_task; let the loop drain.
    await asyncio.sleep(0)
    assert events == ["put"]


@pytest.mark.asyncio
async def test_registry_observer_failure_isolated() -> None:
    r = Registry(scanner=AsyncMock(return_value=[]))

    calls: list[str] = []

    async def bad() -> None:
        calls.append("bad")
        msg = "boom"
        raise RuntimeError(msg)

    async def good() -> None:
        calls.append("good")

    r.on_changed(bad)
    r.on_changed(good)
    await r.scan(ScanOptions(mdns_timeout=0.01))
    assert calls == ["bad", "good"]
```

- [ ] **Step 2: Run — verify fail**

```bash
cd apps/wrangler
uv run pytest tests/test_server_registry.py -v
```

- [ ] **Step 3: Modify `registry.py`**

Add the observer machinery to `apps/wrangler/src/wrangler/server/registry.py`:

```python
import asyncio
import logging
from collections.abc import Awaitable, Callable
# ...existing imports

logger = logging.getLogger(__name__)

ObserverFn = Callable[[], Awaitable[None]]
```

Update the `Registry` class:

```python
class Registry:
    """Tracks the most recent scan result, keyed by MAC."""

    def __init__(self, *, scanner: ScanFn) -> None:
        self._scanner = scanner
        self._devices: dict[str, WledDevice] = {}
        self._lock = asyncio.Lock()
        self._observers: list[ObserverFn] = []

    def on_changed(self, cb: ObserverFn) -> None:
        """Register an async callback fired after each scan/put."""
        self._observers.append(cb)

    async def _notify(self) -> None:
        for cb in self._observers:
            try:
                await cb()
            except Exception:   # noqa: BLE001
                logger.exception("observer failed")

    def _schedule_notify(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no loop — tests in sync context skip
        loop.create_task(self._notify())

    def all(self) -> list[WledDevice]:
        return sorted(self._devices.values(), key=lambda d: int(d.ip))

    def get(self, mac: str) -> WledDevice | None:
        return self._devices.get(mac)

    def put(self, device: WledDevice) -> None:
        self._devices[device.mac] = device
        self._schedule_notify()

    async def scan(self, opts: ScanOptions) -> list[WledDevice]:
        async with self._lock:
            discovered = await self._scanner(opts)
            new_map: dict[str, WledDevice] = {}
            for d in discovered:
                if d.mac in self._devices:
                    d.discovered_at = self._devices[d.mac].discovered_at
                new_map[d.mac] = d
            self._devices = new_map
        await self._notify()
        return self.all()
```

- [ ] **Step 4: Run + lint + commit**

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler
git commit -m "feat(wrangler): add Registry.on_changed observer hook"
```

---

## Task 8: Wrangler settings additions

**Files:**
- Modify: `apps/wrangler/src/wrangler/settings.py`

- [ ] **Step 1: Replace settings**

```python
"""Runtime settings loaded from environment."""

from __future__ import annotations

import socket

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WranglerSettings(BaseSettings):
    """Environment-driven configuration for the wrangler agent."""

    model_config = SettingsConfigDict(env_prefix="WRANGLED_", env_file=".env", extra="ignore")

    api_url: str | None = None
    auth_token: str | None = None
    wrangler_id: str = Field(default_factory=socket.gethostname)

    mdns_timeout_seconds: float = 3.0
    probe_timeout_seconds: float = 2.0
    probe_concurrency: int = 32
```

- [ ] **Step 2: Run + lint + commit**

```bash
cd apps/wrangler
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler
git commit -m "feat(wrangler): settings gain auth_token + wrangler_id"
```

---

## Task 9: `HubClient` — connect, handshake, message dispatch

**Files:**
- Create: `apps/wrangler/src/wrangler/hub_client.py`
- Create: `apps/wrangler/tests/test_hub_client.py`

- [ ] **Step 1: Add `websockets` to wrangler deps**

Modify `apps/wrangler/pyproject.toml` — append to `dependencies`:

```toml
    "websockets>=12.0",
```

Then:

```bash
cd apps/wrangler
uv sync
```

- [ ] **Step 2: Failing tests**

`apps/wrangler/tests/test_hub_client.py`:

```python
"""Tests for wrangler.hub_client."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest
import websockets

from wrangled_contracts import WledDevice

from wrangler.hub_client import HubClient
from wrangler.server.registry import Registry


def _dev(mac: str, ip: str) -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name=f"WLED-{ip}",
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


async def _fake_server(host: str, port: int, handler):
    """Start a local websockets server for tests."""
    return await websockets.serve(handler, host, port)


@pytest.mark.asyncio
async def test_hub_client_sends_hello_on_connect(unused_tcp_port) -> None:
    port = unused_tcp_port
    received: list[dict] = []
    first_message: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

    async def handler(ws):
        raw = await ws.recv()
        data = json.loads(raw)
        received.append(data)
        if not first_message.done():
            first_message.set_result(data)
        # Send welcome so client can proceed.
        await ws.send(json.dumps({"kind": "welcome", "server_version": "test"}))
        # Keep open briefly.
        await asyncio.sleep(0.2)

    server = await _fake_server("127.0.0.1", port, handler)
    try:
        registry = Registry(scanner=AsyncMock(return_value=[_dev("aa:bb:cc:dd:ee:01", "10.0.6.1")]))
        registry.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1"))
        client = HubClient(
            api_url=f"ws://127.0.0.1:{port}/ws",
            auth_token=None,
            wrangler_id="pi-test",
            registry=registry,
        )
        task = asyncio.create_task(client.run())
        hello = await asyncio.wait_for(first_message, timeout=2.0)
        assert hello["kind"] == "hello"
        assert hello["wrangler_id"] == "pi-test"
        assert len(hello["devices"]) == 1
        task.cancel()
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_hub_client_responds_to_command(unused_tcp_port) -> None:
    port = unused_tcp_port
    response: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

    async def handler(ws):
        # Ignore Hello.
        await ws.recv()
        await ws.send(json.dumps({"kind": "welcome", "server_version": "test"}))
        # Send a command.
        await ws.send(json.dumps({
            "kind": "command",
            "request_id": "req-1",
            "mac": "aa:bb:cc:dd:ee:01",
            "command": {"kind": "color", "color": {"r": 1, "g": 2, "b": 3}},
        }))
        raw = await ws.recv()
        if not response.done():
            response.set_result(json.loads(raw))
        await asyncio.sleep(0.1)

    server = await _fake_server("127.0.0.1", port, handler)
    try:
        registry = Registry(scanner=AsyncMock())
        registry.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1"))

        # Patch push_command inside hub_client to avoid real HTTP.
        from unittest.mock import patch
        from wrangled_contracts import PushResult

        with patch(
            "wrangler.hub_client.push_command",
            AsyncMock(return_value=PushResult(ok=True, status=200)),
        ):
            client = HubClient(
                api_url=f"ws://127.0.0.1:{port}/ws",
                auth_token=None,
                wrangler_id="pi-test",
                registry=registry,
            )
            task = asyncio.create_task(client.run())
            result = await asyncio.wait_for(response, timeout=2.0)
        assert result["kind"] == "command_result"
        assert result["request_id"] == "req-1"
        assert result["result"]["ok"] is True
        task.cancel()
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_hub_client_sends_pong_to_ping(unused_tcp_port) -> None:
    port = unused_tcp_port
    saw_pong: asyncio.Future[bool] = asyncio.get_event_loop().create_future()

    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"kind": "welcome", "server_version": "test"}))
        await ws.send(json.dumps({"kind": "ping"}))
        raw = await ws.recv()
        if not saw_pong.done():
            saw_pong.set_result(json.loads(raw)["kind"] == "pong")
        await asyncio.sleep(0.1)

    server = await _fake_server("127.0.0.1", port, handler)
    try:
        client = HubClient(
            api_url=f"ws://127.0.0.1:{port}/ws",
            auth_token=None,
            wrangler_id="pi-test",
            registry=Registry(scanner=AsyncMock()),
        )
        task = asyncio.create_task(client.run())
        assert await asyncio.wait_for(saw_pong, timeout=2.0) is True
        task.cancel()
    finally:
        server.close()
        await server.wait_closed()
```

Note: `unused_tcp_port` is a pytest-plugin fixture from `pytest-asyncio` or `pytest-socket`. If it's not available, grab a port manually:

```python
import socket
@pytest.fixture
def unused_tcp_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
```

Add that fixture to `apps/wrangler/tests/conftest.py` if the plugin doesn't provide it.

- [ ] **Step 3: Implement `hub_client.py`**

```python
"""Outbound WS client — wrangler dialing home to api."""

from __future__ import annotations

import asyncio
import json
import logging
from ipaddress import IPv4Address

import httpx
import websockets
from pydantic import TypeAdapter, ValidationError

from wrangled_contracts import (
    ApiMessage,
    CommandResult,
    DevicesChanged,
    GetState,
    Hello,
    Ping,
    Pong,
    PushResult,
    RelayCommand,
    Rescan,
    StateSnapshot,
    Welcome,
    WranglerMessage,
)

from wrangler import __version__
from wrangler.pusher import push_command
from wrangler.scanner import ScanOptions
from wrangler.server.registry import Registry
from wrangler.server.wled_client import WledUnreachableError, fetch_state

logger = logging.getLogger(__name__)

_API_ADAPTER = TypeAdapter(ApiMessage)

_MIN_BACKOFF = 1.0
_MAX_BACKOFF = 60.0


class HubClient:
    """Maintains an outbound WS connection to apps/api.

    Started as a background task when WRANGLED_API_URL is set. Never
    raises out of run(); always reconnects on failure with exponential backoff.
    """

    def __init__(
        self,
        *,
        api_url: str,
        auth_token: str | None,
        wrangler_id: str,
        registry: Registry,
    ) -> None:
        self._api_url = api_url
        self._auth_token = auth_token
        self._wrangler_id = wrangler_id
        self._registry = registry
        self._socket: websockets.WebSocketClientProtocol | None = None
        self._lock = asyncio.Lock()

    async def run(self) -> None:
        backoff = _MIN_BACKOFF
        while True:
            try:
                await self._connect_once()
                backoff = _MIN_BACKOFF   # successful session resets backoff
            except asyncio.CancelledError:
                raise
            except Exception as exc:   # noqa: BLE001
                logger.info("hub_client: connection lost: %s (retry in %.1fs)", exc, backoff)
            finally:
                self._socket = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF)

    async def notify_devices_changed(self) -> None:
        """Push a DevicesChanged to api if connected."""
        if self._socket is None:
            return
        msg = DevicesChanged(devices=self._registry.all())
        try:
            await self._send(msg.model_dump_json())
        except Exception:   # noqa: BLE001
            logger.debug("hub_client: notify_devices_changed failed; will retry on reconnect")

    # ----------- internals -----------

    async def _send(self, raw: str) -> None:
        async with self._lock:
            sock = self._socket
            if sock is None:
                return
            await sock.send(raw)

    async def _connect_once(self) -> None:
        url = self._api_url
        if self._auth_token:
            joiner = "&" if "?" in url else "?"
            url = f"{url}{joiner}token={self._auth_token}"
        async with websockets.connect(url) as sock:
            self._socket = sock
            hello = Hello(
                wrangler_id=self._wrangler_id,
                wrangler_version=__version__,
                devices=self._registry.all(),
            )
            await sock.send(hello.model_dump_json())
            async for raw in sock:
                await self._handle(raw)

    async def _handle(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            message = _API_ADAPTER.validate_json(raw)
        except ValidationError as exc:
            logger.debug("hub_client: invalid message: %s", exc)
            return

        if isinstance(message, Welcome):
            logger.info("hub_client: connected to api (server_version=%s)", message.server_version)
            return
        if isinstance(message, Ping):
            await self._send(Pong().model_dump_json())
            return
        if isinstance(message, RelayCommand):
            asyncio.create_task(self._handle_command(message))
            return
        if isinstance(message, GetState):
            asyncio.create_task(self._handle_get_state(message))
            return
        if isinstance(message, Rescan):
            asyncio.create_task(self._handle_rescan())
            return

    async def _handle_command(self, msg: RelayCommand) -> None:
        device = self._registry.get(msg.mac)
        if device is None:
            result = PushResult(ok=False, error=f"unknown device on this wrangler: {msg.mac}")
        else:
            async with httpx.AsyncClient() as client:
                result = await push_command(client, device, msg.command)
        await self._send(
            CommandResult(request_id=msg.request_id, result=result).model_dump_json(),
        )

    async def _handle_get_state(self, msg: GetState) -> None:
        device = self._registry.get(msg.mac)
        if device is None:
            snapshot = StateSnapshot(
                request_id=msg.request_id, mac=msg.mac, state=None,
                error=f"unknown device on this wrangler: {msg.mac}",
            )
        else:
            async with httpx.AsyncClient() as client:
                try:
                    state = await fetch_state(client, device)
                    snapshot = StateSnapshot(request_id=msg.request_id, mac=msg.mac, state=state)
                except WledUnreachableError as exc:
                    snapshot = StateSnapshot(
                        request_id=msg.request_id, mac=msg.mac, state=None, error=str(exc),
                    )
        await self._send(snapshot.model_dump_json())

    async def _handle_rescan(self) -> None:
        await self._registry.scan(ScanOptions(mdns_timeout=2.0))
        # Registry.on_changed will fire notify_devices_changed.
```

- [ ] **Step 4: Run + lint + commit**

```bash
cd apps/wrangler
uv run pytest tests/test_hub_client.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler
git commit -m "feat(wrangler): add HubClient with connect/handshake/dispatch"
```

---

## Task 10: Wire `HubClient` into `wrangler serve` + `rescan_all` coverage

**Files:**
- Modify: `apps/wrangler/src/wrangler/server/app.py`

- [ ] **Step 1: Update `app.py`**

Replace `apps/wrangler/src/wrangler/server/app.py`:

```python
"""FastAPI app factory for the wrangler agent."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wrangler.hub_client import HubClient
from wrangler.scanner import ScanOptions, scan
from wrangler.server.devices import build_devices_router
from wrangler.server.metadata import build_metadata_router
from wrangler.server.registry import Registry
from wrangler.settings import WranglerSettings


def create_app(
    *,
    initial_scan: bool = True,
    registry: Registry | None = None,
    scan_options: ScanOptions | None = None,
) -> FastAPI:
    """Build the wrangler FastAPI application."""
    app = FastAPI(title="wrangler", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    reg = registry if registry is not None else Registry(scanner=scan)
    opts = scan_options or ScanOptions(mdns_timeout=2.0)
    settings = WranglerSettings()

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(build_devices_router(reg))
    app.include_router(build_metadata_router())

    hub_client: HubClient | None = None
    if settings.api_url:
        hub_client = HubClient(
            api_url=settings.api_url,
            auth_token=settings.auth_token,
            wrangler_id=settings.wrangler_id,
            registry=reg,
        )
        reg.on_changed(hub_client.notify_devices_changed)

    if initial_scan or hub_client is not None:
        @app.on_event("startup")
        async def _startup() -> None:
            if initial_scan:
                await reg.scan(opts)
            if hub_client is not None:
                app.state.hub_task = asyncio.create_task(hub_client.run())

        @app.on_event("shutdown")
        async def _shutdown() -> None:
            task = getattr(app.state, "hub_task", None)
            if task is not None:
                task.cancel()

    static_dir = Path(__file__).resolve().parents[3] / "static" / "wrangler-ui"
    if static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=static_dir, html=True),
            name="wrangler-ui",
        )

    return app
```

- [ ] **Step 2: Verify existing wrangler tests still pass**

```bash
cd apps/wrangler
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```
Expected: all prior tests green. No new test added here — the HubClient behavior is tested in Task 9; app.py is wiring.

- [ ] **Step 3: Commit**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler
git commit -m "feat(wrangler): boot HubClient on serve startup when api_url set"
```

---

## Task 11: End-to-end integration test

**Files:**
- Create: `apps/api/tests/test_end_to_end.py`

- [ ] **Step 1: Write test**

`apps/api/tests/test_end_to_end.py`:

```python
"""End-to-end: real api + real HubClient (with mocked pusher) round-trip."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import uvicorn
from wrangled_contracts import PushResult, WledDevice

from api.server import create_app
from wrangler.hub_client import HubClient
from wrangler.server.registry import Registry


def _dev() -> WledDevice:
    return WledDevice(
        ip=IPv4Address("10.0.6.207"),
        name="WLED-Matrix",
        mac="aa:bb:cc:dd:ee:ff",
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_post_command_round_trips_to_wrangler(unused_tcp_port) -> None:
    port = unused_tcp_port
    app = create_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", loop="asyncio")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Wait for boot.
    for _ in range(50):
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"http://127.0.0.1:{port}/healthz")
                if r.status_code == 200:
                    break
        except Exception:
            await asyncio.sleep(0.05)

    try:
        registry = Registry(scanner=AsyncMock(return_value=[_dev()]))
        registry.put(_dev())

        with patch(
            "wrangler.hub_client.push_command",
            AsyncMock(return_value=PushResult(ok=True, status=200)),
        ):
            hub_client = HubClient(
                api_url=f"ws://127.0.0.1:{port}/ws",
                auth_token=None,
                wrangler_id="pi-e2e",
                registry=registry,
            )
            run_task = asyncio.create_task(hub_client.run())

            # Wait for registration.
            for _ in range(100):
                async with httpx.AsyncClient() as c:
                    r = await c.get(f"http://127.0.0.1:{port}/api/wranglers")
                    if r.status_code == 200 and len(r.json()) == 1:
                        break
                await asyncio.sleep(0.05)

            async with httpx.AsyncClient() as c:
                resp = await c.post(
                    f"http://127.0.0.1:{port}/api/devices/aa:bb:cc:dd:ee:ff/commands",
                    json={"kind": "color", "color": {"r": 0, "g": 0, "b": 255}},
                    timeout=5.0,
                )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

            run_task.cancel()
    finally:
        server.should_exit = True
        await server_task
```

The `unused_tcp_port` fixture from Task 9 applies here too; add it to `apps/api/tests/conftest.py` if absent:

```python
import socket
import pytest

@pytest.fixture
def unused_tcp_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
```

- [ ] **Step 2: Install wrangler as dev dep of api**

The test imports `wrangler.hub_client` and `wrangler.server.registry`. Add to `apps/api/pyproject.toml` `[dependency-groups].dev`:

```toml
    "wrangler",
```

And under `[tool.uv.sources]`:

```toml
wrangler = { path = "../wrangler", editable = true }
```

Then:

```bash
cd apps/api
uv sync
```

- [ ] **Step 3: Run + lint + commit**

```bash
uv run pytest tests/test_end_to_end.py -v
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/api
git commit -m "test(api): end-to-end round-trip test with real HubClient"
```

---

## Task 12: Build + dev scripts + CLAUDE.md + live verification

**Files:**
- Modify: `build.sh`
- Modify: `dev.sh`
- Modify: `lint.sh`
- Modify: `apps/wrangler/CLAUDE.md`
- Modify: `CLAUDE.md` (root)

- [ ] **Step 1: `build.sh`**

Add under the existing python blocks:

```bash
echo "=== python: apps/api ==="
( cd "$ROOT/apps/api" && uv sync )
```

And under tests:

```bash
echo "=== tests: apps/api ==="
( cd "$ROOT/apps/api" && uv run pytest -v )
```

- [ ] **Step 2: `dev.sh`**

Add to the concurrent process list:

```bash
echo "starting api FastAPI on :8500"
( cd "$ROOT/apps/api" && uv run api serve --host 127.0.0.1 --port 8500 ) &
```

And update the summary:

```bash
echo "  api:          http://localhost:8500/healthz"
```

- [ ] **Step 3: `lint.sh`**

Update `PY_APPS`:

```bash
PY_APPS=(packages/contracts apps/wrangler apps/api)
```

- [ ] **Step 4: Update `apps/wrangler/CLAUDE.md`**

Append after the existing `serve` block:

```markdown

### Dial home to the central api

Set these env vars so `wrangler serve` opens an outbound WS to `apps/api`:

    export WRANGLED_API_URL=ws://localhost:8500/ws
    export WRANGLED_AUTH_TOKEN=devtoken
    export WRANGLED_WRANGLER_ID=pi-venue    # optional; defaults to hostname

Without `WRANGLED_API_URL`, the hub client is inactive — wrangler runs
exactly as before.
```

- [ ] **Step 5: Update root `CLAUDE.md`**

Update the "Layout" block:

```markdown
- `apps/api/` — FastAPI central hub. Multi-wrangler WS endpoint + REST. Serves dashboard static.
```

And update "Design principles" to reflect dial-home semantics:

```markdown
- Wranglers dial home to `api` over WSS (pre-shared-key auth). Commands from any external sender route through `api` to the owning wrangler.
```

- [ ] **Step 6: Run full build**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
./build.sh
```

Expected: ends with `build ok`.

- [ ] **Step 7: Live verification — three-terminal test**

**Terminal 1** (api):

```bash
cd apps/api
WRANGLED_AUTH_TOKEN=devtoken uv run api serve
```

Expected: uvicorn says it's listening on :8500.

**Terminal 2** (wrangler dialing home):

```bash
cd apps/wrangler
WRANGLED_API_URL=ws://localhost:8500/ws \
WRANGLED_AUTH_TOKEN=devtoken \
WRANGLED_WRANGLER_ID=pi-dev \
  uv run wrangler serve
```

Expected: wrangler starts, scans LAN, dials home. Check terminal 1's logs for `hub_client connected`.

**Terminal 3** (remote caller):

```bash
curl -s -H "Authorization: Bearer devtoken" http://localhost:8500/api/wranglers | python3 -m json.tool
# Expected: one wrangler, wrangler_id=pi-dev, device_count >= 1

MAC=$(curl -s -H "Authorization: Bearer devtoken" http://localhost:8500/api/devices \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["devices"][0]["mac"])')

curl -s -X POST "http://localhost:8500/api/devices/$MAC/commands" \
  -H "Authorization: Bearer devtoken" \
  -H 'Content-Type: application/json' \
  -d '{"kind":"color","color":{"r":0,"g":0,"b":255},"brightness":3}'
# Expected: {"ok": true, "status": 200, "error": null}
```

The matrix should change to dim blue — end-to-end through api.

Stop both processes (Ctrl-C).

- [ ] **Step 8: Commit**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
git add build.sh dev.sh lint.sh apps/wrangler/CLAUDE.md CLAUDE.md
git commit -m "chore(m4): wire apps/api into build/dev/lint; docs"
```

---

## Self-Review Notes

### Spec coverage

| Spec section | Task |
|---|---|
| WS protocol envelopes | T1 |
| api scaffolding + /healthz + auth | T2 |
| Hub + WranglerConnection + request/response | T3 |
| /ws endpoint (handshake, loop, heartbeat) | T4 |
| REST endpoints (devices, state, commands, scan, wranglers) | T5 |
| `api serve` CLI + static mount | T6 |
| Registry observer hook | T7 |
| Wrangler settings (auth_token, wrangler_id) | T8 |
| HubClient (connect, handshake, dispatch, command + state + rescan + pong) | T9 |
| HubClient wired into `wrangler serve` startup/shutdown | T10 |
| End-to-end integration test | T11 |
| Build/dev/lint + CLAUDE.md + live verification | T12 |

### Placeholder scan

None. Every step has concrete code + commands. No "add appropriate error handling" language.

### Type consistency

- `WranglerConnection(wrangler_id, socket, wrangler_version, ...)` identical across T3, T4, T9, T11.
- `Hub` method names (`attach`, `detach`, `send_command`, `get_state`, `rescan_all`, `apply_devices`, `resolve_response`, `all_devices`, `find_device`, `wranglers_summary`) match between T3 definition and T4/T5 callers.
- `HubClient(api_url, auth_token, wrangler_id, registry)` same signature in T9 and T10.
- `Hello(wrangler_id, wrangler_version, devices)` / `CommandResult(request_id, result)` / etc. shapes match between contracts (T1), hub (T3), ws (T4), hub_client (T9).
- `PushResult` is defined once in `wrangled_contracts.hub` (T1) and re-exported from wrangler's pusher for back-compat.
- `Registry.on_changed(cb)` matches between definition (T7) and caller (T10).

### Scope boundary

No Discord bot, no rate limits, no dashboard interactivity, no persistence — all explicitly deferred per spec.
