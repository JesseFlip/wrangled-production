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

echo "=== python: apps/api ==="
( cd "$ROOT/apps/api" && uv sync )

echo "=== node: apps/dashboard ==="
( cd "$ROOT/apps/dashboard" && npm install && npm run build )

echo "=== node: apps/wrangler-ui ==="
( cd "$ROOT/apps/wrangler-ui" && npm install && npm run build )

echo "=== lint ==="
"$ROOT/lint.sh"

echo "=== tests: packages/contracts ==="
( cd "$ROOT/packages/contracts" && uv run pytest -v )

echo "=== tests: apps/wrangler ==="
( cd "$ROOT/apps/wrangler" && uv run pytest -v )

echo "=== tests: apps/api ==="
( cd "$ROOT/apps/api" && uv run pytest -v )

echo "build ok"
