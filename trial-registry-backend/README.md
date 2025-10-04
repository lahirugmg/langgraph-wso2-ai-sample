# Trial Registry Service

FastAPI service that stores mock clinical trials and exposes metadata for the Evidence Agent.

## Setup
1. Create/activate a Python 3.10+ virtual environment.
2. `cp trial-registry-backend/.env.example trial-registry-backend/.env` and adjust values as needed.
3. Install dependencies: `pip install -r trial-registry-backend/requirements.txt`.

## Run
```bash
uvicorn app:app --app-dir trial-registry-backend --reload --port 8002
```

The OpenAPI definition is available at `trial-registry-backend/openapi.yaml`.

## Endpoints
- `GET /services` — service capabilities overview.
- `GET /trials` — list seeded trials (includes `nct_id`, `site_distance_km`, and eligibility summary text).
- `GET /trials/{trial_id}` — retrieve a specific trial.
- `POST /trials` — create a new trial; `nct_id` auto-generates if omitted.

Interactive documentation: <http://127.0.0.1:8002/docs>.
