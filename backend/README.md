# Clinical Research Services API

Simple FastAPI service that exposes REST endpoints for clinical trial management.

## Setup
1. Create and activate a Python 3.10+ virtual environment.
2. Install dependencies: `pip install -r backend/requirements.txt` from the repo root.

## Run the service
- Development server: `uvicorn backend.app:app --reload`
- By default the API listens on `http://127.0.0.1:8000`.

## Available endpoints
- `GET /services` — overview of supported clinical research capabilities.
- `GET /trials` — list the seeded clinical trials.
- `GET /trials/{trial_id}` — fetch a single trial.
- `POST /trials` — create a new trial (JSON body matching the schema).

Interactive documentation is available at `http://127.0.0.1:8000/docs` once the server is running.
