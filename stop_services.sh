#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"

stop_process() {
  local name="$1"
  local pattern="$2"

  local pids
  pids=$(pgrep -f "$pattern" || true)

  if [[ -z "$pids" ]]; then
    echo "$name is not running."
    return
  fi

  echo "Stopping $name (PIDs: $pids)..."
  kill $pids
  wait $pids 2>/dev/null || true
  echo "$name stopped."
}

# Note: Trial Registry and EHR services removed - now using MCP servers
stop_process "evidence agent" "uvicorn evidence_agent:app --app-dir $ROOT_DIR/evidence-agent"
stop_process "care plan agent" "uvicorn app:app --app-dir $ROOT_DIR/care-plan-agent"
stop_process "frontend" "next dev -p 8080"

echo
read -rp "Do you want to delete the logs directory? (y/N) " reply
case "${reply}" in
  [yY][eE][sS]|[yY])
    if [[ -d "$LOG_DIR" ]]; then
      rm -rf "$LOG_DIR"
      echo "Logs deleted."
    else
      echo "No logs directory found."
    fi
    ;;
  *)
    echo "Logs retained."
    ;;
esac
