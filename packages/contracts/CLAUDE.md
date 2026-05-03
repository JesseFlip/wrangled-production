# packages/contracts — Shared Pydantic Models

## Purpose
Pydantic v2 models shared by every Python app in the monorepo. Prevents schema drift between producer and consumer (e.g., `wrangler` discovers a `WledDevice`, `api` consumes it).

## Install in a sibling app
In the sibling's `pyproject.toml`:

    [project]
    dependencies = [
        "wrangled-contracts",
    ]

    [tool.uv.sources]
    wrangled-contracts = { path = "../../packages/contracts", editable = true }

Then `uv sync` in the sibling app.

## Current models (milestone 1)
- `WledMatrix` — width / height of a WLED 2D matrix.
- `WledDevice` — a discovered WLED device (ip, mac, name, version, led_count, matrix, etc.).

## Future additions
- `Command` payload shape
- `WledState`
- Auth token envelopes
