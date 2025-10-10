#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
VENV_DIR="$ROOT_DIR/venv"
mkdir -p "$LOG_DIR"

setup_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating Python virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
  fi
  
  echo "Activating Python virtual environment..."
  source "$VENV_DIR/bin/activate"
  
  pip install --upgrade pip
}

start_process() {
  local name="$1"
  shift
  local log_file="$LOG_DIR/${name}.log"

  : > "$log_file"
  echo "Starting $name..."
  nohup "$@" >> "$log_file" 2>&1 &
  local pid=$!
  echo "$name started (PID $pid). Logging to $log_file"
}

ensure_python_requirements() {
  local service_name="$1"
  local req_path="$2"

  if [[ -f "$req_path" ]]; then
    echo "Installing Python dependencies for $service_name..."
    pip install -r "$req_path" > /dev/null 2>&1 || {
      echo "Failed installing dependencies for $service_name" >&2
      exit 1
    }
  fi
}

setup_venv

# Only install dependencies for the agent services (backends are now MCP-based)
ensure_python_requirements "evidence-agent" "$ROOT_DIR/evidence-agent/requirements.txt"
ensure_python_requirements "care-plan-agent" "$ROOT_DIR/care-plan-agent/requirements.txt"

# Note: EHR and Trial Registry services are now provided via MCP (Model Context Protocol)
# No need to start Python backend services - agents communicate directly with MCP servers

start_process "evidence-agent-service" \
  "$VENV_DIR/bin/uvicorn" evidence_agent:app --app-dir "$ROOT_DIR/evidence-agent" --host 0.0.0.0 --port 8003

start_process "care-plan-agent-service" \
  "$VENV_DIR/bin/uvicorn" app:app --app-dir "$ROOT_DIR/care-plan-agent" --host 0.0.0.0 --port 8004

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  npm --prefix "$ROOT_DIR/frontend" install > /dev/null 2>&1
fi

start_process "frontend" \
  npm --prefix "$ROOT_DIR/frontend" run dev

echo "Frontend available at http://127.0.0.1:8080"
if [[ -z "${OPENAI_API_KEY:-}" && -z "${LLM_API_KEY:-}" ]]; then
  echo "(Tip) Set OPENAI_API_KEY or LLM_API_KEY to enable LLM-backed nodes."
fi

cat <<INFO

All services launched. Active logs:
  - $LOG_DIR/evidence-agent-service.log
  - $LOG_DIR/care-plan-agent-service.log
  - $LOG_DIR/frontend.log


INFO
