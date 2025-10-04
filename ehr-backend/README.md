# EHR Service

FastAPI backend that exposes a minimal electronic health record API used by the LangGraph agents.

## Setup
1. Ensure Python 3.10+ is available.
2. (Optional) Create a virtual environment.
3. `cp ehr-backend/.env.example ehr-backend/.env` and adjust environment variables as needed.
4. From the repository root run `pip install -r ehr-backend/requirements.txt`.

## Run
```bash
uvicorn app:app --app-dir ehr-backend --reload --port 8001
```

The OpenAPI contract is available in `ehr-backend/openapi.yaml`. Interactive docs are served at <http://127.0.0.1:8001/docs> when the server is running.

## Endpoints
- `GET /patients/{id}/summary` — demographics, problem list, medications, vitals, and latest HbA1c/eGFR.
- `GET /patients/{id}/labs?names=HbA1c,eGFR&last_n=6` — retrieve lab history with optional filters.
- `POST /orders/medication` — accept a medication order payload and return a draft acknowledgement.
