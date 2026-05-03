# M3: Wrangler FastAPI Server + Wrangler-UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a FastAPI server (`wrangler serve`) on port 8501 that wraps the existing scanner + pusher as HTTP endpoints, plus a Vite/React UI (`apps/wrangler-ui/`) that's built and served by that FastAPI, so the user can drive the matrix interactively from a browser.

**Architecture:** New `apps/wrangler/src/wrangler/server/` package (app factory, routers, registry, WLED read/config client). Existing pusher is reused. UI is a new Vite/React app in `apps/wrangler-ui/` built into `apps/wrangler/static/wrangler-ui/` for FastAPI to serve as static assets. Multi-device UI polls state every 2s.

**Tech Stack:** FastAPI, uvicorn, httpx (all async), pydantic v2 (existing Command contract reused). Vite + React (plain JSX). No UI tests this milestone.

Spec: `docs/superpowers/specs/2026-04-13-m3-wrangler-server-ui-design.md`.

## File Structure

```
apps/wrangler/
├── pyproject.toml                                 # MODIFY: add fastapi, uvicorn
├── src/wrangler/
│   ├── cli.py                                     # MODIFY: add `serve` subcommand
│   └── server/
│       ├── __init__.py                            # CREATE: re-exports create_app
│       ├── app.py                                 # CREATE: FastAPI factory, /healthz, static mount
│       ├── devices.py                             # CREATE: APIRouter — /api/devices/*, /api/scan
│       ├── metadata.py                            # CREATE: APIRouter — /api/effects, /api/presets, /api/emoji
│       ├── registry.py                            # CREATE: in-memory dict + asyncio.Lock
│       └── wled_client.py                         # CREATE: fetch_state, set_name httpx helpers
├── static/wrangler-ui/                            # (build output; gitignored)
└── tests/
    ├── test_server_app.py                         # CREATE
    ├── test_server_devices.py                     # CREATE
    ├── test_server_metadata.py                    # CREATE
    ├── test_server_registry.py                    # CREATE
    └── test_server_wled_client.py                 # CREATE

apps/wrangler-ui/                                  # CREATE entire app
├── package.json
├── vite.config.js
├── eslint.config.js
├── index.html
├── CLAUDE.md
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── api.js
    ├── index.css
    └── components/
        ├── DeviceSelector.jsx
        ├── LiveState.jsx
        ├── BrightnessSlider.jsx
        ├── ColorTab.jsx
        ├── EffectTab.jsx
        ├── TextTab.jsx
        ├── PresetTab.jsx
        ├── EmojiTab.jsx
        └── PowerTab.jsx

build.sh                                            # MODIFY: add wrangler-ui build step
dev.sh                                              # MODIFY: start wrangler FastAPI + ui Vite
.gitignore                                          # MODIFY: exclude static/wrangler-ui/
apps/wrangler/CLAUDE.md                             # MODIFY: document serve subcommand
```

---

## Task 1: Add FastAPI deps + `create_app()` skeleton + `/healthz`

**Files:**
- Modify: `apps/wrangler/pyproject.toml`
- Create: `apps/wrangler/src/wrangler/server/__init__.py`
- Create: `apps/wrangler/src/wrangler/server/app.py`
- Create: `apps/wrangler/tests/test_server_app.py`

- [ ] **Step 1: Add deps to `apps/wrangler/pyproject.toml`**

Append to the `[project] dependencies` list:

```toml
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
```

- [ ] **Step 2: uv sync**

```bash
cd apps/wrangler
uv sync
```
Expected: FastAPI + uvicorn installed, no errors.

- [ ] **Step 3: Write failing test**

`apps/wrangler/tests/test_server_app.py`:

```python
"""Tests for wrangler.server.app."""

from __future__ import annotations

from fastapi.testclient import TestClient

from wrangler.server import create_app


def test_healthz_returns_ok() -> None:
    app = create_app(initial_scan=False)
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_static_mount_absent_returns_404_at_root() -> None:
    app = create_app(initial_scan=False)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 404
```

- [ ] **Step 4: Run — verify fail**

```bash
uv run pytest tests/test_server_app.py -v
```
Expected: ImportError — `wrangler.server` missing.

- [ ] **Step 5: Implement `create_app()`**

`apps/wrangler/src/wrangler/server/__init__.py`:

```python
"""Wrangler FastAPI server."""

from wrangler.server.app import create_app

__all__ = ["create_app"]
```

`apps/wrangler/src/wrangler/server/app.py`:

```python
"""FastAPI app factory for the wrangler agent."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


def create_app(
    *,
    initial_scan: bool = True,
) -> FastAPI:
    """Build the wrangler FastAPI application.

    When `initial_scan=False`, the server does not perform a scan on
    startup — useful for tests that inject mocked dependencies.
    """
    app = FastAPI(title="wrangler", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    static_dir = Path(__file__).resolve().parents[3] / "static" / "wrangler-ui"
    if static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=static_dir, html=True),
            name="wrangler-ui",
        )

    _ = initial_scan  # wired up in a later task
    return app
```

- [ ] **Step 6: Run — verify pass**

```bash
uv run pytest tests/test_server_app.py -v
```
Expected: 2 passed.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/pyproject.toml apps/wrangler/src/wrangler/server apps/wrangler/tests/test_server_app.py
git commit -m "feat(wrangler): add FastAPI server skeleton + /healthz"
```

---

## Task 2: `Registry` — in-memory device map with scan lock

**Files:**
- Create: `apps/wrangler/src/wrangler/server/registry.py`
- Create: `apps/wrangler/tests/test_server_registry.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_server_registry.py`:

```python
"""Tests for wrangler.server.registry."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest

from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions
from wrangler.server.registry import Registry


def _dev(mac: str, ip: str, name: str) -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name=name,
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_registry_starts_empty() -> None:
    r = Registry(scanner=AsyncMock())
    assert r.all() == []
    assert r.get("aa:bb:cc:dd:ee:ff") is None


@pytest.mark.asyncio
async def test_registry_scan_populates_map() -> None:
    fake_scan = AsyncMock(return_value=[_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")])
    r = Registry(scanner=fake_scan)
    devices = await r.scan(ScanOptions(mdns_timeout=0.01))
    assert len(devices) == 1
    assert r.get("aa:bb:cc:dd:ee:01") is not None
    assert len(r.all()) == 1


@pytest.mark.asyncio
async def test_registry_scan_replaces_previous() -> None:
    first = [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")]
    second = [_dev("aa:bb:cc:dd:ee:02", "10.0.6.2", "B")]
    fake_scan = AsyncMock(side_effect=[first, second])
    r = Registry(scanner=fake_scan)
    await r.scan(ScanOptions(mdns_timeout=0.01))
    await r.scan(ScanOptions(mdns_timeout=0.01))
    macs = [d.mac for d in r.all()]
    assert macs == ["aa:bb:cc:dd:ee:02"]


@pytest.mark.asyncio
async def test_registry_concurrent_scans_serialize() -> None:
    calls = 0

    async def slow_scan(_opts: ScanOptions) -> list[WledDevice]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return [_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A")]

    r = Registry(scanner=slow_scan)
    a, b = await asyncio.gather(
        r.scan(ScanOptions(mdns_timeout=0.01)),
        r.scan(ScanOptions(mdns_timeout=0.01)),
    )
    assert a == b
    assert calls == 2  # both awaited serially — not at the same time


@pytest.mark.asyncio
async def test_registry_put_replaces_single_device() -> None:
    r = Registry(scanner=AsyncMock())
    await r.scan(ScanOptions(mdns_timeout=0.01))  # empty result
    r.put(_dev("aa:bb:cc:dd:ee:01", "10.0.6.1", "A-renamed"))
    assert r.get("aa:bb:cc:dd:ee:01").name == "A-renamed"
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_server_registry.py -v
```
Expected: ImportError — `Registry` missing.

- [ ] **Step 3: Implement `Registry`**

`apps/wrangler/src/wrangler/server/registry.py`:

```python
"""In-memory registry of discovered WLED devices, with serialized scans."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions

ScanFn = Callable[[ScanOptions], Awaitable[list[WledDevice]]]


class Registry:
    """Tracks the most recent scan result, keyed by MAC."""

    def __init__(self, *, scanner: ScanFn) -> None:
        self._scanner = scanner
        self._devices: dict[str, WledDevice] = {}
        self._lock = asyncio.Lock()

    def all(self) -> list[WledDevice]:
        """Return all known devices, sorted by IP."""
        return sorted(self._devices.values(), key=lambda d: int(d.ip))

    def get(self, mac: str) -> WledDevice | None:
        return self._devices.get(mac)

    def put(self, device: WledDevice) -> None:
        """Replace (or add) a single device in-place."""
        self._devices[device.mac] = device

    async def scan(self, opts: ScanOptions) -> list[WledDevice]:
        """Run a fresh scan; replace the full registry with the results."""
        async with self._lock:
            discovered = await self._scanner(opts)
            self._devices = {d.mac: d for d in discovered}
            return self.all()
```

- [ ] **Step 4: Run — verify pass**

```bash
uv run pytest tests/test_server_registry.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/server/registry.py apps/wrangler/tests/test_server_registry.py
git commit -m "feat(wrangler): add in-memory device Registry with scan lock"
```

---

## Task 3: `wled_client` — fetch_state + set_name

**Files:**
- Create: `apps/wrangler/src/wrangler/server/wled_client.py`
- Create: `apps/wrangler/tests/test_server_wled_client.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_server_wled_client.py`:

```python
"""Tests for wrangler.server.wled_client."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address

import httpx
import pytest
import respx

from wrangled_contracts import WledDevice

from wrangler.server.wled_client import WledUnreachableError, fetch_state, set_name


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
@respx.mock
async def test_fetch_state_returns_parsed_body() -> None:
    payload = {"on": True, "bri": 80, "seg": [{"fx": 149, "col": [[255, 80, 0]]}]}
    respx.get("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(200, json=payload),
    )
    async with httpx.AsyncClient() as client:
        state = await fetch_state(client, _dev())
    assert state == payload


@pytest.mark.asyncio
@respx.mock
async def test_fetch_state_raises_on_non_200() -> None:
    respx.get("http://10.0.6.207/json/state").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(WledUnreachableError):
            await fetch_state(client, _dev())


@pytest.mark.asyncio
@respx.mock
async def test_fetch_state_raises_on_timeout() -> None:
    respx.get("http://10.0.6.207/json/state").mock(side_effect=httpx.ReadTimeout)
    async with httpx.AsyncClient() as client:
        with pytest.raises(WledUnreachableError):
            await fetch_state(client, _dev())


@pytest.mark.asyncio
@respx.mock
async def test_set_name_posts_to_json_cfg() -> None:
    route = respx.post("http://10.0.6.207/json/cfg").mock(
        return_value=httpx.Response(200, json={"success": True}),
    )
    async with httpx.AsyncClient() as client:
        await set_name(client, _dev(), "Stage-Left")
    assert route.called
    body = route.calls.last.request.read()
    assert b'"Stage-Left"' in body
    assert b'"id"' in body


@pytest.mark.asyncio
@respx.mock
async def test_set_name_raises_on_failure() -> None:
    respx.post("http://10.0.6.207/json/cfg").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(WledUnreachableError):
            await set_name(client, _dev(), "x")
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_server_wled_client.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `wled_client`**

`apps/wrangler/src/wrangler/server/wled_client.py`:

```python
"""HTTP helpers for reading live state and setting the WLED device name."""

from __future__ import annotations

import json
import logging

import httpx

from wrangled_contracts import WledDevice

logger = logging.getLogger(__name__)


class WledUnreachableError(RuntimeError):
    """Raised when a WLED device does not respond to a read or cfg write."""


async def fetch_state(
    client: httpx.AsyncClient,
    device: WledDevice,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> dict:
    """GET /json/state from the device. Raise WledUnreachableError on failure."""
    url = f"http://{device.ip}/json/state"
    try:
        response = await client.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        logger.debug("fetch_state %s: %s", device.ip, exc)
        msg = f"could not reach {device.ip}: {exc}"
        raise WledUnreachableError(msg) from exc

    if response.status_code != httpx.codes.OK:
        msg = f"{device.ip} returned {response.status_code}"
        raise WledUnreachableError(msg)

    try:
        return response.json()
    except ValueError as exc:
        msg = f"{device.ip} returned non-JSON body"
        raise WledUnreachableError(msg) from exc


async def set_name(
    client: httpx.AsyncClient,
    device: WledDevice,
    new_name: str,
    *,
    timeout: float = 2.0,  # noqa: ASYNC109
) -> None:
    """POST to /json/cfg to change the device name on WLED itself."""
    url = f"http://{device.ip}/json/cfg"
    body = {"id": {"name": new_name}}
    try:
        response = await client.post(
            url,
            content=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        msg = f"could not reach {device.ip}: {exc}"
        raise WledUnreachableError(msg) from exc

    if response.status_code != httpx.codes.OK:
        msg = f"{device.ip} returned {response.status_code}"
        raise WledUnreachableError(msg)
```

- [ ] **Step 4: Run + lint + commit**

```bash
uv run pytest tests/test_server_wled_client.py -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/server/wled_client.py apps/wrangler/tests/test_server_wled_client.py
git commit -m "feat(wrangler): add wled_client (fetch_state + set_name)"
```

---

## Task 4: `devices` router — list + single + scan

**Files:**
- Create: `apps/wrangler/src/wrangler/server/devices.py`
- Modify: `apps/wrangler/src/wrangler/server/app.py`
- Create: `apps/wrangler/tests/test_server_devices.py`

- [ ] **Step 1: Write failing tests (only the 3 endpoints for this task)**

`apps/wrangler/tests/test_server_devices.py`:

```python
"""Tests for the devices/scan endpoints in wrangler.server.devices."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from wrangled_contracts import WledDevice

from wrangler.server import create_app
from wrangler.server.registry import Registry


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


@pytest.fixture
def registry_with_one() -> Registry:
    r = Registry(scanner=AsyncMock(return_value=[_dev()]))
    r.put(_dev())
    return r


@pytest.fixture
def app_with_registry(registry_with_one: Registry):
    app = create_app(initial_scan=False, registry=registry_with_one)
    return app


def test_get_devices_returns_list(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["mac"] == "aa:bb:cc:dd:ee:ff"


def test_get_device_by_mac_returns_device(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices/aa:bb:cc:dd:ee:ff")
    assert response.status_code == 200
    assert response.json()["mac"] == "aa:bb:cc:dd:ee:ff"


def test_get_device_by_mac_404(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices/zz:zz:zz:zz:zz:zz")
    assert response.status_code == 404


def test_post_scan_invokes_registry_scan() -> None:
    scanner = AsyncMock(return_value=[_dev("11:22:33:44:55:66", "10.0.6.10")])
    registry = Registry(scanner=scanner)
    app = create_app(initial_scan=False, registry=registry)
    client = TestClient(app)
    response = client.post("/api/scan")
    assert response.status_code == 200
    data = response.json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["mac"] == "11:22:33:44:55:66"
    scanner.assert_awaited_once()
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_server_devices.py -v
```
Expected: `create_app` rejects `registry=...` kwarg and devices router doesn't exist.

- [ ] **Step 3: Implement — update `create_app()` to accept a `Registry` + wire the devices router**

Rewrite `apps/wrangler/src/wrangler/server/app.py`:

```python
"""FastAPI app factory for the wrangler agent."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from wrangler.scanner import ScanOptions, scan
from wrangler.server.devices import build_devices_router
from wrangler.server.registry import Registry


def create_app(
    *,
    initial_scan: bool = True,
    registry: Registry | None = None,
    scan_options: ScanOptions | None = None,
) -> FastAPI:
    """Build the wrangler FastAPI application.

    Args:
        initial_scan: if True, run a single scan on startup.
        registry: inject a pre-built Registry (tests). If None, a default one
            backed by `wrangler.scanner.scan` is constructed.
        scan_options: passed to the initial scan.
    """
    app = FastAPI(title="wrangler", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    reg = registry if registry is not None else Registry(scanner=scan)
    opts = scan_options or ScanOptions(mdns_timeout=2.0)

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(build_devices_router(reg))

    if initial_scan:
        @app.on_event("startup")
        async def _initial_scan() -> None:
            await reg.scan(opts)

    static_dir = Path(__file__).resolve().parents[3] / "static" / "wrangler-ui"
    if static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=static_dir, html=True),
            name="wrangler-ui",
        )

    return app
```

`apps/wrangler/src/wrangler/server/devices.py`:

```python
"""Devices + scan routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions
from wrangler.server.registry import Registry


def build_devices_router(registry: Registry) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/devices")
    def list_devices() -> dict[str, list[WledDevice]]:
        return {"devices": registry.all()}

    @router.get("/devices/{mac}")
    def get_device(mac: str) -> WledDevice:
        device = registry.get(mac)
        if device is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        return device

    @router.post("/scan")
    async def run_scan() -> dict[str, list[WledDevice]]:
        devices = await registry.scan(ScanOptions(mdns_timeout=2.0))
        return {"devices": devices}

    return router
```

- [ ] **Step 4: Run + lint + commit**

```bash
uv run pytest tests/test_server_devices.py -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/server apps/wrangler/tests/test_server_devices.py
git commit -m "feat(wrangler): add /api/devices list/get + POST /api/scan"
```

---

## Task 5: `/api/devices/{mac}/state` — live fetch

**Files:**
- Modify: `apps/wrangler/src/wrangler/server/devices.py`
- Modify: `apps/wrangler/tests/test_server_devices.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_server_devices.py`:

```python
from unittest.mock import patch

import httpx


def test_get_state_returns_live_body(app_with_registry) -> None:
    payload = {"on": True, "bri": 80, "seg": [{"fx": 149}]}
    with patch(
        "wrangler.server.devices.fetch_state",
        AsyncMock(return_value=payload),
    ):
        client = TestClient(app_with_registry)
        response = client.get("/api/devices/aa:bb:cc:dd:ee:ff/state")
    assert response.status_code == 200
    assert response.json() == payload


def test_get_state_returns_502_when_wled_down(app_with_registry) -> None:
    from wrangler.server.wled_client import WledUnreachableError
    with patch(
        "wrangler.server.devices.fetch_state",
        AsyncMock(side_effect=WledUnreachableError("dead")),
    ):
        client = TestClient(app_with_registry)
        response = client.get("/api/devices/aa:bb:cc:dd:ee:ff/state")
    assert response.status_code == 502


def test_get_state_404_for_unknown_mac(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.get("/api/devices/zz:zz:zz:zz:zz:zz/state")
    assert response.status_code == 404
```

- [ ] **Step 2: Run — verify fail**

```bash
uv run pytest tests/test_server_devices.py -v
```
Expected: new state-endpoint tests 404 on the route (not registered yet).

- [ ] **Step 3: Implement state endpoint**

Append to `apps/wrangler/src/wrangler/server/devices.py`:

```python
import httpx

from wrangler.server.wled_client import WledUnreachableError, fetch_state
```

Add inside `build_devices_router`:

```python
    @router.get("/devices/{mac}/state")
    async def get_state(mac: str) -> dict:
        device = registry.get(mac)
        if device is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        async with httpx.AsyncClient() as client:
            try:
                return await fetch_state(client, device)
            except WledUnreachableError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
```

- [ ] **Step 4: Run + lint + commit**

```bash
uv run pytest tests/test_server_devices.py -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/server/devices.py apps/wrangler/tests/test_server_devices.py
git commit -m "feat(wrangler): add GET /api/devices/{mac}/state"
```

---

## Task 6: `POST /api/devices/{mac}/commands` — push

**Files:**
- Modify: `apps/wrangler/src/wrangler/server/devices.py`
- Modify: `apps/wrangler/tests/test_server_devices.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_server_devices.py`:

```python
from wrangler.pusher import PushResult


def test_post_command_color_ok(app_with_registry) -> None:
    with patch(
        "wrangler.server.devices.push_command",
        AsyncMock(return_value=PushResult(ok=True, status=200)),
    ):
        client = TestClient(app_with_registry)
        response = client.post(
            "/api/devices/aa:bb:cc:dd:ee:ff/commands",
            json={"kind": "color", "color": {"r": 255, "g": 0, "b": 0}},
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": 200, "error": None}


def test_post_command_422_on_invalid_body(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.post(
        "/api/devices/aa:bb:cc:dd:ee:ff/commands",
        json={"kind": "color"},  # missing color
    )
    assert response.status_code == 422


def test_post_command_404_unknown_mac(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.post(
        "/api/devices/zz:zz:zz:zz:zz:zz/commands",
        json={"kind": "power", "on": False},
    )
    assert response.status_code == 404


def test_post_command_reports_push_failure(app_with_registry) -> None:
    with patch(
        "wrangler.server.devices.push_command",
        AsyncMock(return_value=PushResult(ok=False, status=500, error="boom")),
    ):
        client = TestClient(app_with_registry)
        response = client.post(
            "/api/devices/aa:bb:cc:dd:ee:ff/commands",
            json={"kind": "power", "on": True},
        )
    assert response.status_code == 200  # FastAPI returns the PushResult as body
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == 500
```

- [ ] **Step 2: Run — verify fail**

Expected: commands endpoint doesn't exist.

- [ ] **Step 3: Implement commands endpoint**

In `apps/wrangler/src/wrangler/server/devices.py`, add the pusher imports:

```python
from wrangled_contracts import Command
from wrangler.pusher import PushResult, push_command
```

Add inside `build_devices_router`:

```python
    @router.post("/devices/{mac}/commands")
    async def post_command(mac: str, command: Command) -> PushResult:
        device = registry.get(mac)
        if device is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        async with httpx.AsyncClient() as client:
            return await push_command(client, device, command)
```

- [ ] **Step 4: Run + lint + commit**

```bash
uv run pytest tests/test_server_devices.py -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/server/devices.py apps/wrangler/tests/test_server_devices.py
git commit -m "feat(wrangler): add POST /api/devices/{mac}/commands"
```

---

## Task 7: `PUT /api/devices/{mac}/name` — rename via WLED cfg

**Files:**
- Modify: `apps/wrangler/src/wrangler/server/devices.py`
- Modify: `apps/wrangler/tests/test_server_devices.py`

- [ ] **Step 1: Append failing tests**

Append to `apps/wrangler/tests/test_server_devices.py`:

```python
from wrangler.scanner.probe import probe_device  # noqa: F401 — referenced by patches


def test_put_name_updates_device(app_with_registry, registry_with_one) -> None:
    renamed = _dev()
    renamed_data = renamed.model_dump()
    renamed_data["name"] = "Stage-Left"
    updated = WledDevice.model_validate(renamed_data)

    with (
        patch("wrangler.server.devices.set_name", AsyncMock()),
        patch("wrangler.server.devices.probe_device", AsyncMock(return_value=updated)),
    ):
        client = TestClient(app_with_registry)
        response = client.put(
            "/api/devices/aa:bb:cc:dd:ee:ff/name",
            json={"name": "Stage-Left"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Stage-Left"
    # Registry should now reflect the new name too
    assert registry_with_one.get("aa:bb:cc:dd:ee:ff").name == "Stage-Left"


def test_put_name_404_unknown_mac(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.put(
        "/api/devices/zz:zz:zz:zz:zz:zz/name",
        json={"name": "x"},
    )
    assert response.status_code == 404


def test_put_name_502_when_wled_down(app_with_registry) -> None:
    from wrangler.server.wled_client import WledUnreachableError
    with patch(
        "wrangler.server.devices.set_name",
        AsyncMock(side_effect=WledUnreachableError("dead")),
    ):
        client = TestClient(app_with_registry)
        response = client.put(
            "/api/devices/aa:bb:cc:dd:ee:ff/name",
            json={"name": "x"},
        )
    assert response.status_code == 502


def test_put_name_rejects_empty(app_with_registry) -> None:
    client = TestClient(app_with_registry)
    response = client.put(
        "/api/devices/aa:bb:cc:dd:ee:ff/name",
        json={"name": ""},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run — verify fail**

- [ ] **Step 3: Implement rename endpoint**

Add imports to `apps/wrangler/src/wrangler/server/devices.py`:

```python
from pydantic import BaseModel, Field

from wrangler.scanner.probe import probe_device
from wrangler.server.wled_client import set_name
```

Add the request model and endpoint:

```python
class _RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=32)


    @router.put("/devices/{mac}/name")
    async def put_name(mac: str, body: _RenameBody) -> WledDevice:
        device = registry.get(mac)
        if device is None:
            raise HTTPException(status_code=404, detail=f"unknown device: {mac}")
        async with httpx.AsyncClient() as client:
            try:
                await set_name(client, device, body.name)
                refreshed = await probe_device(
                    client, device.ip, source="mdns", timeout=2.0,
                )
            except WledUnreachableError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
        if refreshed is None:
            raise HTTPException(status_code=502, detail="device did not re-probe")
        registry.put(refreshed)
        return refreshed
```

Place `_RenameBody` at module scope (above `build_devices_router`), and the `put_name` handler inside the existing `build_devices_router` (remove the extra indentation in the code block above — it's shown with indent to illustrate scope).

- [ ] **Step 4: Run + lint + commit**

```bash
uv run pytest tests/test_server_devices.py -v
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/server/devices.py apps/wrangler/tests/test_server_devices.py
git commit -m "feat(wrangler): add PUT /api/devices/{mac}/name via WLED cfg"
```

---

## Task 8: Metadata endpoints — `/api/effects`, `/api/presets`, `/api/emoji`

**Files:**
- Create: `apps/wrangler/src/wrangler/server/metadata.py`
- Modify: `apps/wrangler/src/wrangler/server/app.py`
- Create: `apps/wrangler/tests/test_server_metadata.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_server_metadata.py`:

```python
"""Tests for metadata endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from wrangler.server import create_app


def test_get_effects_returns_curated_list() -> None:
    client = TestClient(create_app(initial_scan=False))
    response = client.get("/api/effects")
    assert response.status_code == 200
    data = response.json()
    expected = {
        "solid", "breathe", "rainbow", "fire", "sparkle",
        "fireworks", "matrix", "pride", "chase", "noise",
    }
    assert set(data["effects"]) == expected


def test_get_presets_returns_three() -> None:
    client = TestClient(create_app(initial_scan=False))
    response = client.get("/api/presets")
    assert response.status_code == 200
    assert set(response.json()["presets"]) == {"pytexas", "party", "chill"}


def test_get_emoji_returns_mapping() -> None:
    client = TestClient(create_app(initial_scan=False))
    response = client.get("/api/emoji")
    assert response.status_code == 200
    data = response.json()["emoji"]
    assert data["🔥"] == "fire"
    assert data["🌈"] == "rainbow"
    assert data["💙"] == "color(0,0,255)"
    assert data["🖤"] == "power(off)"
```

- [ ] **Step 2: Run — verify fail**

- [ ] **Step 3: Implement**

`apps/wrangler/src/wrangler/server/metadata.py`:

```python
"""Metadata routes: curated effects, presets, emoji shortcuts."""

from __future__ import annotations

from fastapi import APIRouter

from wrangled_contracts import (
    EFFECT_FX_ID,
    EMOJI_COMMANDS,
    PRESETS,
    ColorCommand,
    Command,
    EffectCommand,
    PowerCommand,
)


def _summarize(cmd: Command) -> str:
    if isinstance(cmd, EffectCommand):
        return cmd.name
    if isinstance(cmd, ColorCommand):
        return f"color({cmd.color.r},{cmd.color.g},{cmd.color.b})"
    if isinstance(cmd, PowerCommand):
        return f"power({'on' if cmd.on else 'off'})"
    return cmd.kind  # fallback


def build_metadata_router() -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/effects")
    def list_effects() -> dict[str, list[str]]:
        return {"effects": list(EFFECT_FX_ID.keys())}

    @router.get("/presets")
    def list_presets() -> dict[str, list[str]]:
        return {"presets": list(PRESETS.keys())}

    @router.get("/emoji")
    def list_emoji() -> dict[str, dict[str, str]]:
        return {"emoji": {k: _summarize(v) for k, v in EMOJI_COMMANDS.items()}}

    return router
```

In `apps/wrangler/src/wrangler/server/app.py`, import and register:

```python
from wrangler.server.metadata import build_metadata_router
```

Inside `create_app`, after the devices router:

```python
    app.include_router(build_metadata_router())
```

- [ ] **Step 4: Run + lint + commit**

```bash
uv run pytest tests/test_server_metadata.py -v
uv run pytest -v      # all server tests
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/server/metadata.py apps/wrangler/src/wrangler/server/app.py apps/wrangler/tests/test_server_metadata.py
git commit -m "feat(wrangler): add /api/effects /api/presets /api/emoji"
```

---

## Task 9: `wrangler serve` CLI subcommand

**Files:**
- Modify: `apps/wrangler/src/wrangler/cli.py`

- [ ] **Step 1: Add the subparser + dispatcher**

In `_build_parser()`, after the `send` subparser:

```python
    serve_parser = sub.add_parser("serve", help="Run the wrangler HTTP server.")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8501)
    serve_parser.add_argument(
        "--no-initial-scan",
        dest="initial_scan",
        action="store_false",
        help="Skip the startup scan.",
    )
```

Add import at top of `cli.py`:

```python
import uvicorn

from wrangler.server import create_app
```

Add `_run_serve` helper:

```python
def _run_serve(args: argparse.Namespace) -> int:
    app = create_app(initial_scan=args.initial_scan)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0
```

Extend `main` to dispatch:

```python
    if args.command == "serve":
        return _run_serve(args)
```

- [ ] **Step 2: Smoke-run**

```bash
uv run wrangler serve --help
```
Expected: shows all three serve flags.

- [ ] **Step 3: Lint + commit**

```bash
uv run ruff check .
uv run ruff format --check .
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler/src/wrangler/cli.py
git commit -m "feat(wrangler): add 'wrangler serve' subcommand wiring uvicorn"
```

---

## Task 10: Scaffold `apps/wrangler-ui/` (Vite + React + proxy)

**Files:**
- Create: `apps/wrangler-ui/package.json`
- Create: `apps/wrangler-ui/vite.config.js`
- Create: `apps/wrangler-ui/eslint.config.js`
- Create: `apps/wrangler-ui/index.html`
- Create: `apps/wrangler-ui/CLAUDE.md`
- Create: `apps/wrangler-ui/src/main.jsx`
- Create: `apps/wrangler-ui/src/App.jsx` (placeholder)
- Create: `apps/wrangler-ui/src/index.css`
- Modify: `.gitignore`

- [ ] **Step 1: Write `apps/wrangler-ui/package.json`**

```json
{
  "name": "wrangler-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build --outDir ../wrangler/static/wrangler-ui --emptyOutDir",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@eslint/js": "^9.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "eslint": "^9.0.0",
    "eslint-plugin-react": "^7.35.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Write `apps/wrangler-ui/vite.config.js`**

```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8511,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8501',
      '/healthz': 'http://localhost:8501',
    },
  },
});
```

- [ ] **Step 3: Write `apps/wrangler-ui/eslint.config.js`**

```javascript
import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: {
        window: 'readonly',
        document: 'readonly',
        fetch: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        localStorage: 'readonly',
        console: 'readonly',
      },
    },
    plugins: { react, 'react-hooks': reactHooks },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      complexity: ['error', 15],
    },
    settings: { react: { version: '18' } },
  },
  { ignores: ['dist/', 'node_modules/'] },
];
```

- [ ] **Step 4: Write `apps/wrangler-ui/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Wrangler</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write `apps/wrangler-ui/src/main.jsx`**

```javascript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 6: Placeholder `apps/wrangler-ui/src/App.jsx`**

```javascript
export default function App() {
  return (
    <main style={{ padding: '1rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Wrangler</h1>
      <p>UI scaffold — real controls in later tasks.</p>
    </main>
  );
}
```

- [ ] **Step 7: `apps/wrangler-ui/src/index.css`**

```css
:root {
  --bg: #0f1220;
  --fg: #e9eef7;
  --accent: #ff7a00;
  --muted: #6a7488;
  --panel: #1a1f33;
  --border: #2a3150;
}

* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); }
button { cursor: pointer; }
```

- [ ] **Step 8: `apps/wrangler-ui/CLAUDE.md`**

```markdown
# apps/wrangler-ui — Pi Config Panel (Vite + React)

## Purpose
Browser UI for `apps/wrangler/`. Shipped as static assets served by wrangler's FastAPI on port 8501. Lets the user drive a WLED matrix (color, brightness, effect, text, preset, emoji, power) and rename devices.

## Run locally

    cd apps/wrangler-ui
    npm install
    npm run dev               # Vite on http://localhost:8511
                              # proxies /api/* and /healthz to :8501

## Build

    npm run build             # writes ../wrangler/static/wrangler-ui/

## Dev prerequisite
Run `apps/wrangler/` in another terminal: `uv run wrangler serve`

## Key modules
- `src/App.jsx` — top-level layout + tabs
- `src/api.js` — fetch() wrappers (typed by hand)
- `src/components/*` — DeviceSelector, LiveState, Color/Effect/Text/Preset/Emoji/Power tabs, BrightnessSlider

## Gotchas
- Same-origin in prod. Dev server uses Vite's proxy.
- No TypeScript — plain JSX to match apps/dashboard.
```

- [ ] **Step 9: Install + verify dev server starts**

```bash
cd apps/wrangler-ui
npm install
```

Expected: installs cleanly. Don't try to start `npm run dev` (would hang this session).

- [ ] **Step 10: Append `.gitignore`**

Append to `/home/jvogel/src/personal/wrangled-dashboard/.gitignore`:

```
# Built Vite UI, served by wrangler's FastAPI
apps/wrangler/static/wrangler-ui/
```

- [ ] **Step 11: Commit**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler-ui .gitignore
git commit -m "feat(wrangler-ui): scaffold Vite/React UI with api-proxy dev server"
```

---

## Task 11: `api.js` + device selector + rename + rescan

**Files:**
- Create: `apps/wrangler-ui/src/api.js`
- Create: `apps/wrangler-ui/src/components/DeviceSelector.jsx`
- Modify: `apps/wrangler-ui/src/App.jsx`

- [ ] **Step 1: Write `apps/wrangler-ui/src/api.js`**

```javascript
async function jsonOrThrow(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  listDevices: async () => jsonOrThrow(await fetch('/api/devices')),
  rescan: async () => jsonOrThrow(await fetch('/api/scan', { method: 'POST' })),
  getState: async (mac) =>
    jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/state`)),
  rename: async (mac, name) =>
    jsonOrThrow(
      await fetch(`/api/devices/${encodeURIComponent(mac)}/name`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name }),
      }),
    ),
  sendCommand: async (mac, command) =>
    jsonOrThrow(
      await fetch(`/api/devices/${encodeURIComponent(mac)}/commands`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(command),
      }),
    ),
  listEffects: async () => jsonOrThrow(await fetch('/api/effects')),
  listPresets: async () => jsonOrThrow(await fetch('/api/presets')),
  listEmoji: async () => jsonOrThrow(await fetch('/api/emoji')),
};
```

- [ ] **Step 2: `apps/wrangler-ui/src/components/DeviceSelector.jsx`**

```javascript
import { useState } from 'react';
import { api } from '../api.js';

export default function DeviceSelector({ devices, selectedMac, onSelect, onRescan, onRenamed }) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const current = devices.find((d) => d.mac === selectedMac);

  const commitRename = async () => {
    if (!current || !draft.trim()) {
      setRenaming(false);
      return;
    }
    setBusy(true);
    try {
      await api.rename(current.mac, draft.trim());
      onRenamed?.();
    } finally {
      setBusy(false);
      setRenaming(false);
    }
  };

  const rescan = async () => {
    setBusy(true);
    try {
      await onRescan?.();
    } finally {
      setBusy(false);
    }
  };

  return (
    <header style={{ display: 'flex', gap: '1rem', alignItems: 'center', padding: '1rem', borderBottom: '1px solid var(--border)' }}>
      <strong style={{ fontSize: '1.2rem' }}>Wrangler</strong>
      <select
        value={selectedMac || ''}
        onChange={(e) => onSelect(e.target.value)}
        style={{ padding: '0.4rem', background: 'var(--panel)', color: 'var(--fg)', border: '1px solid var(--border)' }}
      >
        {devices.map((d) => (
          <option key={d.mac} value={d.mac}>{d.name}</option>
        ))}
      </select>
      {current && !renaming && (
        <>
          <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
            {current.ip} · {current.matrix ? `${current.matrix.width}x${current.matrix.height}` : `${current.led_count} LEDs`} · v{current.version}
          </span>
          <button onClick={() => { setDraft(current.name); setRenaming(true); }}>✏️ rename</button>
        </>
      )}
      {current && renaming && (
        <>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenaming(false); }}
            autoFocus
          />
          <button disabled={busy} onClick={commitRename}>save</button>
          <button disabled={busy} onClick={() => setRenaming(false)}>cancel</button>
        </>
      )}
      <span style={{ flex: 1 }} />
      <button disabled={busy} onClick={rescan}>{busy ? 'Scanning…' : 'Rescan 🔄'}</button>
    </header>
  );
}
```

- [ ] **Step 3: Rewrite `apps/wrangler-ui/src/App.jsx`**

```javascript
import { useCallback, useEffect, useState } from 'react';
import DeviceSelector from './components/DeviceSelector.jsx';
import { api } from './api.js';

const STORAGE_KEY = 'wrangler.selectedMac';

export default function App() {
  const [devices, setDevices] = useState([]);
  const [selectedMac, setSelectedMac] = useState(localStorage.getItem(STORAGE_KEY));
  const [error, setError] = useState(null);

  const refreshDevices = useCallback(async () => {
    try {
      const { devices } = await api.listDevices();
      setDevices(devices);
      setError(null);
      if (devices.length && !devices.some((d) => d.mac === selectedMac)) {
        const mac = devices[0].mac;
        setSelectedMac(mac);
        localStorage.setItem(STORAGE_KEY, mac);
      }
    } catch (e) {
      setError(e.message);
    }
  }, [selectedMac]);

  useEffect(() => { refreshDevices(); }, [refreshDevices]);

  const handleSelect = (mac) => {
    setSelectedMac(mac);
    localStorage.setItem(STORAGE_KEY, mac);
  };

  const handleRescan = async () => {
    try {
      const { devices } = await api.rescan();
      setDevices(devices);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div>
      <DeviceSelector
        devices={devices}
        selectedMac={selectedMac}
        onSelect={handleSelect}
        onRescan={handleRescan}
        onRenamed={refreshDevices}
      />
      {error && (
        <div style={{ padding: '0.5rem 1rem', background: '#3a1212', color: '#ffd6d6' }}>
          {error}
        </div>
      )}
      {!devices.length && (
        <p style={{ padding: '1rem', color: 'var(--muted)' }}>
          No devices found. Click Rescan to search the LAN.
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Lint + commit**

```bash
cd apps/wrangler-ui
npm run lint
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler-ui/src
git commit -m "feat(wrangler-ui): device selector with rescan + inline rename"
```

---

## Task 12: LiveState panel (2s polling)

**Files:**
- Create: `apps/wrangler-ui/src/components/LiveState.jsx`
- Modify: `apps/wrangler-ui/src/App.jsx`

- [ ] **Step 1: Write `apps/wrangler-ui/src/components/LiveState.jsx`**

```javascript
import { useEffect, useState } from 'react';
import { api } from '../api.js';

function fxName(effects, fxId) {
  // effects is the list we got from /api/effects; we don't have a reverse map on the client.
  // For now, show the raw fx id. Future: add reverse mapping via /api/effects returning {name, id}.
  return `fx ${fxId}`;
  // eslint-disable-next-line no-unused-vars
}

function swatch(rgb) {
  if (!rgb || rgb.length < 3) return null;
  const [r, g, b] = rgb;
  return (
    <span style={{
      display: 'inline-block', width: '1rem', height: '1rem',
      backgroundColor: `rgb(${r},${g},${b})`, border: '1px solid var(--border)',
      verticalAlign: 'middle', marginRight: '0.25rem',
    }} />
  );
}

export default function LiveState({ selectedMac }) {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!selectedMac) return undefined;
    let cancelled = false;

    const poll = async () => {
      try {
        const s = await api.getState(selectedMac);
        if (!cancelled) { setState(s); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    };
    poll();
    const handle = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(handle); };
  }, [selectedMac]);

  if (!selectedMac) return null;
  if (error) return <section style={{ padding: '0.5rem 1rem', color: '#ffb0b0' }}>Live state: {error}</section>;
  if (!state) return <section style={{ padding: '0.5rem 1rem', color: 'var(--muted)' }}>Live state: loading…</section>;

  const seg = state.seg?.[0] || {};
  const col = seg.col?.[0];

  return (
    <section style={{ padding: '0.75rem 1rem', background: 'var(--panel)', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', fontSize: '0.95rem' }}>
        <span>{state.on ? '● ON' : '○ off'}</span>
        <span>bri {state.bri}</span>
        <span>{fxName(null, seg.fx)}</span>
        <span>{swatch(col)}{col ? `rgb(${col.join(',')})` : ''}</span>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Mount `LiveState` in `App.jsx`**

Edit `apps/wrangler-ui/src/App.jsx` — add import and render below the error banner:

```javascript
import LiveState from './components/LiveState.jsx';
```

And insert into the `return` tree, right after the error banner:

```javascript
      {selectedMac && <LiveState selectedMac={selectedMac} />}
```

- [ ] **Step 3: Lint + commit**

```bash
cd apps/wrangler-ui
npm run lint
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler-ui/src
git commit -m "feat(wrangler-ui): live state panel polling every 2s"
```

---

## Task 13: BrightnessSlider + Color + Power tabs

**Files:**
- Create: `apps/wrangler-ui/src/components/BrightnessSlider.jsx`
- Create: `apps/wrangler-ui/src/components/ColorTab.jsx`
- Create: `apps/wrangler-ui/src/components/PowerTab.jsx`
- Modify: `apps/wrangler-ui/src/App.jsx`

- [ ] **Step 1: `BrightnessSlider.jsx`**

```javascript
import { useState } from 'react';

export default function BrightnessSlider({ onCommit }) {
  const [value, setValue] = useState(80);
  return (
    <div style={{ padding: '1rem', borderTop: '1px solid var(--border)', display: 'flex', gap: '1rem', alignItems: 'center' }}>
      <label>Brightness</label>
      <input
        type="range"
        min={0}
        max={200}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        onPointerUp={() => onCommit(value)}
        onKeyUp={() => onCommit(value)}
        style={{ flex: 1 }}
      />
      <span style={{ minWidth: '4ch', textAlign: 'right' }}>{value} / 200</span>
    </div>
  );
}
```

- [ ] **Step 2: `ColorTab.jsx`**

```javascript
import { useState } from 'react';

const NAMED = [
  ['red', [255, 0, 0]], ['orange', [255, 100, 0]], ['yellow', [255, 220, 0]],
  ['green', [0, 200, 0]], ['cyan', [0, 200, 200]], ['blue', [0, 0, 255]],
  ['purple', [180, 0, 255]], ['pink', [255, 120, 180]], ['white', [255, 255, 255]],
  ['black', [0, 0, 0]],
];

const EMOJI = ['🔴', '🟢', '🔵', '🟠', '🟡', '🟣', '⚪', '⚫'];

function parseHex(h) {
  const s = h.replace('#', '');
  if (s.length === 3) return [0, 2, 4].map((i) => parseInt(s[i / 2] + s[i / 2], 16));
  if (s.length === 6) return [0, 2, 4].map((i) => parseInt(s.slice(i, i + 2), 16));
  return null;
}

export default function ColorTab({ onSend }) {
  const [hex, setHex] = useState('#ff7a00');

  const sendRgb = ([r, g, b]) => {
    onSend({ kind: 'color', color: { r, g, b } });
  };

  const sendHex = () => {
    const rgb = parseHex(hex);
    if (rgb) sendRgb(rgb);
  };

  return (
    <div style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
        {NAMED.map(([name, rgb]) => (
          <button key={name} onClick={() => sendRgb(rgb)}
            style={{ padding: '0.5rem 1rem', background: `rgb(${rgb.join(',')})`, color: '#000', border: '1px solid var(--border)' }}>
            {name}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem' }}>
        <label>Hex</label>
        <input value={hex} onChange={(e) => setHex(e.target.value)} style={{ padding: '0.4rem' }} />
        <span style={{ display: 'inline-block', width: '2rem', height: '1.5rem', background: hex, border: '1px solid var(--border)' }} />
        <button onClick={sendHex}>send</button>
      </div>
      <div style={{ display: 'flex', gap: '0.25rem' }}>
        {EMOJI.map((e) => (
          <button key={e} onClick={() => onSend({ kind: 'emoji-shortcut', emoji: e })} style={{ fontSize: '1.5rem' }}>{e}</button>
        ))}
      </div>
    </div>
  );
}
```

Note: the emoji shortcut buttons in this tab send a sentinel `{ kind: 'emoji-shortcut' }` which the API doesn't accept directly. The parent App converts that into the real Command via a client-side table. This keeps the tab pure (no API calls itself).

Actually, for the color emoji row specifically, they're always color commands — resolve on the client in `ColorTab` itself. Replace the EMOJI row with:

```javascript
const EMOJI_COLORS = [
  ['🔴', [255, 0, 0]], ['🟢', [0, 200, 0]], ['🔵', [0, 0, 255]],
  ['🟠', [255, 100, 0]], ['🟡', [255, 220, 0]], ['🟣', [180, 0, 255]],
  ['⚪', [255, 255, 255]], ['⚫', [0, 0, 0]],
];

// ...inside return, replace the EMOJI.map block with:
      <div style={{ display: 'flex', gap: '0.25rem' }}>
        {EMOJI_COLORS.map(([e, rgb]) => (
          <button key={e} onClick={() => sendRgb(rgb)} style={{ fontSize: '1.5rem' }}>{e}</button>
        ))}
      </div>
```

Use this corrected version.

- [ ] **Step 3: `PowerTab.jsx`**

```javascript
export default function PowerTab({ onSend }) {
  return (
    <div style={{ padding: '1rem', display: 'flex', gap: '1rem' }}>
      <button onClick={() => onSend({ kind: 'power', on: true })}
        style={{ padding: '1rem 2rem', fontSize: '1.1rem' }}>On</button>
      <button onClick={() => onSend({ kind: 'power', on: false })}
        style={{ padding: '1rem 2rem', fontSize: '1.1rem' }}>Off</button>
    </div>
  );
}
```

- [ ] **Step 4: Wire tabs + brightness into `App.jsx`**

Edit `apps/wrangler-ui/src/App.jsx`:

```javascript
import { useCallback, useEffect, useState } from 'react';
import DeviceSelector from './components/DeviceSelector.jsx';
import LiveState from './components/LiveState.jsx';
import ColorTab from './components/ColorTab.jsx';
import PowerTab from './components/PowerTab.jsx';
import BrightnessSlider from './components/BrightnessSlider.jsx';
import { api } from './api.js';

const STORAGE_KEY = 'wrangler.selectedMac';
const TABS = ['Color', 'Power'];

export default function App() {
  const [devices, setDevices] = useState([]);
  const [selectedMac, setSelectedMac] = useState(localStorage.getItem(STORAGE_KEY));
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('Color');

  const refreshDevices = useCallback(async () => {
    try {
      const { devices } = await api.listDevices();
      setDevices(devices);
      setError(null);
      if (devices.length && !devices.some((d) => d.mac === selectedMac)) {
        const mac = devices[0].mac;
        setSelectedMac(mac);
        localStorage.setItem(STORAGE_KEY, mac);
      }
    } catch (e) { setError(e.message); }
  }, [selectedMac]);

  useEffect(() => { refreshDevices(); }, [refreshDevices]);

  const sendCommand = async (command) => {
    if (!selectedMac) return;
    try {
      await api.sendCommand(selectedMac, command);
      setError(null);
    } catch (e) { setError(e.message); }
  };

  const sendBrightness = (level) => sendCommand({ kind: 'brightness', brightness: level });

  return (
    <div>
      <DeviceSelector
        devices={devices}
        selectedMac={selectedMac}
        onSelect={(mac) => { setSelectedMac(mac); localStorage.setItem(STORAGE_KEY, mac); }}
        onRescan={async () => { try { const { devices } = await api.rescan(); setDevices(devices); } catch (e) { setError(e.message); } }}
        onRenamed={refreshDevices}
      />
      {error && <div style={{ padding: '0.5rem 1rem', background: '#3a1212', color: '#ffd6d6' }}>{error}</div>}
      {selectedMac && <LiveState selectedMac={selectedMac} />}
      <nav style={{ padding: '0.5rem 1rem', display: 'flex', gap: '0.25rem', borderBottom: '1px solid var(--border)' }}>
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: '0.4rem 1rem', background: t === tab ? 'var(--accent)' : 'var(--panel)', color: t === tab ? '#000' : 'var(--fg)', border: '1px solid var(--border)' }}>
            {t}
          </button>
        ))}
      </nav>
      {tab === 'Color' && <ColorTab onSend={sendCommand} />}
      {tab === 'Power' && <PowerTab onSend={sendCommand} />}
      {selectedMac && <BrightnessSlider onCommit={sendBrightness} />}
    </div>
  );
}
```

- [ ] **Step 5: Lint + commit**

```bash
cd apps/wrangler-ui && npm run lint
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler-ui/src
git commit -m "feat(wrangler-ui): color tab, power tab, brightness slider"
```

---

## Task 14: Effect + Text + Preset + Emoji tabs

**Files:**
- Create: `apps/wrangler-ui/src/components/EffectTab.jsx`
- Create: `apps/wrangler-ui/src/components/TextTab.jsx`
- Create: `apps/wrangler-ui/src/components/PresetTab.jsx`
- Create: `apps/wrangler-ui/src/components/EmojiTab.jsx`
- Modify: `apps/wrangler-ui/src/App.jsx`

- [ ] **Step 1: `EffectTab.jsx`**

```javascript
import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function EffectTab({ onSend }) {
  const [effects, setEffects] = useState([]);
  const [name, setName] = useState('rainbow');
  const [speed, setSpeed] = useState(128);
  const [intensity, setIntensity] = useState(128);
  const [color, setColor] = useState('');

  useEffect(() => { api.listEffects().then((d) => setEffects(d.effects)).catch(() => {}); }, []);

  const send = () => {
    const cmd = { kind: 'effect', name, speed, intensity };
    if (color.trim()) {
      const hex = color.startsWith('#') ? color.slice(1) : color;
      if (hex.length === 6) {
        cmd.color = {
          r: parseInt(hex.slice(0, 2), 16),
          g: parseInt(hex.slice(2, 4), 16),
          b: parseInt(hex.slice(4, 6), 16),
        };
      }
    }
    onSend(cmd);
  };

  return (
    <div style={{ padding: '1rem', display: 'grid', gap: '0.75rem', maxWidth: '32rem' }}>
      <label>
        Effect:
        <select value={name} onChange={(e) => setName(e.target.value)} style={{ marginLeft: '0.5rem' }}>
          {effects.map((e) => (<option key={e} value={e}>{e}</option>))}
        </select>
      </label>
      <label>Speed ({speed}):
        <input type="range" min={0} max={255} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} style={{ width: '100%' }} />
      </label>
      <label>Intensity ({intensity}):
        <input type="range" min={0} max={255} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} style={{ width: '100%' }} />
      </label>
      <label>Color (#hex, optional):
        <input value={color} onChange={(e) => setColor(e.target.value)} placeholder="#ff7a00" />
      </label>
      <button onClick={send} style={{ padding: '0.6rem 1rem' }}>Fire effect 🔥</button>
    </div>
  );
}
```

- [ ] **Step 2: `TextTab.jsx`**

```javascript
import { useState } from 'react';

export default function TextTab({ onSend }) {
  const [text, setText] = useState('');
  const [color, setColor] = useState('#ff7a00');
  const [speed, setSpeed] = useState(128);

  const send = () => {
    if (!text.trim()) return;
    const hex = color.startsWith('#') ? color.slice(1) : color;
    const cmd = { kind: 'text', text, speed };
    if (hex.length === 6) {
      cmd.color = {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
      };
    }
    onSend(cmd);
  };

  return (
    <div style={{ padding: '1rem', display: 'grid', gap: '0.75rem', maxWidth: '32rem' }}>
      <label>Text ({text.length}/64):
        <input maxLength={64} value={text} onChange={(e) => setText(e.target.value)} style={{ width: '100%' }} />
      </label>
      <label>Color:
        <input value={color} onChange={(e) => setColor(e.target.value)} />
      </label>
      <label>Speed ({speed}):
        <input type="range" min={32} max={240} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} style={{ width: '100%' }} />
      </label>
      <button onClick={send} style={{ padding: '0.6rem 1rem' }}>Send text</button>
    </div>
  );
}
```

- [ ] **Step 3: `PresetTab.jsx`**

```javascript
import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function PresetTab({ onSend }) {
  const [presets, setPresets] = useState([]);
  useEffect(() => { api.listPresets().then((d) => setPresets(d.presets)).catch(() => {}); }, []);
  return (
    <div style={{ padding: '1rem', display: 'flex', gap: '0.75rem' }}>
      {presets.map((name) => (
        <button key={name} onClick={() => onSend({ kind: 'preset', name })}
          style={{ padding: '1rem 1.5rem', fontSize: '1rem' }}>{name}</button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: `EmojiTab.jsx`**

The emoji endpoint returns `{emoji: {"🔥": "fire", ...}}` — labels not Commands. So this tab either POSTs a special endpoint OR resolves emoji client-side. Since the API doesn't have an `/api/emoji/{glyph}/send` endpoint, mirror the CLI behavior: map common emoji to Commands right here in the UI.

```javascript
import { useEffect, useState } from 'react';
import { api } from '../api.js';

function resolveEmojiCommand(glyph) {
  const table = {
    '🔥': { kind: 'effect', name: 'fire' },
    '🌈': { kind: 'effect', name: 'rainbow' },
    '⚡': { kind: 'effect', name: 'sparkle', speed: 220 },
    '🎉': { kind: 'effect', name: 'fireworks' },
    '🐍': { kind: 'effect', name: 'matrix' },
    '❤️': { kind: 'color', color: { r: 255, g: 0, b: 0 } },
    '💙': { kind: 'color', color: { r: 0, g: 0, b: 255 } },
    '💚': { kind: 'color', color: { r: 0, g: 200, b: 0 } },
    '💜': { kind: 'color', color: { r: 180, g: 0, b: 255 } },
    '🧡': { kind: 'color', color: { r: 255, g: 100, b: 0 } },
    '🖤': { kind: 'power', on: false },
  };
  return table[glyph] || null;
}

export default function EmojiTab({ onSend }) {
  const [labels, setLabels] = useState({});
  useEffect(() => { api.listEmoji().then((d) => setLabels(d.emoji)).catch(() => {}); }, []);
  const glyphs = Object.keys(labels);
  return (
    <div style={{ padding: '1rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
      {glyphs.map((g) => {
        const cmd = resolveEmojiCommand(g);
        if (!cmd) return null;
        return (
          <button key={g} onClick={() => onSend(cmd)}
            style={{ padding: '0.6rem 1rem', fontSize: '1.1rem' }}
            title={labels[g]}>
            <span style={{ fontSize: '1.4rem' }}>{g}</span> <small style={{ color: 'var(--muted)' }}>{labels[g]}</small>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: Register the tabs in `App.jsx`**

In `App.jsx`, update imports and `TABS`:

```javascript
import EffectTab from './components/EffectTab.jsx';
import TextTab from './components/TextTab.jsx';
import PresetTab from './components/PresetTab.jsx';
import EmojiTab from './components/EmojiTab.jsx';

// ...
const TABS = ['Color', 'Effect', 'Text', 'Preset', 'Emoji', 'Power'];
```

And render them:

```javascript
      {tab === 'Color' && <ColorTab onSend={sendCommand} />}
      {tab === 'Effect' && <EffectTab onSend={sendCommand} />}
      {tab === 'Text' && <TextTab onSend={sendCommand} />}
      {tab === 'Preset' && <PresetTab onSend={sendCommand} />}
      {tab === 'Emoji' && <EmojiTab onSend={sendCommand} />}
      {tab === 'Power' && <PowerTab onSend={sendCommand} />}
```

- [ ] **Step 6: Lint + commit**

```bash
cd apps/wrangler-ui && npm run lint
cd /home/jvogel/src/personal/wrangled-dashboard
git add apps/wrangler-ui/src
git commit -m "feat(wrangler-ui): effect/text/preset/emoji tabs"
```

---

## Task 15: build.sh / dev.sh / CLAUDE.md updates

**Files:**
- Modify: `build.sh`
- Modify: `dev.sh`
- Modify: `apps/wrangler/CLAUDE.md`

- [ ] **Step 1: Update `build.sh`**

In `/home/jvogel/src/personal/wrangled-dashboard/build.sh`, add these two blocks (after the `apps/wrangler` uv sync but before the lint step):

```bash
echo "=== node: apps/wrangler-ui ==="
( cd "$ROOT/apps/wrangler-ui" && npm install && npm run build )
```

- [ ] **Step 2: Update `dev.sh`**

Replace `dev.sh` with:

```bash
#!/usr/bin/env bash
# Start all dev processes for the monorepo.
# Needs: wrangler FastAPI (8501), wrangler-ui Vite (8511), dashboard Vite (8510).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

command -v uv >/dev/null 2>&1 || { echo "uv is required"; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required"; exit 1; }

cleanup() {
  echo "shutting down..."
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "starting wrangler FastAPI on :8501"
( cd "$ROOT/apps/wrangler" && uv run wrangler serve --host 127.0.0.1 --port 8501 ) &

echo "starting wrangler-ui Vite on :8511"
( cd "$ROOT/apps/wrangler-ui" && npm run dev ) &

echo "starting dashboard Vite on :8510"
( cd "$ROOT/apps/dashboard" && npm run dev ) &

echo ""
echo "  wrangler-ui:  http://localhost:8511"
echo "  dashboard:    http://localhost:5173 (default vite port — adjust in dashboard's vite.config.js if you want 8510)"
echo "  api:          http://localhost:8501/healthz"
echo ""

wait
```

- [ ] **Step 3: Update `apps/wrangler/CLAUDE.md`**

Append to `apps/wrangler/CLAUDE.md` after the existing "Run locally" block:

```markdown

### Serve the web UI + API

    uv run wrangler serve              # FastAPI + built UI on :8501
    uv run wrangler serve --host 0.0.0.0 --port 8501
    uv run wrangler serve --no-initial-scan

Then open `http://localhost:8501/` in a browser.

For development with live reload of the UI, run the Vite dev server too:

    cd ../wrangler-ui && npm run dev    # :8511 with /api/* proxied to :8501
```

Also update the "Key modules" bullet list to include:

```markdown
- `server/app.py` — FastAPI factory (CORS, static UI mount, healthz)
- `server/devices.py` — /api/devices/* + /api/scan routes
- `server/metadata.py` — /api/effects + /api/presets + /api/emoji
- `server/registry.py` — in-memory device map with scan lock
- `server/wled_client.py` — WLED read + cfg HTTP helpers
```

- [ ] **Step 4: Run `./lint.sh` and `./build.sh` to confirm nothing broke**

```bash
./lint.sh
./build.sh
```

Expected: both succeed. If anything is off, fix inline.

- [ ] **Step 5: Commit**

```bash
git add build.sh dev.sh apps/wrangler/CLAUDE.md
git commit -m "chore: wire wrangler-ui into build.sh + dev.sh; update CLAUDE.md"
```

---

## Task 16: End-to-end live verification

Manual, against `10.0.6.207`. No commits; this is acceptance.

- [ ] **Step 1: Build + serve**

```bash
./build.sh
cd apps/wrangler
uv run wrangler serve
```

- [ ] **Step 2: Open browser**

Open `http://localhost:8501/` in a browser on the same LAN.

Expected:

- Header shows "Wrangler" + device dropdown populated with the matrix.
- "Live state" panel shows ON/off, brightness, fx N, and a colored swatch. Updates every 2s if you change state elsewhere.
- Clicking color chips changes the matrix immediately; the color swatch in Live State updates within 2s.
- Clicking a preset (pytexas) turns on orange + starts scrolling "PyTexas 2026".
- Clicking 🔥 in Emoji tab runs firenoise.
- Sending text "Hello Swap" scrolls "Hello Swap".
- Brightness slider release changes brightness and Live State reflects it.
- Power On/Off toggles the matrix.
- Rename: click ✏️, type "Stage-Left", press Enter. Device dropdown and header label both update.
- Rescan: click button; spinner appears; device list refreshes.
- Pull the Pi's power / disconnect WLED from LAN: Live State shows "Matrix unreachable" banner. Plug back in + rescan restores.

- [ ] **Step 3: Confirm CLI still works unchanged**

```bash
uv run wrangler scan
uv run wrangler send --ip 10.0.6.207 color blue --brightness 1
```

Expected: both still work, matrix responds.

- [ ] **Step 4: Verify all tests still pass**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
./build.sh
```

Expected: "build ok".

---

## Self-Review Notes

- **Spec coverage:**
  - FastAPI factory + /healthz → T1.
  - Registry with scan lock → T2.
  - wled_client (state + rename) → T3.
  - /api/devices (list + get) + /api/scan → T4.
  - /api/devices/{mac}/state → T5.
  - /api/devices/{mac}/commands → T6.
  - /api/devices/{mac}/name → T7.
  - /api/effects + /api/presets + /api/emoji → T8.
  - `wrangler serve` CLI → T9.
  - Scaffold wrangler-ui (Vite + React + ESLint + proxy) → T10.
  - Device selector + rename + rescan → T11.
  - LiveState polling → T12.
  - Brightness + Color + Power → T13.
  - Effect + Text + Preset + Emoji → T14.
  - build.sh + dev.sh + CLAUDE.md → T15.
  - Live verification → T16.
- **Placeholder scan:** none; every step has concrete code + commands.
- **Type consistency:** Command body kinds (`"color"`, `"brightness"`, `"effect"`, `"text"`, `"preset"`, `"power"`) match the pydantic discriminator in `wrangled_contracts`. `Registry.scan(opts)`, `Registry.get(mac)`, `Registry.put(device)`, `Registry.all()` consistent across server tests and endpoints. Fetch wrappers in `api.js` use the exact endpoint paths the FastAPI router exposes.

---

## Scope Boundary

This plan does NOT include:

- Tests for the UI (no Vitest/jsdom).
- WebSocket connections to an upstream `api` hub (that's the next milestone).
- Auth.
- Multi-device fanout commands.
- Server-side persistence of any kind (no DB).
- A "favorites" or "primary device" server-side concept (localStorage only).
