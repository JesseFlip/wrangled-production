#!/usr/bin/env bash
# Run Ruff + ESLint across the whole monorepo.
# Usage: ./lint.sh [--fix]

set -euo pipefail

FIX=0
if [[ "${1:-}" == "--fix" ]]; then
  FIX=1
fi

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY_APPS=(packages/contracts apps/wrangler apps/api)
JS_APPS=(apps/dashboard apps/wrangler-ui)

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
