# Evidence Agent

LangGraph-based helper that queries the Trial Registry service, performs a lightweight synthetic "LLM" analysis, and exposes a REST endpoint for downstream care-plan orchestration.

## Setup
1. Install Python 3.10+.
2. `cp evidence-agent/.env.example evidence-agent/.env` and adjust values as needed.
3. `pip install -r evidence-agent/requirements.txt`

## Run
```bash
uvicorn evidence_agent:app --app-dir evidence-agent --reload --port 8003
```

By default the agent expects the Trial Registry backend to be reachable at `http://127.0.0.1:8002`. Override by setting `TRIAL_REGISTRY_URL`.

## API
- `POST /agents/evidence/search` — accepts `{age, diagnosis, egfr, comorbidities, geo}` and returns an `evidence_pack` with ranked trial matches, PICO-style grading, and risk/benefit summaries. When `OPENAI_API_KEY` (or `LLM_API_KEY`) is configured the agent calls the model to produce richer commentary; otherwise it falls back to heuristic scoring.

Set the following to enable LLM grading:

```bash
export OPENAI_API_KEY=sk-...
# Optional overrides
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_BASE_URL=https://api.openai.com/v1
```

The module still ships with a small `run_demo()` helper for quick CLI smoke tests (`python evidence-agent/evidence_agent.py`).
