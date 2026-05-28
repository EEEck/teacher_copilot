#!/usr/bin/env bash
# Restart KlassenPilot dev servers.
# On Windows, delegates to restart-dev.ps1 (Git Bash / PowerShell).
# On macOS/Linux, starts backend + frontend directly.
#
# Usage:
#   ./scripts/restart-dev.sh
#   ./scripts/restart-dev.sh --backend-only
#   ./scripts/restart-dev.sh --frontend-only

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT=8001
FRONTEND_PORT=3000
BACKEND_ONLY=false
FRONTEND_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --backend-only) BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    -h|--help)
      echo "Usage: $0 [--backend-only | --frontend-only]"
      exit 0
      ;;
  esac
done

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  PS_ARGS=()
  $BACKEND_ONLY && PS_ARGS+=("-BackendOnly")
  $FRONTEND_ONLY && PS_ARGS+=("-FrontendOnly")
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$ROOT/scripts/restart-dev.ps1" "${PS_ARGS[@]}"
  exit $?
fi

kill_port() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti ":$port" | xargs -r kill -9 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "$port/tcp" 2>/dev/null || true
  fi
}

echo "Stopping old dev processes..."
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
sleep 2

start_backend() {
  cd "$ROOT/backend"
  if [[ ! -x .venv/bin/uvicorn ]]; then
    echo "Backend venv not found. Run: cd backend && python -m venv .venv && pip install -r requirements.txt" >&2
    exit 1
  fi
  echo "Starting backend on :$BACKEND_PORT"
  .venv/bin/uvicorn app.main:app --reload --port "$BACKEND_PORT" &
}

start_frontend() {
  cd "$ROOT/frontend"
  if [[ ! -d node_modules ]]; then
    echo "Frontend deps not installed. Run: cd frontend && npm install" >&2
    exit 1
  fi
  echo "Starting frontend on :$FRONTEND_PORT"
  npm run dev &
}

$FRONTEND_ONLY || start_backend
$BACKEND_ONLY || start_frontend

sleep 2
echo ""
echo "Dev servers restarted:"
$FRONTEND_ONLY || echo "  Backend:  http://127.0.0.1:$BACKEND_PORT/api/health"
$BACKEND_ONLY || echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop."

wait
