@echo off
setlocal
set "ROOT=%~dp0.."
set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "PYTHON_EXE=python"
) else if exist "%BUNDLED_PY%" (
  set "PYTHON_EXE=%BUNDLED_PY%"
) else (
  echo Python not found. Install Python or run this from Codex with the bundled runtime available. 1>&2
  exit /b 1
)

pushd "%ROOT%"
"%PYTHON_EXE%" "%ROOT%\scripts\worktree_stack.py" %*
set "CODE=%ERRORLEVEL%"
popd
exit /b %CODE%
