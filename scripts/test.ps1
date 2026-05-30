# Run backend pytest + frontend typecheck
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

& "$root\backend\.venv\Scripts\python.exe" -m pytest "$root\backend" -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Push-Location "$root\frontend"
npm run typecheck
$code = $LASTEXITCODE
Pop-Location
exit $code
