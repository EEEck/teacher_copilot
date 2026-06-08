param(
    [string]$ApiBase = "http://localhost:8010",
    [string]$ClassId = "chemie_9b_2026_27",
    [string]$OutputRoot = "backend/runs",
    [string]$RunName = "",
    [string]$Prompt1File = "",
    [string]$Prompt2File = "",
    [string]$Prompt3File = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$argsList = @(
    (Join-Path $PSScriptRoot "run_plan_trace_bundle.py"),
    "--api-base", $ApiBase,
    "--class-id", $ClassId,
    "--output-root", $OutputRoot
)

if ($RunName) {
    $argsList += @("--run-name", $RunName)
}
if ($Prompt1File) {
    $argsList += @("--prompt1-file", $Prompt1File)
}
if ($Prompt2File) {
    $argsList += @("--prompt2-file", $Prompt2File)
}
if ($Prompt3File) {
    $argsList += @("--prompt3-file", $Prompt3File)
}

& $python @argsList
