"""Care-Plan Agent orchestrating EHR and Evidence services using LangGraph."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger("care_plan_agent")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] care-plan-agent: %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

EHR_SERVICE_URL = os.environ.get("EHR_SERVICE_URL", "http://127.0.0.1:8001")
EVIDENCE_AGENT_URL = os.environ.get("EVIDENCE_AGENT_URL", "http://127.0.0.1:8003")
DEFAULT_GEO = {
    "lat": float(os.environ.get("DEFAULT_GEO_LAT", 35.15)),
    "lon": float(os.environ.get("DEFAULT_GEO_LON", -90.05)),
    "radius_km": float(os.environ.get("DEFAULT_GEO_RADIUS", 25)),
}
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# API Manager OAuth2 configuration
API_MANAGER_BASE_URL = os.environ.get("API_MANAGER_BASE_URL")
API_MANAGER_CLIENT_ID = os.environ.get("API_MANAGER_CLIENT_ID")
API_MANAGER_CLIENT_SECRET = os.environ.get("API_MANAGER_CLIENT_SECRET")
API_MANAGER_TOKEN_ENDPOINT = os.environ.get(
    "API_MANAGER_TOKEN_ENDPOINT",
    f"{API_MANAGER_BASE_URL}/oauth2/token" if API_MANAGER_BASE_URL else None
)
API_MANAGER_CHAT_ENDPOINT = os.environ.get(
    "API_MANAGER_CHAT_ENDPOINT",
    f"{API_MANAGER_BASE_URL}/healthcare/openai-api/v1.0/chat/completions" if API_MANAGER_BASE_URL else None
)

# Cache for access token
_access_token_cache = {"token": None, "expires_at": 0}


class CarePlanRequestState(TypedDict):
    user_id: str
    patient_id: str
    question: str


class CarePlanState(TypedDict, total=False):
    request: CarePlanRequestState
    patient_summary: Dict[str, Any]
    evidence_pack: Dict[str, Any]
    plan_card: Dict[str, Any]
    llm_plan_card: Dict[str, Any]


def _diagnosis_from_problems(problems: List[str]) -> str:
    for item in problems:
        if "diabetes" in item.lower():
            return item
    return problems[0] if problems else "Unknown diagnosis"


def _get_access_token() -> Optional[str]:
    """Obtain OAuth2 access token using client credentials flow."""
    if not all([API_MANAGER_CLIENT_ID, API_MANAGER_CLIENT_SECRET, API_MANAGER_TOKEN_ENDPOINT]):
        logger.info("API Manager credentials not configured; skipping authentication")
        return None
    
    # Check if cached token is still valid (with 60 second buffer)
    import time
    if _access_token_cache["token"] and _access_token_cache["expires_at"] > time.time() + 60:
        logger.info("Using cached access token (valid for %d more seconds)", 
                   int(_access_token_cache["expires_at"] - time.time()))
        return _access_token_cache["token"]
    
    logger.info("Requesting new access token from API Manager endpoint: %s", API_MANAGER_TOKEN_ENDPOINT)
    logger.info("Using client_id: %s", API_MANAGER_CLIENT_ID[:10] + "..." if len(API_MANAGER_CLIENT_ID) > 10 else API_MANAGER_CLIENT_ID)
    
    try:
        response = requests.post(
            API_MANAGER_TOKEN_ENDPOINT,
            data={
                "grant_type": "client_credentials",
                "client_id": API_MANAGER_CLIENT_ID,
                "client_secret": API_MANAGER_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        
        logger.info("Token endpoint responded with status: %d", response.status_code)
        
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        
        # Cache the token
        _access_token_cache["token"] = access_token
        _access_token_cache["expires_at"] = time.time() + expires_in
        
        logger.info("✓ Access token obtained successfully (expires in %d seconds)", expires_in)
        logger.info("✓ Token cached for future requests")
        return access_token
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.exception("✗ Failed to obtain access token: %s", exc)
        return None


def _call_llm(messages: List[dict[str, str]]) -> Optional[str]:
    if not API_MANAGER_CHAT_ENDPOINT:
        logger.info("API Manager not configured; skipping LLM plan drafting")
        return None

    access_token = _get_access_token()
    if not access_token:
        logger.error("✗ Failed to obtain access token; skipping LLM plan drafting")
        return None

    logger.info("Calling LLM API via API Manager proxy")
    logger.info("  Endpoint: %s", API_MANAGER_CHAT_ENDPOINT)
    logger.info("  Model: %s", OPENAI_MODEL)
    logger.info("  Messages: %d", len(messages))
    
    headers = {
        "Authorization": f"Bearer {access_token[:20]}..." if len(access_token) > 20 else "Bearer ***",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        logger.info("Sending request to LLM API...")
        response = requests.post(
            API_MANAGER_CHAT_ENDPOINT,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        
        logger.info("LLM API responded with status: %d", response.status_code)
        
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        logger.info("✓ LLM response received successfully (%d chars)", len(content))
        logger.info("✓ LLM plan generation completed")
        return content
    except requests.HTTPError as exc:
        logger.error("✗ LLM API HTTP error: status=%d, response=%s", 
                    response.status_code, 
                    response.text[:200] if response.text else "empty")
        logger.exception("✗ LLM call failed: %s", exc)
        return None
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        logger.exception("✗ LLM call failed: %s", exc)
        return None


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            snippet = match.group(0)
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return None
    return None


def fetch_patient_summary(state: CarePlanState) -> CarePlanState:
    patient_id = state["request"]["patient_id"]
    logger.info("Fetching EHR summary for patient_id=%s", patient_id)
    try:
        response = requests.get(
            f"{EHR_SERVICE_URL.rstrip('/')}/patients/{patient_id}/summary", timeout=5
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Failed to fetch patient summary from EHR Service") from exc

    summary = response.json()
    logger.info(
        "EHR summary received for patient_id=%s (last_a1c=%s, last_egfr=%s)",
        patient_id,
        summary.get("last_a1c"),
        summary.get("last_egfr"),
    )
    return {"patient_summary": summary}


def call_evidence_agent(state: CarePlanState) -> CarePlanState:
    summary = state["patient_summary"]
    demographics = summary.get("demographics", {})
    problems = summary.get("problems", [])
    diagnosis = _diagnosis_from_problems(problems)

    payload = {
        "age": demographics.get("age"),
        "diagnosis": diagnosis,
        "egfr": summary.get("last_egfr"),
        "comorbidities": [p for p in problems if p != diagnosis],
        "geo": DEFAULT_GEO,
    }

    if payload["age"] is None or payload["egfr"] is None:
        raise RuntimeError("Patient summary missing age or eGFR for evidence lookup")

    logger.info(
        "Requesting evidence pack for patient_id=%s (diagnosis=%s, comorbidities=%s)",
        state["request"]["patient_id"],
        diagnosis,
        payload["comorbidities"],
    )
    try:
        response = requests.post(
            f"{EVIDENCE_AGENT_URL.rstrip('/')}/agents/evidence/search",
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Failed to reach Evidence Agent") from exc

    data = response.json()
    pack = data.get("evidence_pack", {})
    logger.info(
        "Evidence pack received: %d analyses, %d trials",
        len(pack.get("analyses", [])),
        len(pack.get("trials", [])),
    )
    return {"evidence_pack": pack}


def _derive_trial_matches(evidence_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    trials: List[Dict[str, Any]] = evidence_pack.get("trials", [])
    matches: List[Dict[str, Any]] = []
    for trial in trials:
        matches.append(
            {
                "title": trial.get("title"),
                "nct_id": trial.get("nct_id"),
                "site_distance_km": trial.get("site_distance_km"),
                "status": trial.get("status"),
                "why_match": trial.get("why_match"),
            }
        )
    return matches[:2]


def _draft_plan_card(state: CarePlanState) -> Dict[str, Any]:
    summary = state["patient_summary"]
    evidence_pack = state.get("evidence_pack", {})
    medications = summary.get("medications", [])
    problems = summary.get("problems", [])
    last_a1c = summary.get("last_a1c")
    last_egfr = summary.get("last_egfr")

    recommendation = "Start SGLT2 inhibitor (empagliflozin 10 mg daily)."
    rationale = (
        f"CKD stage 3 (eGFR {last_egfr}), A1c {last_a1c} on {', '.join(medications)}. "
        "Empagliflozin provides renal protection and CV benefit in similar cohorts."
    )
    alternatives = [
        "GLP-1 RA if weight reduction is prioritized or SGLT2 is contraindicated."
    ]
    safety_checks = [
        "Hold if eGFR <30 or acute illness; monitor for volume depletion.",
        "Repeat BMP in 2 weeks.",
    ]

    plan_card = {
        "recommendation": recommendation,
        "rationale": rationale,
        "alternatives": alternatives,
        "safety_checks": safety_checks,
        "orders": {
            "medication": {
                "name": "empagliflozin",
                "dose": "10 mg qday",
                "start_today": True,
            },
            "labs": [
                {"name": "BMP", "due_in_days": 14},
                {"name": "A1c", "due_in_days": 90},
            ],
        },
        "citations": [
            {"type": "RCT", "id": "EMPA-REG", "year": 2015},
            {"type": "Guideline", "org": "KDIGO", "year": 2022},
        ],
        "trial_matches": _derive_trial_matches(evidence_pack),
    }

    analyses = evidence_pack.get("analyses") or []
    if analyses:
        plan_card["evidence_highlights"] = [a.get("overall_summary") for a in analyses[:2]]

    return plan_card


def _merge_plan_cards(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    primary = primary or {}
    merged = fallback.copy()

    def _coerce_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    if isinstance(primary.get("recommendation"), str):
        merged["recommendation"] = primary["recommendation"]
    if isinstance(primary.get("rationale"), str):
        merged["rationale"] = primary["rationale"]
    if primary.get("alternatives"):
        merged["alternatives"] = [str(item) for item in _coerce_list(primary["alternatives"])]
    if primary.get("safety_checks"):
        merged["safety_checks"] = [str(item) for item in _coerce_list(primary["safety_checks"])]

    if "orders" in primary and isinstance(primary["orders"], dict):
        merged_orders = merged.get("orders", {}).copy()
        primary_orders = primary["orders"]

        if isinstance(primary_orders.get("medication"), dict):
            med = primary_orders["medication"]
            name = med.get("name") or med.get("drug") or med.get("medication")
            dose = med.get("dose") or med.get("strength")
            start_today = med.get("start_today")
            medication: Dict[str, Any] = merged_orders.get("medication", {}).copy()
            if name:
                medication["name"] = name
            if dose:
                medication["dose"] = dose
            if isinstance(start_today, bool):
                medication["start_today"] = start_today
            merged_orders["medication"] = medication

        if primary_orders.get("labs"):
            labs: List[Dict[str, Any]] = []
            for lab in _coerce_list(primary_orders["labs"]):
                if not isinstance(lab, dict):
                    continue
                name = lab.get("name") or lab.get("test")
                due = lab.get("due_in_days")
                if due is None and lab.get("frequency"):
                    freq = str(lab["frequency"]).lower()
                    if "week" in freq:
                        due = 7
                    elif "month" in freq:
                        due = 30
                    elif "day" in freq:
                        due = 1
                if name and isinstance(due, (int, float)):
                    labs.append({"name": str(name), "due_in_days": int(due)})
            if labs:
                merged_orders["labs"] = labs

        merged["orders"] = merged_orders

    if primary.get("citations"):
        citations: List[Dict[str, Any]] = []
        for citation in _coerce_list(primary["citations"]):
            if not isinstance(citation, dict):
                continue
            ctype = citation.get("type") or citation.get("category") or "Reference"
            entry = CitationModel(
                type=str(ctype),
                id=citation.get("id") or citation.get("title"),
                org=citation.get("org") or citation.get("organization"),
                year=citation.get("year"),
            ).dict(exclude_none=True)
            citations.append(entry)
        if citations:
            merged["citations"] = citations

    if primary.get("trial_matches"):
        existing_matches = [m for m in merged.get("trial_matches", []) if isinstance(m, dict)]
        primary_trials = [t for t in _coerce_list(primary["trial_matches"]) if isinstance(t, dict)]
        combined: List[Dict[str, Any]] = []

        def _pop_candidate(base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            title = str(base.get("title", "")).lower()
            nct_id = str(base.get("nct_id", "")).lower()
            for idx, candidate in enumerate(primary_trials):
                cand_title = str(candidate.get("title", "")).lower()
                cand_nct = str(candidate.get("nct_id", "")).lower()
                if (nct_id and cand_nct and cand_nct == nct_id) or (
                    title and cand_title and cand_title == title
                ):
                    return primary_trials.pop(idx)
            return None

        for base in existing_matches:
            candidate = _pop_candidate(base) or {}
            merged_match = TrialMatchModel(
                title=candidate.get("title") or base.get("title"),
                nct_id=candidate.get("nct_id") or base.get("nct_id"),
                site_distance_km=
                candidate.get("site_distance_km")
                if isinstance(candidate.get("site_distance_km"), (int, float))
                else base.get("site_distance_km"),
                status=candidate.get("status") or base.get("status"),
                why_match=candidate.get("why_match")
                or candidate.get("summary")
                or base.get("why_match")
                or base.get("summary"),
            ).dict()
            combined.append(merged_match)

        for candidate in primary_trials:
            combined.append(
                TrialMatchModel(
                    title=candidate.get("title"),
                    nct_id=candidate.get("nct_id"),
                    site_distance_km=candidate.get("site_distance_km"),
                    status=candidate.get("status"),
                    why_match=candidate.get("why_match") or candidate.get("summary"),
                ).dict()
            )

        if combined:
            merged["trial_matches"] = combined

    if primary.get("evidence_highlights"):
        merged["evidence_highlights"] = [
            str(item) for item in _coerce_list(primary["evidence_highlights"])
        ]

    for optional_key in ["llm_model", "generated_at", "notes"]:
        if primary.get(optional_key):
            merged[optional_key] = primary[optional_key]

    return merged


def llm_plan_card(state: CarePlanState) -> CarePlanState:
    summary = state.get("patient_summary")
    evidence_pack = state.get("evidence_pack", {})
    if not summary:
        return {}

    messages = [
        {
            "role": "system",
            "content": (
                "You are a clinical decision support assistant. Respond ONLY with JSON "
                "containing a key 'plan_card'. The plan card must include recommendation, "
                "rationale, alternatives (array), safety_checks (array), orders (medication+labs), "
                "citations (array of objects), trial_matches (array of objects), and optional "
                "evidence_highlights."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "patient_summary": summary,
                    "evidence_pack": evidence_pack,
                },
                default=str,
            ),
        },
    ]

    raw = _call_llm(messages)
    if not raw:
        return {}

    parsed = _extract_json_block(raw) or {}
    logger.info(
        "LLM plan card parsed with keys=%s",
        list(parsed.keys()),
    )
    plan_candidate = parsed.get("plan_card") or parsed
    if not isinstance(plan_candidate, dict):
        return {}

    plan_candidate.setdefault("llm_model", OPENAI_MODEL)
    plan_candidate.setdefault("generated_at", datetime.utcnow().isoformat() + "Z")
    if parsed.get("notes"):
        plan_candidate.setdefault("notes", parsed["notes"])

    logger.info(
        "LLM produced plan card keys=%s",
        list(plan_candidate.keys()),
    )
    return {"llm_plan_card": plan_candidate}


def assemble_plan(state: CarePlanState) -> CarePlanState:
    heuristic = _draft_plan_card(state)
    llm_card = state.get("llm_plan_card")
    if llm_card:
        plan_card = _merge_plan_cards(llm_card, heuristic)
        logger.info(
            "Merged LLM and heuristic plan cards for patient_id=%s",
            state["request"]["patient_id"],
        )
    else:
        plan_card = heuristic
        logger.info(
            "Using heuristic-only plan card for patient_id=%s",
            state["request"]["patient_id"],
        )

    return {"plan_card": plan_card}


def build_graph() -> StateGraph:
    graph = StateGraph(CarePlanState)
    graph.add_node("fetch_patient_summary", fetch_patient_summary)
    graph.add_node("call_evidence_agent", call_evidence_agent)
    graph.add_node("llm_plan_card", llm_plan_card)
    graph.add_node("assemble_plan", assemble_plan)
    graph.set_entry_point("fetch_patient_summary")
    graph.add_edge("fetch_patient_summary", "call_evidence_agent")
    graph.add_edge("call_evidence_agent", "llm_plan_card")
    graph.add_edge("llm_plan_card", "assemble_plan")
    graph.add_edge("assemble_plan", END)
    return graph.compile()


CARE_PLAN_GRAPH = build_graph()


# ---------------------------------------------------------------------------
# FastAPI wiring
# ---------------------------------------------------------------------------
class CarePlanRequestModel(BaseModel):
    user_id: str
    patient_id: str
    question: str


class MedicationOrderModel(BaseModel):
    name: str
    dose: str
    start_today: bool = Field(True, description="Flag to start medication immediately")


class LabOrderModel(BaseModel):
    name: str
    due_in_days: int


class CitationModel(BaseModel):
    type: str
    id: Optional[str] = None
    org: Optional[str] = None
    year: Optional[int] = None


class OrdersModel(BaseModel):
    medication: MedicationOrderModel
    labs: List[LabOrderModel]


class TrialMatchModel(BaseModel):
    title: Optional[str]
    nct_id: Optional[str]
    site_distance_km: Optional[float]
    status: Optional[str]
    why_match: Optional[str]


class PlanCardModel(BaseModel):
    recommendation: str
    rationale: str
    alternatives: List[str]
    safety_checks: List[str]
    orders: OrdersModel
    citations: List[CitationModel]
    trial_matches: List[TrialMatchModel]
    evidence_highlights: Optional[List[str]] = None
    llm_model: Optional[str] = None
    generated_at: Optional[str] = None
    notes: Optional[str] = None


class CarePlanResponseModel(BaseModel):
    patient_id: str
    plan_card: PlanCardModel


app = FastAPI(
    title="Care-Plan Agent",
    description="Orchestrates EHR context, evidence synthesis, and returns a plan card.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/agents/care-plan/recommendation", response_model=CarePlanResponseModel)
def recommend_care_plan(payload: CarePlanRequestModel) -> CarePlanResponseModel:
    try:
        result = CARE_PLAN_GRAPH.invoke({"request": payload.dict()})
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    plan_card = result.get("plan_card")
    if not plan_card:
        raise HTTPException(status_code=500, detail="Plan generation failed")

    return CarePlanResponseModel(patient_id=payload.patient_id, plan_card=PlanCardModel.parse_obj(plan_card))


@app.get("/health", summary="Basic health-check endpoint")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


def run_demo() -> None:
    request = CarePlanRequestModel(
        user_id="dr_patel",
        patient_id="12873",
        question="Add-on to metformin for T2D with CKD stage 3; show supporting evidence and local recruiting trials.",
    )
    response = recommend_care_plan(request)
    print(response.json(indent=2))


if __name__ == "__main__":
    run_demo()
