#!/usr/bin/env bash
# Docker Compose dev helpers (Git Bash on Windows, macOS, Linux).
#
# Usage (from repo root):
#   ./scripts/docker-dev.sh              # up --build -d
#   ./scripts/docker-dev.sh up           # same
#   ./scripts/docker-dev.sh up-fg        # foreground (logs in terminal)
#   ./scripts/docker-dev.sh down         # stop and remove containers
#   ./scripts/docker-dev.sh logs         # follow all service logs
#   ./scripts/docker-dev.sh ps           # container status
#   ./scripts/docker-dev.sh restart      # restart both services
#   ./scripts/docker-dev.sh restart backend
#   ./scripts/docker-dev.sh rebuild frontend
#
# App:     http://localhost:3000
# API:     http://localhost:8010/api/health

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/compose.yaml"
CMD="${1:-up}"

cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker Desktop and reopen Git Bash." >&2
  exit 1
fi

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

case "$CMD" in
  up|start)
    compose up --build -d
    echo ""
    echo "Docker dev stack started:"
    echo "  App:  http://localhost:3000"
    echo "  API:  http://localhost:8010/api/health"
    echo ""
    echo "  ./scripts/docker-dev.sh logs   # follow logs"
    echo "  ./scripts/docker-dev.sh down   # stop"
    ;;
  up-fg)
    compose up --build
    ;;
  down|stop)
    compose down
    echo "Docker dev stack stopped."
    ;;
  logs)
    shift || true
    compose logs -f "$@"
    ;;
  ps|status)
    compose ps
    ;;
  restart)
    shift || true
    if [[ $# -eq 0 ]]; then
      compose restart backend frontend
    else
      compose restart "$@"
    fi
    ;;
  rebuild)
    shift || true
    if [[ $# -eq 0 ]]; then
      compose up --build -d
    else
      compose up --build -d "$@"
    fi
    ;;
  -h|--help|help)
    sed -n '2,16p' "$0"
    ;;
  *)
    echo "Unknown command: $CMD" >&2
    echo "Run: ./scripts/docker-dev.sh --help" >&2
    exit 1
    ;;
esac
