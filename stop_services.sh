#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"

stop_process() {
  local name="$1"
  local pattern="$2"

  # shellcheck disable=SC2009
  local pids
  pids=$(pgrep -f "$pattern" || true)

  if [[ -z "$pids" ]];
  then
    echo "$name is not running."
    return
  fi

  echo "Stopping $name (PIDs: $pids)..."
  # SIGTERM by default for graceful shutdown
  kill $pids
  wait $pids 2>/dev/null || true
  echo "$name stopped."
}

stop_process "trial registry service" "uvicorn app:app --app-dir $ROOT_DIR/trial-registry-backend"
stop_process "EHR service" "uvicorn app:app --app-dir $ROOT_DIR/ehr-backend"
stop_process "care plan agent" "$ROOT_DIR/care-plan-agent/simple_langgraph.py"

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
