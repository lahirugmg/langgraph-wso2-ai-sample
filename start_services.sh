#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

start_process() {
  local name="$1"
  shift
  local log_file="$LOG_DIR/${name}.log"

  # Truncate previous logs to keep runs clean.
  : > "$log_file"

  echo "Starting $name..."
  nohup "$@" >> "$log_file" 2>&1 &
  local pid=$!
  echo "$name started (PID $pid). Logging to $log_file"
}

start_process "trial-registry-service" \
  uvicorn app:app --app-dir "$ROOT_DIR/trial-registry-backend" --host 0.0.0.0 --port 8002

start_process "ehr-service" \
  uvicorn app:app --app-dir "$ROOT_DIR/ehr-backend" --host 0.0.0.0 --port 8001

start_process "care-plan-agent" \
  python "$ROOT_DIR/care-plan-agent/simple_langgraph.py"

cat <<INFO

All services launched. Active logs:
  - $LOG_DIR/trial-registry-service.log
  - $LOG_DIR/ehr-service.log
  - $LOG_DIR/care-plan-agent.log

INFO
