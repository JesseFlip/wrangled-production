$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot

Write-Host "starting wrangler FastAPI on :8501"
$api = Start-Process -PassThru -FilePath "uv" -ArgumentList "run","wrangler","serve","--host","127.0.0.1","--port","8501" -WorkingDirectory "$ROOT\apps\wrangler" -WindowStyle Minimized

Write-Host "starting wrangler-ui Vite on :8511"
$ui = Start-Process -PassThru -FilePath "npm.cmd" -ArgumentList "run","dev","--","--port","8511" -WorkingDirectory "$ROOT\apps\wrangler-ui" -WindowStyle Minimized

Write-Host "starting dashboard Vite on :5173"
$dashboard = Start-Process -PassThru -FilePath "npm.cmd" -ArgumentList "run","dev","--","--port","5173" -WorkingDirectory "$ROOT\apps\dashboard" -WindowStyle Minimized

Write-Host ""
Write-Host "  wrangler-ui:  http://localhost:8511"
Write-Host "  wrangler api: http://localhost:8501/healthz"
Write-Host "  dashboard:    http://localhost:5173"
Write-Host ""
Write-Host "Servers are running in minimized windows."
Write-Host "Press Ctrl+C to stop servers."

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "Shutting down..."
    $api, $ui, $dashboard | Stop-Process -Force -ErrorAction SilentlyContinue
}
