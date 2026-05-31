# Run backend pytest + frontend typecheck + Vitest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Get-NpmExecutable {
    $cmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $npmPath = Join-Path ${env:ProgramFiles} "nodejs\npm.cmd"
    if (Test-Path $npmPath) { return $npmPath }
    throw "npm not found. Install Node.js 18+ (https://nodejs.org) and reopen the terminal."
}

$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Backend venv missing. Run: cd backend; python -m venv .venv; .\.venv\Scripts\pip install -e ."
}

& $python -m pytest "$root\backend" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$npm = Get-NpmExecutable
Push-Location "$root\frontend"
& $npm run typecheck
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
& $npm run test
$code = $LASTEXITCODE
Pop-Location
exit $code
