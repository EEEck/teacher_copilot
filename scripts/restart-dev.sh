#!/usr/bin/env bash
# Start or restart KlassenPilot dev servers (Git Bash on Windows, macOS, Linux).
#
# Usage (from repo root):
#   ./scripts/restart-dev.sh              # restart backend + frontend
#   ./scripts/restart-dev.sh stop         # stop only
#   ./scripts/restart-dev.sh status       # show what's listening
#   ./scripts/restart-dev.sh --backend-only
#   ./scripts/restart-dev.sh --frontend-only
#
# Backend:  http://127.0.0.1:8010/api/health
# Frontend: http://localhost:3000

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
LOG_DIR="$ROOT/scripts/.logs"
BACKEND_ONLY=false
FRONTEND_ONLY=false
MODE="restart"

for arg in "$@"; do
  case "$arg" in
    --backend-only) BACKEND_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    stop) MODE="stop" ;;
    status) MODE="status" ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
  esac
done

is_windows() {
  [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* || "${OSTYPE:-}" == win32* ]]
}

# Stop uvicorn/next processes for this repo (Windows leaves ghost :8001 listeners otherwise).
kill_project_dev_processes() {
  if ! is_windows || ! command -v powershell.exe >/dev/null 2>&1; then
    return 0
  fi
  powershell.exe -NoProfile -Command "
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object {
        \$_.CommandLine -and \$_.CommandLine -like '*teacher_agent_v2*' -and (
          \$_.CommandLine -like '*uvicorn*' -or
          \$_.CommandLine -like '*app.main*' -or
          \$_.CommandLine -like '*multiprocessing-fork*' -or
          (\$_.CommandLine -like '*next*' -and \$_.CommandLine -like '*dev*')
        )
      } | ForEach-Object {
        Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue
      }
  " 2>/dev/null || true
}

ensure_windows_path() {
  if ! is_windows; then
    return 0
  fi
  for dir in \
    "/c/Program Files/nodejs" \
    "/c/Program Files (x86)/nodejs" \
    "$HOME/AppData/Local/Programs/nodejs"; do
    if [[ -d "$dir" ]]; then
      export PATH="$dir:$PATH"
    fi
  done
}

# Kill whatever is listening on a TCP port.
kill_port() {
  local port=$1
  if is_windows; then
    # Git Bash: netstat + taskkill (repeat — uvicorn --reload leaves parent/child pairs)
    local attempt pid pids
    for attempt in 1 2 3 4 5 6; do
      pids="$(netstat -ano 2>/dev/null | grep ":${port} " | grep LISTENING | awk '{print $NF}' | sort -u || true)"
      [[ -z "$pids" ]] && break
      while read -r pid; do
        [[ -z "$pid" || "$pid" == "0" ]] && continue
        taskkill //F //PID "$pid" 2>/dev/null || true
      done <<< "$pids"
      sleep 1
    done
    if command -v npx >/dev/null 2>&1; then
      npx --yes kill-port "$port" 2>/dev/null || true
    elif [[ -f "/c/Program Files/nodejs/npx.cmd" ]]; then
      "/c/Program Files/nodejs/npx.cmd" --yes kill-port "$port" 2>/dev/null || true
    fi
    sleep 1
  elif command -v lsof >/dev/null 2>&1; then
    lsof -ti ":$port" | xargs -r kill -9 2>/dev/null || true
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
}

port_listening() {
  local port=$1
  if is_windows; then
    netstat -ano 2>/dev/null | grep ":${port} " | grep -q LISTEN
  elif command -v lsof >/dev/null 2>&1; then
    lsof -ti ":$port" >/dev/null 2>&1
  else
    return 1
  fi
}

load_backend_env() {
  local env_file="$ROOT/backend/.env"
  if [[ ! -f "$env_file" ]]; then
    echo "Warning: no backend/.env (set OPENAI_API_KEY there for live agent chat)" >&2
    return 0
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line//$'\r'/}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    if [[ "$line" == *=* ]]; then
      local name="${line%%=*}"
      local value="${line#*=}"
      value="${value%\"}"; value="${value#\"}"
      value="${value%\'}"; value="${value#\'}"
      export "$name=$value"
    fi
  done < "$env_file"
}

uvicorn_bin() {
  if is_windows; then
    echo "$ROOT/backend/.venv/Scripts/uvicorn.exe"
  else
    echo "$ROOT/backend/.venv/bin/uvicorn"
  fi
}

npm_cmd() {
  if command -v npm >/dev/null 2>&1; then
    echo npm
  elif [[ -f "/c/Program Files/nodejs/npm.cmd" ]]; then
    echo "/c/Program Files/nodejs/npm.cmd"
  else
    echo ""
  fi
}

show_status() {
  echo "Ports:"
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    if port_listening "$port"; then
      echo "  :$port  listening"
    else
      echo "  :$port  free"
    fi
  done
}

stop_ports() {
  if ! $FRONTEND_ONLY; then
    kill_port "$BACKEND_PORT"
  fi
  if ! $BACKEND_ONLY; then
    kill_port "$FRONTEND_PORT"
  fi
}

stop_all() {
  echo "Stopping dev servers..."
  kill_project_dev_processes
  stop_ports
  sleep 1
  echo "Done."
}

start_backend() {
  local uvicorn
  uvicorn="$(uvicorn_bin)"
  if [[ ! -f "$uvicorn" ]]; then
    echo "Backend venv missing. Run:" >&2
    echo "  cd backend && python -m venv .venv && .venv/Scripts/pip install -e ." >&2
    exit 1
  fi
  mkdir -p "$LOG_DIR"
  load_backend_env
  echo "Starting backend on :$BACKEND_PORT (log: scripts/.logs/backend.log)"
  cd "$ROOT/backend"
  nohup "$uvicorn" app.main:app --reload --port "$BACKEND_PORT" \
    >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$LOG_DIR/backend.pid"
}

start_frontend() {
  ensure_windows_path
  if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
    echo "Frontend deps missing. Run: cd frontend && npm install" >&2
    exit 1
  fi
  mkdir -p "$LOG_DIR"
  echo "Starting frontend on :$FRONTEND_PORT (log: scripts/.logs/frontend.log)"
  cd "$ROOT/frontend"
  local npm_bin
  npm_bin="$(npm_cmd)"
  if [[ -z "$npm_bin" ]]; then
    echo "npm not found. Install Node.js 18+ (https://nodejs.org) and reopen Git Bash." >&2
    exit 1
  fi
  nohup "$npm_bin" run dev >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$LOG_DIR/frontend.pid"
}

case "$MODE" in
  status)
    show_status
    exit 0
    ;;
  stop)
    stop_all
    exit 0
    ;;
esac

kill_project_dev_processes
stop_ports
sleep 1

$FRONTEND_ONLY || start_backend
$BACKEND_ONLY || start_frontend

sleep 3
echo ""
echo "Dev servers:"
$FRONTEND_ONLY || echo "  Backend:  http://127.0.0.1:$BACKEND_PORT/api/health"
$BACKEND_ONLY || echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Logs:     scripts/.logs/"
echo ""
echo "  ./scripts/restart-dev.sh stop     # stop"
echo "  ./scripts/restart-dev.sh status   # check ports"
echo "  tail -f scripts/.logs/backend.log"
