# WrangLED Monorepo + Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the WrangLED monorepo (dashboard + api + wrangler-ui + wrangler + contracts), with the first functional component — the `wrangler` WLED network scanner — fully implemented and tested against real hardware at `10.0.6.207`.

**Architecture:** Python apps use `uv` + pydantic v2 + FastAPI (where applicable) + Ruff-max linting. JS apps use Vite + ESLint-max. Shared pydantic models live in `packages/contracts/`. Scanner is structured as an importable async library (`wrangler.scanner.scan()`) with a thin CLI wrapper, using mDNS-first discovery with IP-sweep fallback.

**Tech Stack:** Python 3.11+, uv, httpx, zeroconf, pydantic v2, pydantic-settings, pytest, pytest-asyncio, respx. Vite/React + ESLint flat config. Ruff for Python lint+format. Prettier for JS.

---

## File Structure

```
wrangled-dashboard/
├── CLAUDE.md                       # monorepo conventions (ports, scripts, linting)
├── ruff.toml                       # shared Python lint config
├── lint.sh                         # run all linters
├── build.sh                        # install + build + lint + test
├── dev.sh                          # start all dev processes concurrently
├── .gitignore                      # augmented for python
├── .github/workflows/deploy.yml    # updated: dashboard moved to apps/dashboard/
├── apps/
│   ├── dashboard/                  # moved here from repo root
│   │   ├── CLAUDE.md
│   │   ├── package.json, vite.config.js, index.html
│   │   ├── eslint.config.js
│   │   ├── src/, public/
│   ├── api/
│   │   └── CLAUDE.md               # placeholder, "not yet implemented"
│   ├── wrangler-ui/
│   │   └── CLAUDE.md               # placeholder
│   └── wrangler/
│       ├── CLAUDE.md
│       ├── pyproject.toml
│       ├── src/wrangler/
│       │   ├── __init__.py
│       │   ├── __main__.py         # `python -m wrangler`
│       │   ├── cli.py              # argparse, `scan` subcommand
│       │   ├── settings.py         # pydantic-settings
│       │   └── scanner/
│       │       ├── __init__.py     # public: scan(), ScanOptions
│       │       ├── mdns.py         # zeroconf
│       │       ├── sweep.py        # IP range sweep
│       │       ├── probe.py        # GET /json/info → WledDevice
│       │       └── netinfo.py      # subnet autodetect
│       └── tests/
│           ├── conftest.py
│           ├── fixtures/wled_info_v0_15.json
│           ├── test_probe.py
│           ├── test_netinfo.py
│           ├── test_sweep.py
│           ├── test_mdns.py
│           ├── test_scan_integration.py
│           ├── test_cli.py
│           └── test_live.py        # opt-in, @pytest.mark.live
├── packages/
│   └── contracts/
│       ├── CLAUDE.md
│       ├── pyproject.toml
│       └── src/wrangled_contracts/
│           ├── __init__.py
│           └── wled.py             # WledMatrix, WledDevice
├── infra/pi/
│   └── CLAUDE.md                   # placeholder
└── docs/superpowers/{specs,plans}/
```

---

## Task 1: Relocate existing dashboard into `apps/dashboard/`

**Files:**
- Move: `index.html`, `package.json`, `package-lock.json`, `vite.config.js`, `eslint.config.js`, `original_index.html`, `src/`, `public/` → `apps/dashboard/`
- Modify: `.github/workflows/deploy.yml`
- Create: `apps/api/.gitkeep`, `apps/wrangler/.gitkeep`, `apps/wrangler-ui/.gitkeep`, `packages/contracts/.gitkeep`, `infra/pi/.gitkeep`

- [ ] **Step 1: Create the monorepo directory skeleton**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
mkdir -p apps/dashboard apps/api apps/wrangler apps/wrangler-ui packages/contracts infra/pi
```

- [ ] **Step 2: Move existing dashboard files with git mv**

```bash
git mv index.html package.json package-lock.json vite.config.js eslint.config.js original_index.html src public apps/dashboard/
```

- [ ] **Step 3: Verify the dashboard still builds**

```bash
cd apps/dashboard && npm install && npm run build
```
Expected: clean build, `apps/dashboard/dist/` produced.

- [ ] **Step 4: Update the GitHub Pages workflow to the new path**

Replace `.github/workflows/deploy.yml` with:

```yaml
name: Deploy static content to Pages

on:
  push:
    branches: ['main', 'master']
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: 'pages'
  cancel-in-progress: true

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/dashboard
    steps:
      - name: Checkout
        uses: actions/checkout@v6
      - name: Set up Node
        uses: actions/setup-node@v6
        with:
          node-version: lts/*
          cache: 'npm'
          cache-dependency-path: apps/dashboard/package-lock.json
      - name: Install dependencies
        run: npm install
      - name: Build
        run: npm run build
      - name: Setup Pages
        uses: actions/configure-pages@v6
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v4
        with:
          path: ./apps/dashboard/dist
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v5
```

- [ ] **Step 5: Add .gitkeep files so empty dirs are tracked**

```bash
touch apps/api/.gitkeep apps/wrangler/.gitkeep apps/wrangler-ui/.gitkeep packages/contracts/.gitkeep infra/pi/.gitkeep
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: relocate dashboard into apps/dashboard monorepo layout"
```

---

## Task 2: Augment `.gitignore` for Python

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append Python / uv / pytest entries**

Append to `.gitignore`:

```gitignore

# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/

# uv
uv.lock
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: extend .gitignore for Python toolchain"
```

---

## Task 3: Shared Ruff config at repo root

**Files:**
- Create: `ruff.toml`

- [ ] **Step 1: Write the root ruff config**

`ruff.toml`:

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["ALL"]
ignore = [
    "D",       # pydocstyle: opt in later
    "ANN101",  # self annotation redundant
    "ANN102",  # cls annotation redundant
    "COM812",  # trailing comma — conflicts with formatter
    "ISC001",  # implicit string concat — conflicts with formatter
    "TD002",   # allow TODOs without author
    "TD003",   # allow TODOs without issue link
    "FIX002",  # allow TODO comments in code
]

[lint.mccabe]
max-complexity = 15

[lint.per-file-ignores]
"**/tests/**" = ["S101", "PLR2004", "ANN", "D"]
"**/__main__.py" = ["T201"]       # print allowed in CLI entry
"**/cli.py" = ["T201"]            # print allowed in CLI

[lint.pydocstyle]
convention = "google"

[format]
quote-style = "double"
indent-style = "space"
```

- [ ] **Step 2: Commit**

```bash
git add ruff.toml
git commit -m "chore: add shared Ruff config at repo root"
```

---

## Task 4: Root and per-module CLAUDE.md files

**Files:**
- Create: `CLAUDE.md`, `apps/dashboard/CLAUDE.md`, `apps/api/CLAUDE.md`, `apps/wrangler-ui/CLAUDE.md`, `apps/wrangler/CLAUDE.md`, `packages/contracts/CLAUDE.md`, `infra/pi/CLAUDE.md`

- [ ] **Step 1: Write root `CLAUDE.md`**

```markdown
# WrangLED — Monorepo Conventions

## Layout
- `apps/dashboard/` — Vite/React "Command Center" UI. Built static assets served by `apps/api/` in prod; deployed standalone to GitHub Pages for the public build log.
- `apps/api/` — FastAPI hub. Serves dashboard static, REST, WebSocket hub, optional Discord gateway.
- `apps/wrangler-ui/` — Vite/React local config panel. Built static assets served by `apps/wrangler/`.
- `apps/wrangler/` — FastAPI + agent running on the Raspberry Pi. Scans for WLEDs, holds WS to api, pushes to WLEDs.
- `packages/contracts/` — Shared pydantic v2 models imported by every Python app.
- `infra/pi/` — systemd units, install scripts for Pi deployment.

## Ports
| Service                | Port  |
|------------------------|-------|
| `api` FastAPI          | 8500  |
| `wrangler` FastAPI     | 8501  |
| `dashboard` Vite dev   | 8510  |
| `wrangler-ui` Vite dev | 8511  |

Vite dev servers proxy `/api/*` and `/ws` to their paired FastAPI so the React code is environment-agnostic.

## Scripts
- `./build.sh` — install all deps, build UIs, lint, test.
- `./lint.sh [--fix]` — run Ruff + ESLint across the repo.
- `./dev.sh` — start all dev processes concurrently.

## Python
- Python 3.11+ via `uv`. Each app owns its own `pyproject.toml` and `.venv`.
- Ruff config lives at repo root (`ruff.toml`). Every app's `pyproject.toml` uses `extend = "../../ruff.toml"`.
- Tests via pytest. Models live in `packages/contracts/` and are imported as `wrangled_contracts`.

## JS/TS
- Vite + React, ESLint flat config maxed (strict TS-style rules, a11y, import order, complexity ≤ 15). Prettier for formatting.

## Design principles
- `api` is the command hub. Interfaces (Discord, dashboard, CLIs) produce Commands into it.
- `wrangler` is outbound-only. It dials `api`; no inbound ports exposed beyond the local LAN config UI.
- Optional interfaces: Discord gateway only if `DISCORD_BOT_TOKEN` is set; `wrangler` connects only if `WRANGLED_API_URL` is set.
- Shared pydantic `contracts/` prevents schema drift between producer and consumer.
```

- [ ] **Step 2: Write `apps/dashboard/CLAUDE.md`**

```markdown
# apps/dashboard — Command Center UI

## Purpose
Vite/React dashboard showing the PyTexas WrangLED build log, hardware tracking, architecture, boot order, team. Deployed standalone to GitHub Pages (public log) and also served as static assets by `apps/api/` in the live control context.

## Run locally
```bash
cd apps/dashboard
npm install
npm run dev   # Vite on http://localhost:8510 (see vite.config.js when updated)
```

## Build
```bash
npm run build   # produces apps/dashboard/dist/
```

## Key files
- `src/App.jsx` — single-file React dashboard
- `vite.config.js` — Vite config (dev port + proxy to api at :8500 added in a later milestone)
- `index.html` — Vite entry

## Gotchas
- The GitHub Pages deploy in `.github/workflows/deploy.yml` cds into this directory. Keep the `package.json` build script named `build`.
```

- [ ] **Step 3: Write `apps/api/CLAUDE.md`**

```markdown
# apps/api — FastAPI Hub

## Status
**Not yet implemented.** Placeholder for milestone 1.

## Intended purpose
FastAPI process that:
- Serves `apps/dashboard/dist/` as static files on `/`.
- Exposes REST under `/api/*`.
- Exposes a WebSocket hub under `/ws` for dashboard browsers and `wrangler` agents.
- Starts a `discord.py` gateway task if `DISCORD_BOT_TOKEN` is set.

## Port
8500.

## Downstream
- Consumes Commands from Discord / dashboard.
- Pushes Commands to `wrangler` over WebSocket.
```

- [ ] **Step 4: Write `apps/wrangler-ui/CLAUDE.md`**

```markdown
# apps/wrangler-ui — Pi Config Panel

## Status
**Not yet implemented.** Placeholder for milestone 1.

## Intended purpose
Small Vite/React UI served by `apps/wrangler/` on port 8501. Shows discovered WLEDs, connection status to `api`, config for which WLED is "the matrix", and a manual test-fire button.
```

- [ ] **Step 5: Write `apps/wrangler/CLAUDE.md`**

```markdown
# apps/wrangler — Pi Agent

## Purpose
Runs on the Raspberry Pi. Responsible for:
- Discovering WLEDs on the LAN (mDNS + sweep).
- Holding a WebSocket connection out to `apps/api` (future milestone).
- Pushing commands to WLEDs via their HTTP JSON API (future milestone).
- Serving `apps/wrangler-ui/dist/` as a local config panel (future milestone).

**Milestone 1 scope:** scanner only (discovery + CLI).

## Run locally
```bash
cd apps/wrangler
uv sync
uv run wrangler scan             # mDNS-first with sweep fallback
uv run wrangler scan --sweep     # force sweep in addition to mDNS
uv run wrangler scan --no-mdns   # sweep only
uv run wrangler scan --json      # JSON output
```

## Test
```bash
uv run pytest                    # unit tests
uv run pytest -m live            # opt-in live test against 10.0.6.207
```

## Key modules
- `scanner/mdns.py` — zeroconf-based discovery
- `scanner/sweep.py` — concurrent HTTP probe across a subnet
- `scanner/probe.py` — parses `/json/info` into a `WledDevice`
- `scanner/netinfo.py` — detects the local `/24`
- `scanner/__init__.py` — public `scan(opts)` orchestrator
- `cli.py` — argparse CLI

## Gotchas
- Some networks block mDNS. The scanner falls back to sweep when mDNS returns zero candidates.
- The probe timeout is 2s per device; 32-way concurrency by default.
```

- [ ] **Step 6: Write `packages/contracts/CLAUDE.md`**

```markdown
# packages/contracts — Shared Pydantic Models

## Purpose
Pydantic v2 models shared by every Python app in the monorepo. Prevents schema drift between producer and consumer (e.g., `wrangler` discovers a `WledDevice`, `api` consumes it).

## Install in a sibling app
In the sibling's `pyproject.toml`:

```toml
[project]
dependencies = [
    "wrangled-contracts",
]

[tool.uv.sources]
wrangled-contracts = { path = "../../packages/contracts", editable = true }
```

Then `uv sync` in the sibling app.

## Current models (milestone 1)
- `WledMatrix` — width / height of a WLED 2D matrix.
- `WledDevice` — a discovered WLED device (ip, mac, name, version, led_count, matrix, etc.).

## Future additions
- `Command` payload shape
- `WledState`
- Auth token envelopes
```

- [ ] **Step 7: Write `infra/pi/CLAUDE.md`**

```markdown
# infra/pi — Raspberry Pi Deployment Assets

## Status
**Not yet implemented.** Placeholder for milestone 1.

## Intended contents
- `wrangler.service` — systemd unit running `uv run wrangler run` on boot
- `install.sh` — first-time setup (apt prereqs, uv install, clone, enable service)
- `update.sh` — pull + restart
```

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md apps/*/CLAUDE.md packages/*/CLAUDE.md infra/pi/CLAUDE.md
git rm apps/api/.gitkeep apps/wrangler-ui/.gitkeep infra/pi/.gitkeep
git commit -m "docs: add root and per-module CLAUDE.md conventions"
```

---

## Task 5: `packages/contracts` — Python package skeleton

**Files:**
- Create: `packages/contracts/pyproject.toml`
- Create: `packages/contracts/src/wrangled_contracts/__init__.py`
- Delete: `packages/contracts/.gitkeep`

- [ ] **Step 1: Write `packages/contracts/pyproject.toml`**

```toml
[project]
name = "wrangled-contracts"
version = "0.1.0"
description = "Shared pydantic models for the WrangLED monorepo"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/wrangled_contracts"]

[tool.ruff]
extend = "../../ruff.toml"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.5",
]
```

- [ ] **Step 2: Create the package module**

`packages/contracts/src/wrangled_contracts/__init__.py`:

```python
"""Shared pydantic models for the WrangLED monorepo."""

from wrangled_contracts.wled import WledDevice, WledMatrix

__all__ = ["WledDevice", "WledMatrix"]
```

- [ ] **Step 3: Verify uv can resolve and install the empty package**

```bash
cd packages/contracts
uv sync
```
Expected: `.venv/` created, no errors.

- [ ] **Step 4: Remove the .gitkeep and commit the skeleton**

```bash
git rm packages/contracts/.gitkeep
git add packages/contracts/pyproject.toml packages/contracts/src
git commit -m "feat(contracts): scaffold wrangled-contracts package"
```

---

## Task 6: TDD — `WledMatrix` model

**Files:**
- Create: `packages/contracts/tests/__init__.py`, `packages/contracts/tests/test_wled.py`
- Create: `packages/contracts/src/wrangled_contracts/wled.py`

- [ ] **Step 1: Write failing test for `WledMatrix`**

`packages/contracts/tests/test_wled.py`:

```python
"""Tests for wrangled_contracts.wled."""

import pytest
from pydantic import ValidationError

from wrangled_contracts import WledMatrix


def test_wled_matrix_accepts_positive_dimensions() -> None:
    matrix = WledMatrix(width=16, height=16)
    assert matrix.width == 16
    assert matrix.height == 16


def test_wled_matrix_rejects_zero_width() -> None:
    with pytest.raises(ValidationError):
        WledMatrix(width=0, height=16)


def test_wled_matrix_rejects_negative_height() -> None:
    with pytest.raises(ValidationError):
        WledMatrix(width=16, height=-1)
```

`packages/contracts/tests/__init__.py`: empty file.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/contracts
uv run pytest tests/test_wled.py -v
```
Expected: ImportError — `WledMatrix` does not exist.

- [ ] **Step 3: Implement minimal `WledMatrix`**

`packages/contracts/src/wrangled_contracts/wled.py`:

```python
"""Pydantic models describing WLED devices and their topology."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WledMatrix(BaseModel):
    """Dimensions of a WLED 2D matrix, in LED count."""

    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0, description="Columns of LEDs.")
    height: int = Field(gt=0, description="Rows of LEDs.")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_wled.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/src/wrangled_contracts/wled.py packages/contracts/tests
git commit -m "feat(contracts): add WledMatrix model with dimension validation"
```

---

## Task 7: TDD — `WledDevice` model

**Files:**
- Modify: `packages/contracts/tests/test_wled.py`
- Modify: `packages/contracts/src/wrangled_contracts/wled.py`

- [ ] **Step 1: Append failing tests for `WledDevice`**

Append to `packages/contracts/tests/test_wled.py`:

```python
from datetime import UTC, datetime
from ipaddress import IPv4Address

from wrangled_contracts import WledDevice


def _base_device_kwargs() -> dict:
    return {
        "ip": IPv4Address("10.0.6.207"),
        "name": "WLED-Matrix",
        "mac": "aa:bb:cc:dd:ee:ff",
        "version": "0.15.0",
        "led_count": 256,
        "matrix": WledMatrix(width=16, height=16),
        "udp_port": 21324,
        "raw_info": {"leds": {"count": 256}},
        "discovered_via": "mdns",
        "discovered_at": datetime(2026, 4, 13, 12, 0, tzinfo=UTC),
    }


def test_wled_device_roundtrip() -> None:
    device = WledDevice(**_base_device_kwargs())
    assert device.ip == IPv4Address("10.0.6.207")
    assert device.matrix is not None
    assert device.matrix.width == 16


def test_wled_device_without_matrix_is_allowed() -> None:
    kwargs = _base_device_kwargs()
    kwargs["matrix"] = None
    kwargs["led_count"] = 60
    device = WledDevice(**kwargs)
    assert device.matrix is None


def test_wled_device_mac_is_lowercased() -> None:
    kwargs = _base_device_kwargs()
    kwargs["mac"] = "AA:BB:CC:DD:EE:FF"
    device = WledDevice(**kwargs)
    assert device.mac == "aa:bb:cc:dd:ee:ff"


def test_wled_device_mac_without_colons_is_canonicalized() -> None:
    kwargs = _base_device_kwargs()
    kwargs["mac"] = "AABBCCDDEEFF"
    device = WledDevice(**kwargs)
    assert device.mac == "aa:bb:cc:dd:ee:ff"


def test_wled_device_rejects_invalid_mac() -> None:
    kwargs = _base_device_kwargs()
    kwargs["mac"] = "not-a-mac"
    with pytest.raises(ValidationError):
        WledDevice(**kwargs)


def test_wled_device_discovered_via_is_constrained() -> None:
    kwargs = _base_device_kwargs()
    kwargs["discovered_via"] = "smoke-signal"
    with pytest.raises(ValidationError):
        WledDevice(**kwargs)
```

- [ ] **Step 2: Run test to verify they fail**

```bash
uv run pytest tests/test_wled.py -v
```
Expected: ImportError — `WledDevice` not defined.

- [ ] **Step 3: Implement `WledDevice`**

Append to `packages/contracts/src/wrangled_contracts/wled.py`:

```python
import re
from datetime import datetime
from ipaddress import IPv4Address
from typing import Literal

from pydantic import field_validator

_MAC_CLEAN_RE = re.compile(r"[^0-9a-fA-F]")
_MAC_HEX_RE = re.compile(r"^[0-9a-f]{12}$")


class WledDevice(BaseModel):
    """A WLED device discovered on the local network."""

    model_config = ConfigDict(frozen=False)

    ip: IPv4Address
    name: str
    mac: str = Field(description="Canonical lowercase colon-separated MAC.")
    version: str
    led_count: int = Field(gt=0)
    matrix: WledMatrix | None = None
    udp_port: int | None = None
    raw_info: dict = Field(default_factory=dict, repr=False, exclude=True)
    discovered_via: Literal["mdns", "sweep"]
    discovered_at: datetime

    @field_validator("mac", mode="before")
    @classmethod
    def _canonicalize_mac(cls, value: object) -> str:
        if not isinstance(value, str):
            msg = "mac must be a string"
            raise TypeError(msg)
        cleaned = _MAC_CLEAN_RE.sub("", value).lower()
        if not _MAC_HEX_RE.match(cleaned):
            msg = f"invalid MAC address: {value!r}"
            raise ValueError(msg)
        return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_wled.py -v
```
Expected: all 9 tests pass.

- [ ] **Step 5: Lint the package**

```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: both pass clean. If `ruff check` reports complaints, run `uv run ruff check --fix .` and re-run.

- [ ] **Step 6: Commit**

```bash
git add packages/contracts
git commit -m "feat(contracts): add WledDevice model with MAC canonicalization"
```

---

## Task 8: `apps/wrangler` — Python package skeleton

**Files:**
- Create: `apps/wrangler/pyproject.toml`
- Create: `apps/wrangler/src/wrangler/__init__.py`
- Create: `apps/wrangler/src/wrangler/settings.py`
- Delete: `apps/wrangler/.gitkeep`

- [ ] **Step 1: Write `apps/wrangler/pyproject.toml`**

```toml
[project]
name = "wrangler"
version = "0.1.0"
description = "WrangLED Pi-side agent: WLED discovery + control"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "zeroconf>=0.132",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "wrangled-contracts",
]

[project.scripts]
wrangler = "wrangler.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/wrangler"]

[tool.uv.sources]
wrangled-contracts = { path = "../../packages/contracts", editable = true }

[tool.ruff]
extend = "../../ruff.toml"

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "live: hits a real WLED on the LAN (opt-in, skipped by default)",
]
addopts = "-m 'not live'"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "ruff>=0.5",
]
```

- [ ] **Step 2: Create the package modules**

`apps/wrangler/src/wrangler/__init__.py`:

```python
"""WrangLED Pi-side agent."""

__version__ = "0.1.0"
```

`apps/wrangler/src/wrangler/settings.py`:

```python
"""Runtime settings loaded from environment."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WranglerSettings(BaseSettings):
    """Environment-driven configuration for the wrangler agent."""

    model_config = SettingsConfigDict(env_prefix="WRANGLED_", env_file=".env", extra="ignore")

    api_url: str | None = None
    mdns_timeout_seconds: float = 3.0
    probe_timeout_seconds: float = 2.0
    probe_concurrency: int = 32
```

- [ ] **Step 3: Verify uv can install**

```bash
cd apps/wrangler
uv sync
```
Expected: resolves, installs contracts from the editable local path, creates `.venv/`.

- [ ] **Step 4: Verify the package imports**

```bash
uv run python -c "import wrangler; from wrangled_contracts import WledDevice; print(wrangler.__version__)"
```
Expected: prints `0.1.0`.

- [ ] **Step 5: Commit**

```bash
git rm apps/wrangler/.gitkeep
git add apps/wrangler/pyproject.toml apps/wrangler/src
git commit -m "feat(wrangler): scaffold wrangler package with contracts dep"
```

---

## Task 9: TDD — `scanner/probe.py` (parse /json/info into WledDevice)

**Files:**
- Create: `apps/wrangler/tests/__init__.py`, `apps/wrangler/tests/conftest.py`
- Create: `apps/wrangler/tests/fixtures/wled_info_v0_15.json`
- Create: `apps/wrangler/tests/test_probe.py`
- Create: `apps/wrangler/src/wrangler/scanner/__init__.py`
- Create: `apps/wrangler/src/wrangler/scanner/probe.py`

- [ ] **Step 1: Create the fixture file**

`apps/wrangler/tests/fixtures/wled_info_v0_15.json`:

```json
{
  "ver": "0.15.0",
  "vid": 2406030,
  "leds": {
    "count": 256,
    "rgbw": false,
    "wv": 0,
    "cct": 0,
    "pwr": 0,
    "fps": 60,
    "maxpwr": 0,
    "maxseg": 32,
    "matrix": { "w": 16, "h": 16 },
    "seglc": [0],
    "lc": 1
  },
  "name": "WLED-Matrix",
  "udpport": 21324,
  "live": false,
  "liveseg": -1,
  "lm": "",
  "lip": "",
  "ws": -1,
  "fxcount": 187,
  "palcount": 71,
  "wifi": { "bssid": "xx", "rssi": -52, "signal": 100, "channel": 6 },
  "fs": { "u": 16, "t": 983, "pmt": 0 },
  "ndc": -1,
  "arch": "esp32",
  "core": "v4.4.2",
  "clock": 240,
  "flash": 4,
  "lwip": 0,
  "freeheap": 180020,
  "uptime": 42,
  "time": "",
  "opt": 79,
  "brand": "WLED",
  "product": "FOSS",
  "mac": "AABBCCDDEEFF",
  "ip": "10.0.6.207"
}
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
"""Shared pytest fixtures for wrangler tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def wled_info_v0_15() -> dict:
    return json.loads((FIXTURES / "wled_info_v0_15.json").read_text())
```

`apps/wrangler/tests/__init__.py`: empty.

- [ ] **Step 3: Write failing tests for probe**

`apps/wrangler/tests/test_probe.py`:

```python
"""Tests for wrangler.scanner.probe."""

from __future__ import annotations

from ipaddress import IPv4Address

import httpx
import pytest
import respx

from wrangler.scanner.probe import probe_device


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_parses_v0_15_info(wled_info_v0_15: dict) -> None:
    respx.get("http://10.0.6.207/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.207"), source="mdns")

    assert device is not None
    assert device.name == "WLED-Matrix"
    assert device.mac == "aa:bb:cc:dd:ee:ff"
    assert device.version == "0.15.0"
    assert device.led_count == 256
    assert device.matrix is not None
    assert device.matrix.width == 16
    assert device.matrix.height == 16
    assert device.udp_port == 21324
    assert device.discovered_via == "mdns"


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_returns_none_on_timeout() -> None:
    respx.get("http://10.0.6.99/json/info").mock(side_effect=httpx.ReadTimeout)
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.99"), source="sweep")
    assert device is None


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_returns_none_on_non_200() -> None:
    respx.get("http://10.0.6.50/json/info").mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.50"), source="sweep")
    assert device is None


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_returns_none_on_non_wled_json() -> None:
    respx.get("http://10.0.6.42/json/info").mock(
        return_value=httpx.Response(200, json={"hello": "router"}),
    )
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.42"), source="sweep")
    assert device is None


@pytest.mark.asyncio
@respx.mock
async def test_probe_device_handles_missing_matrix(wled_info_v0_15: dict) -> None:
    info = dict(wled_info_v0_15)
    info["leds"] = {**info["leds"]}
    info["leds"].pop("matrix")
    respx.get("http://10.0.6.10/json/info").mock(
        return_value=httpx.Response(200, json=info),
    )
    async with httpx.AsyncClient() as client:
        device = await probe_device(client, IPv4Address("10.0.6.10"), source="sweep")
    assert device is not None
    assert device.matrix is None
```

- [ ] **Step 4: Run to verify fail**

```bash
cd apps/wrangler
uv run pytest tests/test_probe.py -v
```
Expected: ImportError — `wrangler.scanner.probe` missing.

- [ ] **Step 5: Implement probe**

`apps/wrangler/src/wrangler/scanner/__init__.py`: empty for now, filled in later.

`apps/wrangler/src/wrangler/scanner/probe.py`:

```python
"""HTTP probe: fetch /json/info from a candidate IP and parse into a WledDevice."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import Literal

import httpx
from pydantic import ValidationError

from wrangled_contracts import WledDevice, WledMatrix

logger = logging.getLogger(__name__)


async def probe_device(
    client: httpx.AsyncClient,
    ip: IPv4Address,
    *,
    source: Literal["mdns", "sweep"],
    timeout: float = 2.0,
) -> WledDevice | None:
    """Probe a single IP. Return a WledDevice or None if not a responsive WLED."""
    url = f"http://{ip}/json/info"
    try:
        response = await client.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        logger.debug("probe %s: transport error: %s", ip, exc)
        return None

    if response.status_code != httpx.codes.OK:
        logger.debug("probe %s: status %s", ip, response.status_code)
        return None

    try:
        info = response.json()
    except ValueError:
        logger.debug("probe %s: non-JSON body", ip)
        return None

    if not isinstance(info, dict) or "leds" not in info or "mac" not in info:
        logger.debug("probe %s: not a WLED info response", ip)
        return None

    return _info_to_device(info, ip=ip, source=source)


def _info_to_device(
    info: dict,
    *,
    ip: IPv4Address,
    source: Literal["mdns", "sweep"],
) -> WledDevice | None:
    leds = info.get("leds") or {}
    matrix_raw = leds.get("matrix") if isinstance(leds, dict) else None
    matrix = None
    if isinstance(matrix_raw, dict) and "w" in matrix_raw and "h" in matrix_raw:
        try:
            matrix = WledMatrix(width=int(matrix_raw["w"]), height=int(matrix_raw["h"]))
        except (ValueError, ValidationError) as exc:
            logger.debug("probe %s: bad matrix: %s", ip, exc)
            matrix = None

    try:
        return WledDevice(
            ip=ip,
            name=str(info.get("name") or f"WLED-{ip}"),
            mac=str(info["mac"]),
            version=str(info.get("ver") or "unknown"),
            led_count=int(leds.get("count", 0)) or 1,
            matrix=matrix,
            udp_port=_maybe_int(info.get("udpport")),
            raw_info=info,
            discovered_via=source,
            discovered_at=datetime.now(tz=UTC),
        )
    except (ValueError, ValidationError) as exc:
        logger.debug("probe %s: failed validation: %s", ip, exc)
        return None


def _maybe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_probe.py -v
```
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add apps/wrangler/src/wrangler/scanner apps/wrangler/tests
git commit -m "feat(wrangler): probe /json/info and map to WledDevice"
```

---

## Task 10: TDD — `scanner/netinfo.py` (auto-detect local /24)

**Files:**
- Create: `apps/wrangler/tests/test_netinfo.py`
- Create: `apps/wrangler/src/wrangler/scanner/netinfo.py`

- [ ] **Step 1: Write failing test**

`apps/wrangler/tests/test_netinfo.py`:

```python
"""Tests for wrangler.scanner.netinfo."""

from __future__ import annotations

from ipaddress import IPv4Network
from unittest.mock import patch

import pytest

from wrangler.scanner.netinfo import NoSubnetDetectedError, detect_default_subnet


def test_detect_default_subnet_returns_24() -> None:
    fake_getaddrinfo = [(None, None, None, None, ("10.0.6.42", 0))]
    with (
        patch("wrangler.scanner.netinfo.socket.getaddrinfo", return_value=fake_getaddrinfo),
        patch("wrangler.scanner.netinfo._connect_probe", return_value="10.0.6.42"),
    ):
        subnet = detect_default_subnet()
    assert subnet == IPv4Network("10.0.6.0/24")


def test_detect_default_subnet_raises_on_failure() -> None:
    with patch("wrangler.scanner.netinfo._connect_probe", return_value=None):
        with pytest.raises(NoSubnetDetectedError):
            detect_default_subnet()
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_netinfo.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement**

`apps/wrangler/src/wrangler/scanner/netinfo.py`:

```python
"""Detect the local /24 subnet we should sweep."""

from __future__ import annotations

import socket
from ipaddress import IPv4Address, IPv4Network


class NoSubnetDetectedError(RuntimeError):
    """Raised when we cannot determine a local IPv4 subnet to sweep."""


def _connect_probe() -> str | None:
    """Use a connected UDP socket to learn which local IPv4 address we'd use outbound.

    Does not send packets; only asks the kernel for the source address that would
    be chosen when routing to a public address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addr: str = sock.getsockname()[0]
    except OSError:
        return None
    return addr


def detect_default_subnet() -> IPv4Network:
    """Return the /24 surrounding the kernel's default outbound IPv4 source address."""
    addr = _connect_probe()
    if not addr:
        msg = "could not detect a local IPv4 address; pass --subnet explicitly"
        raise NoSubnetDetectedError(msg)
    ip = IPv4Address(addr)
    return IPv4Network(f"{ip}/24", strict=False)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_netinfo.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/wrangler/src/wrangler/scanner/netinfo.py apps/wrangler/tests/test_netinfo.py
git commit -m "feat(wrangler): auto-detect local /24 via UDP-connect trick"
```

---

## Task 11: TDD — `scanner/sweep.py` (concurrent IP range probe)

**Files:**
- Create: `apps/wrangler/tests/test_sweep.py`
- Create: `apps/wrangler/src/wrangler/scanner/sweep.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_sweep.py`:

```python
"""Tests for wrangler.scanner.sweep."""

from __future__ import annotations

from ipaddress import IPv4Network

import httpx
import pytest
import respx

from wrangler.scanner.sweep import sweep_subnet


@pytest.mark.asyncio
@respx.mock
async def test_sweep_finds_single_wled(wled_info_v0_15: dict) -> None:
    respx.get("http://10.0.6.207/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    respx.get(url__regex=r"http://10\.0\.6\.\d+/json/info").mock(
        return_value=httpx.Response(404),
    )
    devices = await sweep_subnet(
        IPv4Network("10.0.6.0/29"),
        timeout=0.5,
        concurrency=8,
    )
    assert len(devices) == 1
    assert str(devices[0].ip) == "10.0.6.207"


@pytest.mark.asyncio
@respx.mock
async def test_sweep_dedupes_by_mac(wled_info_v0_15: dict) -> None:
    respx.get("http://10.0.6.1/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    # Second IP responds with the same MAC — should dedupe.
    respx.get("http://10.0.6.2/json/info").mock(
        return_value=httpx.Response(200, json=wled_info_v0_15),
    )
    respx.get(url__regex=r"http://10\.0\.6\.\d+/json/info").mock(
        return_value=httpx.Response(404),
    )
    devices = await sweep_subnet(IPv4Network("10.0.6.0/29"), timeout=0.5, concurrency=4)
    assert len(devices) == 1


@pytest.mark.asyncio
@respx.mock
async def test_sweep_handles_empty_subnet() -> None:
    respx.get(url__regex=r"http://10\.0\.6\.\d+/json/info").mock(
        return_value=httpx.Response(404),
    )
    devices = await sweep_subnet(IPv4Network("10.0.6.0/29"), timeout=0.5, concurrency=4)
    assert devices == []
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_sweep.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement sweep**

`apps/wrangler/src/wrangler/scanner/sweep.py`:

```python
"""Concurrent IP-range sweep: probe every host in a subnet for WLED."""

from __future__ import annotations

import asyncio
from ipaddress import IPv4Network
from typing import Iterable

import httpx

from wrangled_contracts import WledDevice

from wrangler.scanner.probe import probe_device


async def sweep_subnet(
    subnet: IPv4Network,
    *,
    timeout: float = 2.0,
    concurrency: int = 32,
) -> list[WledDevice]:
    """Probe every host in `subnet`, return the WLED devices found, deduped by MAC."""
    return await sweep_hosts(subnet.hosts(), timeout=timeout, concurrency=concurrency)


async def sweep_hosts(
    hosts: Iterable,
    *,
    timeout: float = 2.0,
    concurrency: int = 32,
) -> list[WledDevice]:
    """Probe each host concurrently. Dedupe by MAC, sort by IP."""
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:

        async def _one(ip) -> WledDevice | None:
            async with sem:
                return await probe_device(client, ip, source="sweep", timeout=timeout)

        results = await asyncio.gather(*(_one(ip) for ip in hosts))

    by_mac: dict[str, WledDevice] = {}
    for device in results:
        if device is None:
            continue
        by_mac.setdefault(device.mac, device)
    return sorted(by_mac.values(), key=lambda d: int(d.ip))
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_sweep.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/wrangler/src/wrangler/scanner/sweep.py apps/wrangler/tests/test_sweep.py
git commit -m "feat(wrangler): concurrent IP-range sweep with MAC dedup"
```

---

## Task 12: TDD — `scanner/mdns.py` (zeroconf discovery)

**Files:**
- Create: `apps/wrangler/tests/test_mdns.py`
- Create: `apps/wrangler/src/wrangler/scanner/mdns.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_mdns.py`:

```python
"""Tests for wrangler.scanner.mdns."""

from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import MagicMock, patch

import pytest

from wrangler.scanner.mdns import discover_via_mdns


class _FakeInfo:
    def __init__(self, addresses: list[bytes]) -> None:
        self.addresses = addresses

    def parsed_addresses(self) -> list[str]:
        return [IPv4Address(int.from_bytes(a, "big")).compressed for a in self.addresses]


@pytest.mark.asyncio
async def test_discover_via_mdns_returns_ips() -> None:
    fake_info = _FakeInfo([IPv4Address("10.0.6.207").packed])
    fake_zeroconf = MagicMock()
    fake_zeroconf.get_service_info.return_value = fake_info

    class _FakeBrowser:
        def __init__(self, zc, service_type, listener) -> None:  # noqa: ARG002
            listener.add_service(zc, service_type, "WLED-Matrix._wled._tcp.local.")

        def cancel(self) -> None:
            pass

    with (
        patch("wrangler.scanner.mdns.Zeroconf", return_value=fake_zeroconf),
        patch("wrangler.scanner.mdns.ServiceBrowser", _FakeBrowser),
    ):
        ips = await discover_via_mdns(timeout=0.1)

    assert IPv4Address("10.0.6.207") in ips


@pytest.mark.asyncio
async def test_discover_via_mdns_empty_on_timeout() -> None:
    fake_zeroconf = MagicMock()

    class _NoopBrowser:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def cancel(self) -> None:
            pass

    with (
        patch("wrangler.scanner.mdns.Zeroconf", return_value=fake_zeroconf),
        patch("wrangler.scanner.mdns.ServiceBrowser", _NoopBrowser),
    ):
        ips = await discover_via_mdns(timeout=0.05)

    assert ips == set()
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_mdns.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement mdns discovery**

`apps/wrangler/src/wrangler/scanner/mdns.py`:

```python
"""mDNS-based WLED discovery using python-zeroconf."""

from __future__ import annotations

import asyncio
import logging
from ipaddress import IPv4Address

from zeroconf import ServiceBrowser, Zeroconf

logger = logging.getLogger(__name__)

_WLED_SERVICE = "_wled._tcp.local."


class _WledListener:
    def __init__(self) -> None:
        self.addresses: set[IPv4Address] = set()

    def add_service(self, zc: Zeroconf, service_type: str, name: str) -> None:
        info = zc.get_service_info(service_type, name, timeout=1000)
        if info is None:
            logger.debug("mdns: no info for %s", name)
            return
        for addr in info.parsed_addresses():
            try:
                self.addresses.add(IPv4Address(addr))
            except ValueError:
                logger.debug("mdns: non-ipv4 address %s from %s", addr, name)

    def update_service(self, *_args, **_kwargs) -> None:  # pragma: no cover - zeroconf noise
        pass

    def remove_service(self, *_args, **_kwargs) -> None:  # pragma: no cover - zeroconf noise
        pass


async def discover_via_mdns(*, timeout: float = 3.0) -> set[IPv4Address]:
    """Browse the LAN for `_wled._tcp` services for `timeout` seconds.

    Never raises: a zeroconf bind failure yields an empty set.
    """
    try:
        zc = Zeroconf()
    except OSError as exc:
        logger.warning("mdns: zeroconf bind failed: %s", exc)
        return set()

    listener = _WledListener()
    browser = ServiceBrowser(zc, _WLED_SERVICE, listener)
    try:
        await asyncio.sleep(timeout)
    finally:
        browser.cancel()
        zc.close()
    return listener.addresses
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_mdns.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/wrangler/src/wrangler/scanner/mdns.py apps/wrangler/tests/test_mdns.py
git commit -m "feat(wrangler): mDNS discovery of _wled._tcp services"
```

---

## Task 13: TDD — `scanner.__init__` orchestrator (mdns-first + fallback)

**Files:**
- Create: `apps/wrangler/tests/test_scan_integration.py`
- Modify: `apps/wrangler/src/wrangler/scanner/__init__.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_scan_integration.py`:

```python
"""Integration tests for the scan() orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv4Network
from unittest.mock import AsyncMock, patch

import pytest

from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions, scan


def _device(ip: str, mac: str, via: str) -> WledDevice:
    return WledDevice(
        ip=IPv4Address(ip),
        name=f"WLED-{ip}",
        mac=mac,
        version="0.15.0",
        led_count=256,
        matrix=None,
        udp_port=21324,
        raw_info={},
        discovered_via=via,  # type: ignore[arg-type]
        discovered_at=datetime.now(tz=UTC),
    )


@pytest.mark.asyncio
async def test_scan_prefers_mdns_and_skips_sweep_when_found() -> None:
    with (
        patch(
            "wrangler.scanner.discover_via_mdns",
            AsyncMock(return_value={IPv4Address("10.0.6.207")}),
        ),
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[]),
        ) as mock_sweep,
        patch(
            "wrangler.scanner.probe_device",
            AsyncMock(return_value=_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "mdns")),
        ),
    ):
        devices = await scan(ScanOptions(mdns_timeout=0.01))

    assert len(devices) == 1
    assert devices[0].discovered_via == "mdns"
    mock_sweep.assert_not_awaited()


@pytest.mark.asyncio
async def test_scan_falls_back_to_sweep_when_mdns_empty() -> None:
    with (
        patch(
            "wrangler.scanner.discover_via_mdns",
            AsyncMock(return_value=set()),
        ),
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "sweep")]),
        ) as mock_sweep,
        patch(
            "wrangler.scanner.detect_default_subnet",
            return_value=IPv4Network("10.0.6.0/24"),
        ),
    ):
        devices = await scan(ScanOptions(mdns_timeout=0.01))

    assert len(devices) == 1
    assert devices[0].discovered_via == "sweep"
    mock_sweep.assert_awaited_once()


@pytest.mark.asyncio
async def test_scan_force_sweep_runs_both() -> None:
    with (
        patch(
            "wrangler.scanner.discover_via_mdns",
            AsyncMock(return_value={IPv4Address("10.0.6.207")}),
        ),
        patch(
            "wrangler.scanner.probe_device",
            AsyncMock(return_value=_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "mdns")),
        ),
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[_device("10.0.6.208", "11:22:33:44:55:66", "sweep")]),
        ) as mock_sweep,
        patch(
            "wrangler.scanner.detect_default_subnet",
            return_value=IPv4Network("10.0.6.0/24"),
        ),
    ):
        devices = await scan(ScanOptions(mdns_timeout=0.01, sweep=True))

    assert len(devices) == 2
    mock_sweep.assert_awaited_once()


@pytest.mark.asyncio
async def test_scan_no_mdns_is_sweep_only() -> None:
    with (
        patch("wrangler.scanner.discover_via_mdns", AsyncMock(return_value=set())) as mock_mdns,
        patch(
            "wrangler.scanner.sweep_hosts",
            AsyncMock(return_value=[_device("10.0.6.207", "aa:bb:cc:dd:ee:ff", "sweep")]),
        ),
        patch(
            "wrangler.scanner.detect_default_subnet",
            return_value=IPv4Network("10.0.6.0/24"),
        ),
    ):
        devices = await scan(ScanOptions(use_mdns=False))

    assert len(devices) == 1
    mock_mdns.assert_not_awaited()
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_scan_integration.py -v
```
Expected: ImportError — `ScanOptions`/`scan` not defined.

- [ ] **Step 3: Implement the orchestrator**

`apps/wrangler/src/wrangler/scanner/__init__.py`:

```python
"""Public scanner API: mDNS-first discovery with sweep fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

import httpx

from wrangled_contracts import WledDevice

from wrangler.scanner.mdns import discover_via_mdns
from wrangler.scanner.netinfo import detect_default_subnet
from wrangler.scanner.probe import probe_device
from wrangler.scanner.sweep import sweep_hosts

__all__ = [
    "ScanOptions",
    "discover_via_mdns",
    "detect_default_subnet",
    "probe_device",
    "scan",
    "sweep_hosts",
]


@dataclass(frozen=True)
class ScanOptions:
    """Configuration for a scan.

    sweep:
        None  → fallback: sweep only if mDNS finds nothing (default).
        True  → always sweep, in addition to mDNS (unless use_mdns=False).
        False → never sweep.
    """

    use_mdns: bool = True
    mdns_timeout: float = 3.0
    sweep: bool | None = None
    sweep_subnet: IPv4Network | None = None
    probe_timeout: float = 2.0
    probe_concurrency: int = 32
    include: Iterable[IPv4Address] = field(default_factory=tuple)


async def scan(opts: ScanOptions | None = None) -> list[WledDevice]:
    """Discover WLEDs on the LAN. Returns a deduped list sorted by IP."""
    opts = opts or ScanOptions()
    found_by_mac: dict[str, WledDevice] = {}

    mdns_candidates: set[IPv4Address] = set()
    if opts.use_mdns:
        mdns_candidates = await discover_via_mdns(timeout=opts.mdns_timeout)

    if mdns_candidates:
        async with httpx.AsyncClient() as client:
            for ip in mdns_candidates:
                device = await probe_device(
                    client,
                    ip,
                    source="mdns",
                    timeout=opts.probe_timeout,
                )
                if device is not None:
                    found_by_mac.setdefault(device.mac, device)

    should_sweep = opts.sweep is True or (opts.sweep is None and not found_by_mac)
    if should_sweep:
        subnet = opts.sweep_subnet or detect_default_subnet()
        sweep_results = await sweep_hosts(
            subnet.hosts(),
            timeout=opts.probe_timeout,
            concurrency=opts.probe_concurrency,
        )
        for device in sweep_results:
            found_by_mac.setdefault(device.mac, device)

    return sorted(found_by_mac.values(), key=lambda d: int(d.ip))
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_scan_integration.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run the full wrangler test suite**

```bash
uv run pytest -v
```
Expected: all non-live tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/wrangler/src/wrangler/scanner/__init__.py apps/wrangler/tests/test_scan_integration.py
git commit -m "feat(wrangler): scan() orchestrator with mDNS-first + sweep fallback"
```

---

## Task 14: TDD — CLI (`wrangler scan`)

**Files:**
- Create: `apps/wrangler/tests/test_cli.py`
- Create: `apps/wrangler/src/wrangler/cli.py`
- Create: `apps/wrangler/src/wrangler/__main__.py`

- [ ] **Step 1: Write failing tests**

`apps/wrangler/tests/test_cli.py`:

```python
"""Tests for wrangler.cli."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest

from wrangled_contracts import WledDevice, WledMatrix

from wrangler.cli import main


def _device() -> WledDevice:
    return WledDevice(
        ip=IPv4Address("10.0.6.207"),
        name="WLED-Matrix",
        mac="aa:bb:cc:dd:ee:ff",
        version="0.15.0",
        led_count=256,
        matrix=WledMatrix(width=16, height=16),
        udp_port=21324,
        raw_info={},
        discovered_via="mdns",
        discovered_at=datetime(2026, 4, 13, tzinfo=UTC),
    )


@pytest.fixture
def fake_scan() -> AsyncMock:
    return AsyncMock(return_value=[_device()])


def test_cli_scan_table_output(
    fake_scan: AsyncMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("wrangler.cli.scan", fake_scan):
        exit_code = main(["scan"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "10.0.6.207" in captured.out
    assert "WLED-Matrix" in captured.out
    assert "16x16" in captured.out


def test_cli_scan_json_output(
    fake_scan: AsyncMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("wrangler.cli.scan", fake_scan):
        exit_code = main(["scan", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload[0]["ip"] == "10.0.6.207"


def test_cli_scan_empty_is_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("wrangler.cli.scan", AsyncMock(return_value=[])):
        exit_code = main(["scan"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 devices" in captured.out


def test_cli_scan_force_sweep_flag_sets_option() -> None:
    captured_opts = {}

    async def _capture(opts):
        captured_opts["opts"] = opts
        return []

    with patch("wrangler.cli.scan", side_effect=_capture):
        main(["scan", "--sweep"])
    assert captured_opts["opts"].sweep is True


def test_cli_scan_no_mdns_flag_sets_option() -> None:
    captured_opts = {}

    async def _capture(opts):
        captured_opts["opts"] = opts
        return []

    with patch("wrangler.cli.scan", side_effect=_capture):
        main(["scan", "--no-mdns"])
    assert captured_opts["opts"].use_mdns is False


def test_cli_scan_subnet_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_opts = {}

    async def _capture(opts):
        captured_opts["opts"] = opts
        return []

    with patch("wrangler.cli.scan", side_effect=_capture):
        main(["scan", "--subnet", "10.0.6.0/24"])
    assert str(captured_opts["opts"].sweep_subnet) == "10.0.6.0/24"
    capsys.readouterr()
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_cli.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement the CLI**

`apps/wrangler/src/wrangler/cli.py`:

```python
"""Wrangler command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from ipaddress import IPv4Network
from typing import Sequence

from wrangled_contracts import WledDevice

from wrangler.scanner import ScanOptions, scan


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wrangler", description="WrangLED Pi-side agent.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="Discover WLEDs on the LAN.")
    scan_parser.add_argument(
        "--sweep",
        action="store_true",
        help="Force IP-range sweep in addition to mDNS.",
    )
    scan_parser.add_argument(
        "--no-mdns",
        dest="use_mdns",
        action="store_false",
        help="Skip mDNS; sweep only.",
    )
    scan_parser.add_argument(
        "--subnet",
        type=IPv4Network,
        default=None,
        help="Override subnet to sweep (e.g. 10.0.6.0/24).",
    )
    scan_parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Per-host probe timeout seconds (default: 2.0).",
    )
    scan_parser.add_argument(
        "--mdns-timeout",
        type=float,
        default=3.0,
        help="mDNS listen duration (default: 3.0).",
    )
    scan_parser.add_argument(
        "--concurrency",
        type=int,
        default=32,
        help="Max concurrent probes during sweep (default: 32).",
    )
    scan_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit results as JSON instead of a table.",
    )
    return parser


def _opts_from_args(args: argparse.Namespace) -> ScanOptions:
    return ScanOptions(
        use_mdns=args.use_mdns,
        mdns_timeout=args.mdns_timeout,
        sweep=True if args.sweep else None,
        sweep_subnet=args.subnet,
        probe_timeout=args.timeout,
        probe_concurrency=args.concurrency,
    )


def _print_table(devices: list[WledDevice]) -> None:
    if not devices:
        print("0 devices found.")
        return
    header = f"{'IP':<15} {'NAME':<20} {'MAC':<18} {'VER':<10} {'LEDS':>5}  {'MATRIX':<7} {'VIA':<6}"
    print(header)
    for d in devices:
        matrix = f"{d.matrix.width}x{d.matrix.height}" if d.matrix else "-"
        print(
            f"{str(d.ip):<15} {d.name[:20]:<20} {d.mac:<18} {d.version:<10} "
            f"{d.led_count:>5}  {matrix:<7} {d.discovered_via:<6}",
        )
    print(f"\n{len(devices)} device{'s' if len(devices) != 1 else ''}.")


def _print_json(devices: list[WledDevice]) -> None:
    payload = [d.model_dump(mode="json") for d in devices]
    print(json.dumps(payload, indent=2))


async def _run_scan(opts: ScanOptions, *, as_json: bool) -> int:
    devices = await scan(opts)
    if as_json:
        _print_json(devices)
    else:
        _print_table(devices)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "scan":
        return asyncio.run(_run_scan(_opts_from_args(args), as_json=args.as_json))
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

`apps/wrangler/src/wrangler/__main__.py`:

```python
"""Allow `python -m wrangler`."""

import sys

from wrangler.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_cli.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Smoke-run the CLI**

```bash
uv run wrangler scan --help
```
Expected: argparse help text listing all flags.

- [ ] **Step 6: Lint the whole wrangler app**

```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: clean. Fix any nits with `ruff check --fix .`.

- [ ] **Step 7: Commit**

```bash
git add apps/wrangler/src/wrangler/cli.py apps/wrangler/src/wrangler/__main__.py apps/wrangler/tests/test_cli.py
git commit -m "feat(wrangler): scan CLI with table + JSON output"
```

---

## Task 15: Live smoke test against `10.0.6.207` (opt-in)

**Files:**
- Create: `apps/wrangler/tests/test_live.py`

- [ ] **Step 1: Write the live test**

`apps/wrangler/tests/test_live.py`:

```python
"""Opt-in live test hitting a real WLED on the LAN.

Run with: `uv run pytest -m live`
Skipped by default (see pytest addopts in pyproject.toml).
"""

from __future__ import annotations

import pytest

from wrangler.scanner import ScanOptions, scan

LIVE_IP = "10.0.6.207"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_scan_finds_known_device() -> None:
    devices = await scan(ScanOptions(mdns_timeout=3.0))
    found = [d for d in devices if str(d.ip) == LIVE_IP]
    assert found, f"expected to find WLED at {LIVE_IP}; found instead: {[str(d.ip) for d in devices]}"
    device = found[0]
    assert device.mac
    assert device.led_count > 0
```

- [ ] **Step 2: Run the live test manually**

```bash
cd apps/wrangler
uv run pytest -m live -v
```
Expected: passes when 10.0.6.207 is reachable; otherwise it explains what it found. If it fails because mDNS is blocked on your dev box, also try:

```bash
uv run pytest -m live -v --override-ini="addopts="
# or run the CLI directly
uv run wrangler scan --sweep --subnet 10.0.6.0/24
```

- [ ] **Step 3: Confirm default run skips the live test**

```bash
uv run pytest -v
```
Expected: live test deselected.

- [ ] **Step 4: Commit**

```bash
git add apps/wrangler/tests/test_live.py
git commit -m "test(wrangler): add opt-in live scan against 10.0.6.207"
```

---

## Task 16: Root `lint.sh`

**Files:**
- Create: `lint.sh`

- [ ] **Step 1: Write `lint.sh`**

```bash
#!/usr/bin/env bash
# Run Ruff + ESLint across the whole monorepo.
# Usage: ./lint.sh [--fix]

set -euo pipefail

FIX=0
if [[ "${1:-}" == "--fix" ]]; then
  FIX=1
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY_APPS=(packages/contracts apps/wrangler)
JS_APPS=(apps/dashboard)

failed=0

for app in "${PY_APPS[@]}"; do
  if [[ ! -f "$ROOT/$app/pyproject.toml" ]]; then
    echo "skip (no pyproject): $app"
    continue
  fi
  echo "=== ruff: $app ==="
  (
    cd "$ROOT/$app"
    if [[ $FIX -eq 1 ]]; then
      uv run ruff check --fix .
      uv run ruff format .
    else
      uv run ruff check .
      uv run ruff format --check .
    fi
  ) || failed=1
done

for app in "${JS_APPS[@]}"; do
  if [[ ! -f "$ROOT/$app/package.json" ]]; then
    echo "skip (no package.json): $app"
    continue
  fi
  echo "=== eslint: $app ==="
  (
    cd "$ROOT/$app"
    if [[ $FIX -eq 1 ]]; then
      npx eslint . --fix
    else
      npx eslint .
    fi
  ) || failed=1
done

if [[ $failed -ne 0 ]]; then
  echo "lint failed" >&2
  exit 1
fi
echo "lint clean"
```

- [ ] **Step 2: Make it executable and run it**

```bash
chmod +x lint.sh
./lint.sh
```
Expected: `lint clean`. If ESLint produces errors against the existing dashboard, capture the output — the expectation is the dashboard currently lints clean under its existing config; if it doesn't, open a follow-up task (do NOT rewrite the dashboard as part of this milestone).

- [ ] **Step 3: Commit**

```bash
git add lint.sh
git commit -m "chore: add repo-root lint.sh (ruff + eslint)"
```

---

## Task 17: Root `build.sh`

**Files:**
- Create: `build.sh`

- [ ] **Step 1: Write `build.sh`**

```bash
#!/usr/bin/env bash
# Install, build, lint, and test the monorepo.
# Usage: ./build.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 1; }

echo "=== python: packages/contracts ==="
( cd "$ROOT/packages/contracts" && uv sync )

echo "=== python: apps/wrangler ==="
( cd "$ROOT/apps/wrangler" && uv sync )

echo "=== node: apps/dashboard ==="
( cd "$ROOT/apps/dashboard" && npm install && npm run build )

echo "=== lint ==="
"$ROOT/lint.sh"

echo "=== tests: packages/contracts ==="
( cd "$ROOT/packages/contracts" && uv run pytest -v )

echo "=== tests: apps/wrangler ==="
( cd "$ROOT/apps/wrangler" && uv run pytest -v )

echo "build ok"
```

- [ ] **Step 2: Make executable and run it**

```bash
chmod +x build.sh
./build.sh
```
Expected: ends with `build ok`.

- [ ] **Step 3: Commit**

```bash
git add build.sh
git commit -m "chore: add repo-root build.sh (install + build + lint + test)"
```

---

## Task 18: Root `dev.sh` (minimal)

**Files:**
- Create: `dev.sh`

Note: `api` and `wrangler-ui` aren't implemented yet. `dev.sh` for milestone 1 just runs the dashboard Vite dev server. Later milestones extend it to concurrently run api + wrangler + both Vite servers.

- [ ] **Step 1: Write `dev.sh`**

```bash
#!/usr/bin/env bash
# Start dev processes for the monorepo.
# Milestone 1: only apps/dashboard has a dev server. Extended in later milestones.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "dev.sh — milestone 1: dashboard only"
echo "later milestones will add: api (8500), wrangler (8501), wrangler-ui (8511)"
echo ""

cd "$ROOT/apps/dashboard"
exec npm run dev
```

- [ ] **Step 2: Make executable**

```bash
chmod +x dev.sh
```

- [ ] **Step 3: Commit**

```bash
git add dev.sh
git commit -m "chore: add minimal dev.sh (dashboard-only for milestone 1)"
```

---

## Task 19: End-to-end verification against the real matrix

This is a manual verification step, not a test task, but it's the whole point of milestone 1.

- [ ] **Step 1: From the dev laptop (same LAN as 10.0.6.207)**

```bash
cd /home/jvogel/src/personal/wrangled-dashboard
./build.sh
cd apps/wrangler
uv run wrangler scan
```

Expected: at least one row including `10.0.6.207` / `WLED-Matrix`. MAC populated. Matrix dimensions populated. `VIA` column is `mdns` (or `sweep` if mDNS is blocked locally — still a pass).

- [ ] **Step 2: Try JSON output**

```bash
uv run wrangler scan --json
```
Expected: valid JSON array, one object per device.

- [ ] **Step 3: Try forced sweep on the known subnet**

```bash
uv run wrangler scan --no-mdns --subnet 10.0.6.0/24
```
Expected: same device discovered via sweep.

- [ ] **Step 4: Run the opt-in live test**

```bash
uv run pytest -m live -v
```
Expected: passes.

- [ ] **Step 5: Merge / celebrate**

No code change here — the milestone is done when the above four commands succeed on your dev machine with the real hardware.

---

## Self-Review Notes

- **Spec coverage:** every section of the spec maps to tasks — monorepo layout (T1), gitignore (T2), ruff config (T3), CLAUDE.mds (T4), contracts (T5–T7), wrangler scaffold (T8), scanner modules (T9–T13), CLI (T14), live test (T15), lint.sh (T16), build.sh (T17), dev.sh (T18), end-to-end check (T19).
- **Placeholder scan:** no TBDs, every step shows the code or exact command.
- **Type consistency:** `ScanOptions` field names (`use_mdns`, `sweep`, `sweep_subnet`, `probe_timeout`, `probe_concurrency`, `mdns_timeout`) referenced consistently across tests and implementation. `WledDevice` field names match between contracts tests (T7), probe (T9), and CLI (T14). `discovered_via` is `"mdns" | "sweep"` everywhere.
- **Scope:** bounded to milestone 1 per spec. WS client, WLED pushing, wrangler-ui, auth, persistence are all deferred.
