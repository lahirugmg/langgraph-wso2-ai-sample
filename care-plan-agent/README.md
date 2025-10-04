# Care-Plan Agent

LangGraph-powered orchestrator that pulls context from the EHR service, asks the Evidence Agent for current trials/guidelines, performs a mock LLM planning step, and returns a single "plan card" for the UI.

## Setup
1. Install Python 3.10+.
2. `cp care-plan-agent/.env.example care-plan-agent/.env` and adjust values as needed.
3. `pip install -r care-plan-agent/requirements.txt`

## Run
```bash
uvicorn app:app --app-dir care-plan-agent --reload --port 8004
```

Environment variables:
- `EHR_SERVICE_URL` — base URL for the EHR backend (default `http://127.0.0.1:8001`).
- `EVIDENCE_AGENT_URL` — base URL for the Evidence Agent (default `http://127.0.0.1:8003`).
- `DEFAULT_GEO_LAT` / `DEFAULT_GEO_LON` / `DEFAULT_GEO_RADIUS` — adjust the location payload sent to the Evidence Agent.
- `OPENAI_API_KEY` — enables the LLM plan-card node to draft recommendations. Optional `OPENAI_MODEL` / `OPENAI_BASE_URL` override the defaults.

## API
- `POST /agents/care-plan/recommendation`
  - Request: `{"user_id": "dr_patel", "patient_id": "12873", "question": "…"}`
  - Response: `{ "patient_id": "12873", "plan_card": { … } }`

The response embeds recommendation text, safety checks, draft orders, citations, and trial matches chosen from the Evidence Agent output.
