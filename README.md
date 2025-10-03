# langgraph-wso2-ai-sample

Minimal workspace with a single LangGraph example placed under `agent/`.

## Prerequisites
- Python 3.10 or newer
- `pip install langgraph`

## Run the sample
1. Change into this directory.
2. Execute `python agent/simple_langgraph.py`.
3. You should see the counter output for each graph step until it reaches three.

Feel free to modify the state or the transition logic inside `agent/simple_langgraph.py` to experiment with LangGraph flows.

## Clinical Research Services API
A small FastAPI service lives in `backend/` and exposes REST endpoints for managing clinical trials.

- Install requirements: `pip install -r backend/requirements.txt`
- Start the server: `uvicorn backend.app:app --reload`
- Explore the docs: `http://127.0.0.1:8000/docs`

Endpoints include a `GET /services` overview plus CRUD-style trial operations (`GET /trials`, `GET /trials/{id}`, `POST /trials`). See `backend/README.md` for details.
