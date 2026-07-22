<#
.SYNOPSIS
  Provision a Railway beta tester from a short name prefix.

.DESCRIPTION
  Generates a secure invite code `{prefix}_{random}`, derives tester/workspace
  ids, SSHs into the linked Railway backend, and runs beta_cli provision.
  Prints an invite message you can paste to the tester.

.EXAMPLE
  .\scripts\railway-beta-provision.ps1 -Prefix maria

.EXAMPLE
  .\scripts\railway-beta-provision.ps1 -Prefix lb -DisplayLabel "LB (Chemie 9b)" -SuffixLength 24
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z][A-Za-z0-9_-]{0,31}$')]
  [string]$Prefix,

  [string]$DisplayLabel = "",

  [ValidateRange(16, 48)]
  [int]$SuffixLength = 22,

  [string]$Service = "backend",

  [string]$LoginUrl = "https://klassenpilot-beta.up.railway.app/beta/login",

  [string]$IdentityFile = "$env:USERPROFILE\.ssh\railway_ed25519"
)

$ErrorActionPreference = "Stop"

function New-InviteSuffix([int]$Length) {
  $alphabet = [char[]]([char]'a'..[char]'z' + [char]'A'..[char]'Z' + [char]'0'..[char]'9')
  -join (1..$Length | ForEach-Object { $alphabet[(Get-Random -Maximum $alphabet.Length)] })
}

function Get-RailwayCmd {
  $cmd = Get-Command railway.cmd -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $cmd = Get-Command railway -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "Railway CLI not found. Install with: npm.cmd i -g @railway/cli"
}

$slug = ($Prefix -replace '[^A-Za-z0-9]+', '_').ToLowerInvariant().Trim('_')
if (-not $slug) { throw "Prefix produced an empty slug." }

$inviteCode = "${Prefix}_$(New-InviteSuffix $SuffixLength)"
$testerId = "t_$slug"
$workspaceId = "w_$slug"
if (-not $DisplayLabel) {
  $DisplayLabel = "$Prefix beta"
}

# Escape for remote single-quoted shell args (invite may contain ').
function Escape-ShSingle([string]$Value) {
  return $Value.Replace("'", "'\''")
}

# chmod/chown AFTER provision: SSH often runs as root; API runs as uid 1000.
$remote = @(
  "python -m app.services.beta_cli provision"
  "--tester-id $(Escape-ShSingle $testerId)"
  "--workspace-id $(Escape-ShSingle $workspaceId)"
  "--invite-code '$(Escape-ShSingle $inviteCode)'"
  "--display-label '$(Escape-ShSingle $DisplayLabel)'"
  ";"
  "chmod -R a+rwX /data/beta_data 2>/dev/null || true"
  ";"
  "chown -R 1000:1000 /data/beta_data 2>/dev/null || true"
) -join " "

$railway = Get-RailwayCmd
$sshArgs = @("ssh", "-s", $Service)
if (Test-Path $IdentityFile) {
  $sshArgs += @("-i", $IdentityFile)
}
$sshArgs += @("--", "sh", "-lc", $remote)

Write-Host "Provisioning $testerId -> $workspaceId on Railway service '$Service'..."
& $railway @sshArgs
if ($LASTEXITCODE -ne 0) {
  throw "railway ssh provision failed (exit $LASTEXITCODE)"
}

Write-Host ""
Write-Host "=== Invite (share out of band) ==="
Write-Host $inviteCode
Write-Host ""
Write-Host "=== Message template ==="
@"
Hi — you're invited to the KlassenPilot beta (private teacher copilot).

1. Open: $LoginUrl
2. Paste this invite code:
   $inviteCode
3. Choose a display name, then explore with the sample class Chemie 9b.

Notes:
- Your workspace is private to you (your invite only).
- Early beta: expect rough edges; feedback is welcome via the app menu.
- Please don't reshare the invite code.

Thanks!
"@
Write-Host ""
# Optional: append a line to deploy/railway/invites.local.md (gitignored).
$tracker = Join-Path (Split-Path $PSScriptRoot -Parent) "deploy\railway\invites.local.md"
if (-not (Test-Path $tracker)) {
  @"
# Local beta invite tracker (gitignored — do not commit)

| Account / label | Invite code | tester_id | workspace_id | Created |
|-----------------|-------------|-----------|--------------|---------|
"@ | Set-Content -Path $tracker -Encoding utf8
}
$created = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm") + "Z"
Add-Content -Path $tracker -Encoding utf8 -Value "| $DisplayLabel | ``$inviteCode`` | ``$testerId`` | ``$workspaceId`` | $created |"
Write-Host "Tracked in $tracker"
