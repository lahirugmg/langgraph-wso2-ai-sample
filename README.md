# langgraph-wso2-ai-sample

Minimal workspace containing LangGraph agents plus REST backends for clinical research, EHR, and an accompanying clinician UI.

## Prerequisites
- Python 3.10 or newer (virtual environments recommended)

## Services & Agents

> **Note**: EHR and Trial Registry services are now provided via **MCP (Model Context Protocol)** servers with OAuth2 authentication. The Python backend implementations have been removed as we're fully dependent on MCP services.

### MCP Services (External)
The following services are accessed via MCP protocol:

#### **EHR MCP Service**
- Provides patient demographics, conditions, medications, and lab results
- Endpoint: `EHR_MCP_URL` (configured in `.env`)
- MCP Tool: `getPatientsIdSummary`
- Authentication: OAuth2 client credentials flow

#### **Trial Registry MCP Service**
- Supplies structured clinical trial data
- Endpoint: `TRIAL_REGISTRY_MCP_URL` (configured in `.env`)
- MCP Tools: `get`, `getTrialid`, `post`
- Authentication: OAuth2 client credentials flow

## Agent Responsibilities
1. **Planner (Care-Plan) Agent**
   - Pulls patient context from the EHR platform (labs such as A1c, renal function, current medications).
   - Identifies the clinician’s intent (care-plan vs. research question) and routes the workflow accordingly.
   - Delegates evidence gathering to the Evidence Agent when building a full care plan.
2. **Evidence Agent**
   - Finds and summarizes relevant trials and guideline snippets through the Trial Registry MCP server.
   - Returns a structured `evidence_pack` that captures trial suitability, benefit, and risk signals.
3. **Planner Agent + LLM (via Gateway)**
   - Synthesizes the data into a structured JSON `plan_card` (recommendation, rationale, safety checks, orders, citations).
   - Falls back to heuristic defaults when the upstream LLM call times out or is disabled.
   - Produces a trial-focused plan when the incoming question is solely about research enrollment.

### Evidence Agent
1. `cp evidence-agent/.env.example evidence-agent/.env`
2. `pip install -r evidence-agent/requirements.txt`
3. `uvicorn evidence_agent:app --app-dir evidence-agent --reload --port 8003`

`POST /agents/evidence/search` accepts `{age, diagnosis, egfr, comorbidities, geo}` and returns an `evidence_pack` with ranked trial matches, PICO-style grading, and risk/benefit notes. The agent uses LangGraph to fetch the Trial Registry service and perform the synthetic analysis step.

### Care-Plan Agent
1. `cp care-plan-agent/.env.example care-plan-agent/.env`
2. `pip install -r care-plan-agent/requirements.txt`
3. `uvicorn app:app --app-dir care-plan-agent --reload --port 8004`

`POST /agents/care-plan/recommendation` now supports two paths:
- **Full care-plan route** – Detects a clinical management question, fetches EHR context via MCP, asks the Evidence Agent for ranked trials, then drafts a plan card with the LLM (falling back to heuristics on timeout).
- **Trial-only route** – Detects research-only questions, queries the Trial Registry MCP directly (LLM-assisted parameter mapping), and synthesizes a trial-focused plan card without the Evidence Agent.

Example request:
```json
{
  "user_id": "dr_patel",
  "patient_id": "12873",
  "question": "Add-on to metformin for T2D with CKD stage 3; show supporting evidence and local recruiting trials."
}
```

### Frontend (Doctor UI)
1. `cd frontend && cp .env.local.example .env.local`
2. (Optional) `cp .env.example .env` for shared tooling or deployment.
3. Update URLs/tokens in the env files as needed (e.g., `CARE_PLAN_URL`, `EHR_URL`, `OPENAI_API_KEY`).
4. `npm install`
5. `npm run dev` (Next.js on <http://127.0.0.1:8080>)

The portal calls the Care-Plan Agent via `/api/care-plan`, fetches labs through `/api/labs`, and offers an evidence preview tab backed by `/api/evidence`.

### Architecture Overview
- **Frontend (Next.js)** – orchestrates the doctor workflow and keeps credentials server-side. It talks only to internal `/api/*` routes.
- **Care-Plan Agent (LangGraph)** – fetches EHR summary via MCP ➜ requests the Evidence Agent ➜ invokes an optional LLM node to draft the plan card ➜ merges with guard-rail heuristics before responding.
- **Evidence Agent (LangGraph)** – pulls candidate trials from Trial Registry via MCP ➜ optional LLM node grades relevance (PICO, risk/benefit) ➜ falls back to heuristics when no model is configured.
- **EHR MCP Service** (External) – provides patient summaries, labs, and order capabilities via Model Context Protocol.
- **Trial Registry MCP Service** (External) – supplies structured trial data via Model Context Protocol.

Set `OPENAI_API_KEY` plus optional `OPENAI_MODEL`/`OPENAI_BASE_URL` to enable the LLM nodes. Without these variables the agents happily revert to heuristic logic, keeping local demos self-contained.

![FHIR-aligned flow](media/FHIR_flow.png)

## Test the Care-Plan Agent
1. Ensure MCP services are configured (see **MCP Integration** section below).
2. Run the agents: `./start_services.sh`
3. Trigger the agent: `curl -X POST http://127.0.0.1:8004/agents/care-plan/recommendation \
   -H 'Content-Type: application/json' \
   -d '{"user_id":"dr_patel","patient_id":"12873","question":"Add-on to metformin..."}'`
4. Verify the JSON response contains a `plan_card.recommendation` recommending an SGLT2 inhibitor and two local trial matches.

For ad-hoc checks, run `python care-plan-agent/simple_langgraph.py` to confirm the sample LangGraph loop still operates.

## Start / Stop everything with scripts
- Start: `./start_services.sh` (launches agents and frontend; logs streamed to `logs/<service>.log`).
- Stop: `./stop_services.sh` (gracefully terminates everything and optionally deletes the `logs/` directory).

**Note**: EHR and Trial Registry services are accessed via external MCP servers and do not need to be started locally.

## MCP Integration

The agents **require** consuming backend services via **Model Context Protocol (MCP)** with OAuth2 authentication:

- **Care Plan Agent**: Consumes EHR data via MCP gateway (`EHR_MCP_URL`)
- **Evidence Agent**: Consumes trials via MCP gateway (`TRIAL_REGISTRY_MCP_URL`)
- **Authentication**: OAuth2 client credentials flow with token caching
- **Schema Transformation**: Automatic conversion between Ballerina MCP and Python backend formats
- **No Fallback**: Python backend services have been removed - MCP is the only data source

### Configuration (.env files)
```bash
# MCP Gateway OAuth2 Settings
MCP_GATEWAY_CLIENT_ID=your_client_id
MCP_GATEWAY_CLIENT_SECRET=your_client_secret
MCP_GATEWAY_TOKEN_ENDPOINT=https://gateway/oauth2/token

# MCP Server URLs
EHR_MCP_URL=https://gateway/clinicagent/ehr-mcp/v1.0/mcp
TRIAL_REGISTRY_MCP_URL=https://gateway/clinicagent/trial-registry-mcp/v1.0/mcp
```

### Key Features
- ✅ **OAuth2 Token Caching**: Reduces authentication overhead (3600s TTL)
- ✅ **Schema Transformation**: Maps Ballerina MCP format (camelCase, nested objects) to Python format (snake_case, flat values)
- ✅ **JSON-RPC 2.0**: Proper MCP protocol implementation
- ✅ **MCP-Only Architecture**: No Python backend dependencies - fully cloud-native
- ✅ **Detailed Logging**: Comprehensive JSON-RPC request/response logging for debugging

## FHIR Relevance
- **EHR Service** — could emit FHIR `Patient`, `Condition`, `Observation`, and `MedicationRequest` resources instead of ad-hoc JSON.
- **Trial Registry Service** — trial payloads map cleanly to FHIR `ResearchStudy` / `ResearchSubject` resources, easing Evidence Agent ingestion.
- **Evidence Agent** — can translate graded outputs into `EvidenceReport` or `DocumentReference` resources for system-of-record storage.
- **Care-Plan Agent** — current plan card is JSON but can be expressed as a FHIR `CarePlan` or `ServiceRequest` bundle to plug into downstream EHRs.
- **Frontend** — consumes the REST APIs today, but could directly interact with FHIR endpoints for standards-aligned read/write operations.
