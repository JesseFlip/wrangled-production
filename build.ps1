$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required: https://docs.astral.sh/uv/"
    exit 1
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm is required"
    exit 1
}

Write-Host "=== python: packages/contracts ==="
Push-Location "$ROOT\packages\contracts"
uv sync
Pop-Location

Write-Host "=== python: apps/wrangler ==="
Push-Location "$ROOT\apps\wrangler"
uv sync
Pop-Location

Write-Host "=== node: apps/dashboard ==="
Push-Location "$ROOT\apps\dashboard"
npm install
npm run build
Pop-Location

Write-Host "=== node: apps/wrangler-ui ==="
Push-Location "$ROOT\apps\wrangler-ui"
npm install
npm run build
Pop-Location

Write-Host "=== tests: packages/contracts ==="
Push-Location "$ROOT\packages\contracts"
uv run pytest -v
Pop-Location

Write-Host "=== tests: apps/wrangler ==="
Push-Location "$ROOT\apps\wrangler"
uv run pytest -v
Pop-Location

Write-Host "build ok"
