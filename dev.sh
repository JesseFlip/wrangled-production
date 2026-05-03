#!/usr/bin/env bash
# Start all dev processes for the monorepo.
# wrangler FastAPI (8501), wrangler-ui Vite (8511), dashboard Vite.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 1; }

cleanup() {
  echo "shutting down..."
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "starting api FastAPI on :8500"
( cd "$ROOT/apps/api" && uv run api serve --host 127.0.0.1 --port 8500 ) &

echo "starting wrangler FastAPI on :8501"
( cd "$ROOT/apps/wrangler" && uv run wrangler serve --host 127.0.0.1 --port 8501 ) &

echo "starting wrangler-ui Vite on :8511"
( cd "$ROOT/apps/wrangler-ui" && npm run dev ) &

echo "starting dashboard Vite"
( cd "$ROOT/apps/dashboard" && npm run dev ) &

echo ""
echo "  api:          http://localhost:8500/healthz"
echo "  wrangler-ui:  http://localhost:8511"
echo "  wrangler api: http://localhost:8501/healthz"
echo "  dashboard:    (see dashboard Vite output for URL)"
echo ""

wait
