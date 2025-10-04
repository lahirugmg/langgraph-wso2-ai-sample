# EHR + Trial Registry Service

Demo FastAPI backend that mocks a minimal electronic health record (EHR) API and a trial registry search endpoint.

## Setup
1. Ensure Python 3.10+ is available.
2. (Optional) Create a virtual environment.
3. `cp ehr-backend/.env.example ehr-backend/.env` and tweak origins/titles as needed.
4. From the repository root run `pip install -r ehr-backend/requirements.txt`.

## Run
```bash
uvicorn ehr-backend.app:app --reload
```
By default the service listens on <http://127.0.0.1:8000>.

## Endpoints
- `GET /patients/{id}/summary` — demographics, active problems, medications, vitals, and last HbA1c/eGFR.
- `GET /patients/{id}/labs?names=HbA1c,eGFR&last_n=3` — retrieve lab history (filters optional).
- `POST /orders/medication` — accept a medication order payload and return a draft confirmation.
- `POST /evidence/search` — accept clinical context (condition, comorbidities, age, geography) and return guideline/RCT IDs plus nearby trial suggestions.

Interactive docs are available at <http://127.0.0.1:8000/docs> when the server runs.
