param(
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 4173,
    [switch]$SkipBrowserInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $repoRoot "deploy/compose.yaml"
$overrideFile = Join-Path $repoRoot "deploy/compose.mock-recorded.yaml"
$envFile = Join-Path $repoRoot "deploy/profiles/mock-recorded.env"
$env:PE_AGENT_API_PORT = "$ApiPort"
$env:PE_AGENT_FRONTEND_PORT = "$FrontendPort"

function Wait-Http([string]$Url, [int]$Seconds = 120) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "Timed out waiting for $Url"
}

try {
    docker compose --env-file $envFile -f $composeFile -f $overrideFile up --build -d
    Wait-Http "http://localhost:$ApiPort/health/live"
    Wait-Http "http://localhost:$FrontendPort"

    if (-not $SkipBrowserInstall) {
        npm --prefix (Join-Path $repoRoot "frontend") exec playwright install chromium
    }
    $env:PLAYWRIGHT_BASE_URL = "http://localhost:$FrontendPort"
    npm --prefix (Join-Path $repoRoot "frontend") run test:e2e
} finally {
    docker compose --env-file $envFile -f $composeFile -f $overrideFile down
}
