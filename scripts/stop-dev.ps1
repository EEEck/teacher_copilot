# Stop KlassenPilot dev servers without restarting.
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "SilentlyContinue"
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

if (-not $FrontendOnly) { Stop-PortListeners -Port $BackendPort }
if (-not $BackendOnly) { Stop-PortListeners -Port $FrontendPort }

Write-Host "Dev servers stopped."
