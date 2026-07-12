$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$python = Get-Command python -ErrorAction SilentlyContinue

if ($python) {
    $pythonExe = $python.Source
} elseif (Test-Path $bundledPython) {
    $pythonExe = $bundledPython
} else {
    throw "Python not found. Install Python or run this from Codex with the bundled runtime available."
}

Push-Location $root
try {
    & $pythonExe "$root\scripts\worktree_stack.py" @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
