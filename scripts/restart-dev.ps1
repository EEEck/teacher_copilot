# Restart KlassenPilot dev servers (backend + frontend).
# Usage:
#   .\scripts\restart-dev.ps1              # restart both
#   .\scripts\restart-dev.ps1 -BackendOnly
#   .\scripts\restart-dev.ps1 -FrontendOnly
#   .\scripts\restart-dev.ps1 -NoNewWindow # run in background (same terminal)

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$NoNewWindow
)

$ErrorActionPreference = "SilentlyContinue"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendPort = 8001
$FrontendPort = 3000

function Stop-PortListeners {
    param([int]$Port)
    Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            if ($_ -gt 0) { Stop-Process -Id $_ -Force }
        }
}

function Stop-ProjectDevProcesses {
    Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -like "*teacher_agent_v2*" -and (
                $_.CommandLine -like "*uvicorn*" -or
                $_.CommandLine -like "*app.main*" -or
                $_.CommandLine -like "*multiprocessing-fork*" -or
                ($_.CommandLine -like "*next*" -and $_.CommandLine -like "*dev*")
            )
        } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
}

function Start-DevProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$Command
    )

    if ($NoNewWindow) {
        $logDir = Join-Path $Root "scripts\.logs"
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        $logFile = Join-Path $logDir "$Name.log"
        Write-Host "Starting $Name (log: $logFile)"
        Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoProfile", "-Command",
            "Set-Location '$WorkingDirectory'; $Command *>&1 | Tee-Object -FilePath '$logFile'"
        ) -WindowStyle Hidden
    }
    else {
        Write-Host "Starting $Name in new window"
        Start-Process -FilePath "powershell.exe" -ArgumentList @(
            "-NoExit", "-NoProfile", "-Command",
            "Set-Location '$WorkingDirectory'; Write-Host '=== $Name ===' -ForegroundColor Green; $Command"
        )
    }
}

$restartBackend = -not $FrontendOnly
$restartFrontend = -not $BackendOnly

Write-Host "Stopping old dev processes..."
Stop-ProjectDevProcesses
if ($restartBackend) { Stop-PortListeners -Port $BackendPort }
if ($restartFrontend) { Stop-PortListeners -Port $FrontendPort }
Start-Sleep -Seconds 2

if ($restartBackend) {
    $backendDir = Join-Path $Root "backend"
    $uvicorn = Join-Path $backendDir ".venv\Scripts\uvicorn.exe"
    if (-not (Test-Path $uvicorn)) {
        Write-Error "Backend venv not found. Run: cd backend; python -m venv .venv; pip install -r requirements.txt"
        exit 1
    }
    Start-DevProcess -Name "backend" -WorkingDirectory $backendDir `
        -Command ".\.venv\Scripts\uvicorn app.main:app --reload --port $BackendPort"
}

if ($restartFrontend) {
    $frontendDir = Join-Path $Root "frontend"
    if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
        Write-Error "Frontend deps not installed. Run: cd frontend; npm install"
        exit 1
    }
    Start-DevProcess -Name "frontend" -WorkingDirectory $frontendDir -Command "npm run dev"
}

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "Dev servers restarted:"
if ($restartBackend) { Write-Host "  Backend:  http://127.0.0.1:$BackendPort/api/health" }
if ($restartFrontend) { Write-Host "  Frontend: http://localhost:$FrontendPort" }
