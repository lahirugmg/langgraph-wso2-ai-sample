# langgraph-wso2-ai-sample

Minimal workspace containing a LangGraph sample agent plus REST backends for clinical research and EHR demonstrations.

## Prerequisites
- Python 3.10 or newer (virtual environments recommended)

## Run the LangGraph agent
1. Install LangGraph: `pip install langgraph`
2. From the repo root, execute: `python care-plan-agent/simple_langgraph.py`
3. Watch the console output as the counter advances to three.

Feel free to modify the state or the transition logic inside `care-plan-agent/simple_langgraph.py` to experiment with LangGraph flows.

## Run the Trial Registry Service
1. Install dependencies: `pip install -r trial-registry-backend/requirements.txt`
2. Start the server (use port 8002 to avoid clashes): `uvicorn trial-registry-backend.app:app --reload --port 8002`
3. Open `http://127.0.0.1:8002/docs` for interactive documentation.

### Quick smoke tests
```bash
curl http://127.0.0.1:8002/services
curl http://127.0.0.1:8002/trials
curl -X POST http://127.0.0.1:8002/trials \
  -H 'Content-Type: application/json' \
  -d '{"title":"Demo Study","condition":"Hypertension","phase":"Phase I","status":"Recruiting","principal_investigator":"Dr. Ada","start_date":"2024-01-01"}'
```

## Run the EHR Service
1. Install dependencies: `pip install -r ehr-backend/requirements.txt`
2. Start the server (port 8001 keeps things separated): `uvicorn ehr-backend.app:app --reload --port 8001`
3. Open `http://127.0.0.1:8001/docs` to try the interactive schema.

### Quick smoke tests
```bash
curl http://127.0.0.1:8001/patients/12345/summary
curl "http://127.0.0.1:8001/patients/12345/labs?names=HbA1c,eGFR&last_n=2"
curl -X POST http://127.0.0.1:8001/orders/medication \
  -H 'Content-Type: application/json' \
  -d '{"patient_id":"12345","medication":"Empagliflozin","dose":"10 mg","route":"PO","frequency":"Once daily"}'
```
