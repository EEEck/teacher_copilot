@echo off
REM Restart KlassenPilot dev servers (works from cmd.exe or PowerShell).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart-dev.ps1" -NoNewWindow %*
