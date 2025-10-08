"""LangGraph-driven Evidence Agent exposed via FastAPI.

The agent queries the Trial Registry service, applies a lightweight heuristic
"LLM" grading step, and returns a structured evidence pack that downstream
services (e.g., care-plan agent) can consume.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, List, Optional, TypedDict

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger("evidence_agent")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] evidence-agent: %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

def _strip_quotes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


TRIAL_REGISTRY_URL = _strip_quotes(os.environ.get("TRIAL_REGISTRY_URL")) or "http://127.0.0.1:8002"
OPENAI_MODEL = _strip_quotes(os.environ.get("OPENAI_MODEL")) or "gpt-4o-mini"

# API Manager OAuth2 configuration
API_MANAGER_BASE_URL = _strip_quotes(os.environ.get("API_MANAGER_BASE_URL"))
API_MANAGER_CLIENT_ID = _strip_quotes(os.environ.get("API_MANAGER_CLIENT_ID"))
API_MANAGER_CLIENT_SECRET = _strip_quotes(os.environ.get("API_MANAGER_CLIENT_SECRET"))
API_MANAGER_TOKEN_ENDPOINT = _strip_quotes(
    os.environ.get(
        "API_MANAGER_TOKEN_ENDPOINT",
        f"{API_MANAGER_BASE_URL}/oauth2/token" if API_MANAGER_BASE_URL else None
    )
) or None
API_MANAGER_CHAT_ENDPOINT = _strip_quotes(
    os.environ.get(
        "API_MANAGER_CHAT_ENDPOINT",
        f"{API_MANAGER_BASE_URL}/healthcare/openai-api/v1.0/chat/completions" if API_MANAGER_BASE_URL else None
    )
) or None

# MCP Gateway configuration
MCP_GATEWAY_CLIENT_ID = _strip_quotes(os.environ.get("MCP_GATEWAY_CLIENT_ID"))
MCP_GATEWAY_CLIENT_SECRET = _strip_quotes(os.environ.get("MCP_GATEWAY_CLIENT_SECRET"))
MCP_GATEWAY_SCOPE = _strip_quotes(os.environ.get("MCP_GATEWAY_SCOPE"))
MCP_GATEWAY_TOKEN_ENDPOINT = _strip_quotes(os.environ.get("MCP_GATEWAY_TOKEN_ENDPOINT")) or None

EHR_MCP_URL = _strip_quotes(os.environ.get("EHR_MCP_URL"))
TRIAL_REGISTRY_MCP_URL = _strip_quotes(os.environ.get("TRIAL_REGISTRY_MCP_URL"))

# Cache for access token
_access_token_cache = {"token": None, "expires_at": 0}
_mcp_access_token_cache = {"token": None, "expires_at": 0}


def _get_mcp_access_token() -> Optional[str]:
    """Obtain OAuth2 access token for MCP gateway using client credentials flow."""
    if not all([MCP_GATEWAY_CLIENT_ID, MCP_GATEWAY_CLIENT_SECRET, MCP_GATEWAY_TOKEN_ENDPOINT]):
        logger.info("MCP Gateway credentials not configured; skipping MCP authentication")
        return None
    
    # Check if cached token is still valid (with 60 second buffer)
    import time
    if _mcp_access_token_cache["token"] and _mcp_access_token_cache["expires_at"] > time.time() + 60:
        logger.info("Using cached MCP access token (valid for %d more seconds)", 
                   int(_mcp_access_token_cache["expires_at"] - time.time()))
        return _mcp_access_token_cache["token"]
    
    logger.info("Requesting new MCP access token from endpoint: %s", MCP_GATEWAY_TOKEN_ENDPOINT)
    logger.info("Using MCP client_id: %s", MCP_GATEWAY_CLIENT_ID[:10] + "..." if len(MCP_GATEWAY_CLIENT_ID) > 10 else MCP_GATEWAY_CLIENT_ID)
    
    try:
        data = {
            "grant_type": "client_credentials",
            "client_id": MCP_GATEWAY_CLIENT_ID,
            "client_secret": MCP_GATEWAY_CLIENT_SECRET,
        }
        if MCP_GATEWAY_SCOPE:
            data["scope"] = MCP_GATEWAY_SCOPE
            
        response = requests.post(
            MCP_GATEWAY_TOKEN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        
        logger.info("MCP token endpoint responded with status: %d", response.status_code)
        
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        
        # Cache the token
        _mcp_access_token_cache["token"] = access_token
        _mcp_access_token_cache["expires_at"] = time.time() + expires_in
        
        logger.info("✓ MCP access token obtained successfully (expires in %d seconds)", expires_in)
        logger.info("✓ MCP token cached for future requests")
        return access_token
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.exception("✗ Failed to obtain MCP access token: %s", exc)
        return None


def _call_mcp_tool(mcp_url: str, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call an MCP tool with given arguments."""
    access_token = _get_mcp_access_token()
    if not access_token:
        logger.error("✗ Failed to obtain MCP access token; skipping MCP tool call")
        return None
    
    logger.info("Calling MCP tool '%s' at %s", tool_name, mcp_url)
    logger.info("  Arguments: %s", arguments)
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    try:
        logger.info("Sending MCP tool request...")
        response = requests.post(
            mcp_url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        
        logger.info("MCP tool responded with status: %d", response.status_code)
        
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            logger.error("✗ MCP tool error: %s", data["error"])
            return None
        
        result = data.get("result")
        logger.info("✓ MCP tool '%s' executed successfully", tool_name)
        return result
        
    except requests.HTTPError as exc:
        logger.error("✗ MCP tool HTTP error: status=%d, response=%s", 
                    response.status_code, 
                    response.text[:200] if response.text else "empty")
        logger.exception("✗ MCP tool call failed: %s", exc)
        return None
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.exception("✗ MCP tool call failed: %s", exc)
        return None


def _list_mcp_tools(mcp_url: str) -> Optional[List[Dict[str, Any]]]:
    """List available tools from an MCP server."""
    access_token = _get_mcp_access_token()
    if not access_token:
        logger.error("✗ Failed to obtain MCP access token; skipping MCP tools list")
        return None
    
    logger.info("Listing MCP tools from %s", mcp_url)
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(
            mcp_url,
            headers=headers,
            json=payload,
            timeout=10,
        )
        
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            logger.error("✗ MCP tools list error: %s", data["error"])
            return None
        
        tools = data.get("result", {}).get("tools", [])
        logger.info("✓ Found %d MCP tools", len(tools))
        for tool in tools:
            logger.info("  - %s: %s", tool.get("name", "Unknown"), tool.get("description", "No description"))
        
        return tools
        
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.exception("✗ Failed to list MCP tools: %s", exc)
        return None


class GeoContext(TypedDict):
    lat: float
    lon: float
    radius_km: float


class PatientContext(TypedDict):
    age: int
    diagnosis: str
    egfr: float
    comorbidities: List[str]
    geo: Optional[GeoContext]


class TrialMatch(TypedDict, total=False):
    id: int
    nct_id: str
    title: str
    condition: str
    phase: str
    status: str
    site_distance_km: Optional[float]
    suitability: float
    why_match: Optional[str]


class EvidenceAnalysis(TypedDict):
    trial_id: int
    trial_title: str
    pico_grade: str
    benefit_summary: str
    risk_summary: str
    overall_summary: str


class EvidencePack(TypedDict, total=False):
    patient: PatientContext
    analyses: List[EvidenceAnalysis]
    trials: List[TrialMatch]
    llm_model: str
    generated_at: str
    notes: Optional[str]


class EvidenceState(TypedDict, total=False):
    context: PatientContext
    trial_matches: List[TrialMatch]
    analyses: List[EvidenceAnalysis]
    evidence_pack: EvidencePack
    llm_notes: Optional[str]


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


def _get_mcp_access_token() -> Optional[str]:
    """Fetch bearer token from the MCP gateway using client credentials."""
    if not all(
        [
            MCP_GATEWAY_CLIENT_ID,
            MCP_GATEWAY_CLIENT_SECRET,
            MCP_GATEWAY_TOKEN_ENDPOINT,
        ]
    ):
        logger.info("MCP gateway credentials not fully configured")
        return None

    import time

    if _mcp_access_token_cache["token"] and _mcp_access_token_cache["expires_at"] > time.time() + 60:
        logger.debug(
            "Using cached MCP gateway token (valid for %d more seconds)",
            int(_mcp_access_token_cache["expires_at"] - time.time()),
        )
        return _mcp_access_token_cache["token"]

    logger.info("Requesting MCP gateway token from %s", MCP_GATEWAY_TOKEN_ENDPOINT)
    data = {
        "grant_type": "client_credentials",
        "client_id": MCP_GATEWAY_CLIENT_ID,
        "client_secret": MCP_GATEWAY_CLIENT_SECRET,
    }
    if MCP_GATEWAY_SCOPE:
        data["scope"] = MCP_GATEWAY_SCOPE

    try:
        response = requests.post(
            MCP_GATEWAY_TOKEN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        logger.info("MCP gateway token response status: %d", response.status_code)
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)

        _mcp_access_token_cache["token"] = access_token
        _mcp_access_token_cache["expires_at"] = time.time() + expires_in
        return access_token
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.exception("✗ Failed to obtain MCP gateway token: %s", exc)
        return None


def _log_mcp_request(method: str, url: str, headers: Optional[dict[str, str]], payload: Optional[Any]) -> None:
    """Emit a structured log entry for outgoing MCP calls without leaking secrets."""
    redacted_headers: dict[str, Any] = {}
    for key, value in (headers or {}).items():
        if isinstance(value, str) and key.lower() == "authorization":
            token_len = len(value)
            redacted_headers[key] = f"Bearer <redacted len={token_len}>"
        else:
            redacted_headers[key] = value

    if payload is None:
        payload_preview = None
    elif isinstance(payload, (dict, list)):
        serialized = json.dumps(payload)
        payload_preview = serialized[:500] + ("..." if len(serialized) > 500 else "")
    else:
        text = str(payload)
        payload_preview = text[:500] + ("..." if len(text) > 500 else "")

    logger.info(
        "MCP request prepared: method=%s url=%s headers=%s payload=%s",
        method,
        url,
        redacted_headers,
        payload_preview,
    )


def _call_llm(messages: List[dict[str, str]]) -> Optional[str]:
    """Call a chat-completions style LLM endpoint if credentials exist.

    Returns the raw model string or ``None`` when unavailable/failing so callers
    can gracefully fall back to heuristic behaviour.
    """

    if not API_MANAGER_CHAT_ENDPOINT:
        logger.info("API Manager not configured; skipping trial grading LLM call")
        return None

    access_token = _get_access_token()
    if not access_token:
        logger.error("✗ Failed to obtain access token; skipping trial grading LLM call")
        return None

    logger.info("Calling LLM API for trial grading via API Manager proxy")
    logger.info("  Endpoint: %s", API_MANAGER_CHAT_ENDPOINT)
    logger.info("  Model: %s", OPENAI_MODEL)
    logger.info("  Trials to grade: %d", len(messages) - 1)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        logger.info("Sending request to LLM API...")
        response = requests.post(
            API_MANAGER_CHAT_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30,
        )
        
        logger.info("LLM API responded with status: %d", response.status_code)
        
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        logger.info("✓ LLM evidence grading response received successfully (%d chars)", len(content))
        logger.info("✓ Trial grading completed")
        return content
    except requests.HTTPError as exc:
        logger.error("✗ LLM API HTTP error: status=%d, response=%s", 
                    response.status_code, 
                    response.text[:200] if response.text else "empty")
        logger.exception("✗ LLM evidence grading failed: %s", exc)
        return None
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        logger.exception("✗ LLM evidence grading failed: %s", exc)
        return None


def _extract_json_block(text: str) -> Optional[dict[str, Any]]:
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


def fetch_trials(state: EvidenceState) -> EvidenceState:
    context = state["context"]
    logger.info(
        "Fetching trials for diagnosis=%s egfr=%.1f (radius=%s)",
        context["diagnosis"],
        context["egfr"],
        context.get("geo", {}).get("radius_km"),
    )
    
    trials: List[dict] = []
    
    # Try MCP first if configured
    if TRIAL_REGISTRY_MCP_URL:
        logger.info("Using Trial Registry MCP server: %s", TRIAL_REGISTRY_MCP_URL)
        # Note: Trial Registry MCP tool is named "get" not "getTrials"
        mcp_result = _call_mcp_tool(TRIAL_REGISTRY_MCP_URL, "get", {})
        
        if mcp_result and not mcp_result.get("isError", True):
            # Extract trials from MCP response
            content = mcp_result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                text_content = content[0].get("text", "")
                try:
                    mcp_data = json.loads(text_content)
                    # MCP returns {totalCount: N, trials: [...]} structure
                    if isinstance(mcp_data, dict) and "trials" in mcp_data:
                        trials = mcp_data["trials"]
                        logger.info("✓ Retrieved %d trials via MCP (totalCount: %d)", 
                                   len(trials), mcp_data.get("totalCount", len(trials)))
                    elif isinstance(mcp_data, list):
                        # Fallback: if it's already a list
                        trials = mcp_data
                        logger.info("✓ Retrieved %d trials via MCP", len(trials))
                    else:
                        logger.warning("Unexpected MCP response format: %s", type(mcp_data))
                except json.JSONDecodeError:
                    logger.warning("Failed to parse MCP response as JSON, falling back to direct service")
        else:
            logger.warning("MCP call failed or returned no data, falling back to direct Trial Registry service")
    
    # Fallback to direct REST call if MCP failed or not configured
    if not trials and TRIAL_REGISTRY_URL:
        logger.info("Using direct Trial Registry service: %s", TRIAL_REGISTRY_URL)
        try:
            url = f"{TRIAL_REGISTRY_URL.rstrip('/')}/trials"
            response = requests.get(url, timeout=10)
            logger.info("Trial Registry endpoint responded: status=%s", response.status_code)
            response.raise_for_status()
            trials = response.json()
            logger.info("✓ Retrieved %d trials via direct service", len(trials))
        except requests.RequestException as exc:
            logger.exception("Trial Registry request failed: %s", exc)
            raise RuntimeError("Failed to reach Trial Registry service") from exc
    diagnosis = context["diagnosis"].lower()
    egfr = context["egfr"]
    geo = context.get("geo")

    scored: List[TrialMatch] = []
    for trial in trials:
        # Handle both camelCase (MCP) and snake_case (Python backend) field names
        title = trial.get("title", "")
        condition = trial.get("condition", "")
        # Try both eligibilitySummary (MCP/Ballerina) and eligibility_summary (Python)
        eligibility = trial.get("eligibilitySummary") or trial.get("eligibility_summary")
        score = 0.0

        if diagnosis in condition.lower():
            score += 2.0
        if "ckd" in condition.lower() or "renal" in title.lower():
            score += 0.8
        if egfr <= 45 and eligibility and "eGFR" in eligibility:
            score += 0.7
        if context["age"] >= 60:
            score += 0.3

        # Try both distance (MCP) and site_distance_km (Python)
        distance = trial.get("distance") or trial.get("site_distance_km")
        if geo and distance is not None and distance > geo["radius_km"]:
            continue

        # Try both nctId (MCP) and nct_id (Python)
        nct_id = trial.get("nctId") or trial.get("nct_id") or f"NCT{trial['id']:08d}"
        
        scored.append(
            TrialMatch(
                id=int(trial["id"]),
                nct_id=nct_id,
                title=title,
                condition=condition,
                phase=trial.get("phase", ""),
                status=trial.get("status", ""),
                site_distance_km=distance,
                suitability=round(score, 2),
                why_match=eligibility or f"Matches diagnosis {context['diagnosis']}",
            )
        )

    scored.sort(key=lambda item: item["suitability"], reverse=True)
    logger.info("Scored %d trials; returning top %d", len(scored), len(scored[:3]))
    return {"trial_matches": scored[:3]}


def _synthetic_llm_grade(trial: TrialMatch, context: PatientContext) -> EvidenceAnalysis:
    suitability = trial["suitability"]
    if suitability >= 2.5:
        pico_grade = "high"
        benefit = "Strong renal and cardiovascular benefit observed in similar cohorts."
        risk = "Monitor renal function, hydration status, and genital mycotic risk."
    elif suitability >= 1.5:
        pico_grade = "medium"
        benefit = "Reasonable evidence for metabolic control with renal safety signals."
        risk = "Assess for GI side effects and titrate alongside current therapy."
    else:
        pico_grade = "low"
        benefit = "Limited directly applicable data; consider within shared decision making."
        risk = "Eligibility uncertain; requires further screening."

    summary = (
        f"{trial['title']} ({trial['nct_id']}) targets {trial['condition']} in {trial['phase']} and "
        f"shows {pico_grade} relevance for a {context['age']} y/o with eGFR {context['egfr']:.1f}."
    )

    return EvidenceAnalysis(
        trial_id=trial["id"],
        trial_title=trial["title"],
        pico_grade=pico_grade,
        benefit_summary=benefit,
        risk_summary=risk,
        overall_summary=summary,
    )


def llm_grade_trials(state: EvidenceState) -> EvidenceState:
    trials = state.get("trial_matches", [])
    if not trials:
        return {}

    context = state["context"]
    logger.info("Preparing LLM grading payload for %d trials", len(trials))
    messages = [
        {
            "role": "system",
            "content": (
                "You are an evidence synthesis assistant. Respond ONLY with JSON containing "
                "an array named 'analyses'. For each trial provide keys: trial_id, "
                "pico_grade (high/medium/low), benefit_summary, risk_summary, overall_summary, "
                "and optional why_match."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "patient": context,
                    "trials": trials,
                },
                default=str,
            ),
        },
    ]

    raw = _call_llm(messages)
    if not raw:
        logger.info("LLM grading unavailable; using heuristic analyses")
        return {}

    parsed = _extract_json_block(raw) or {}
    logger.info("Parsed LLM grading payload keys=%s", list(parsed.keys()))
    analyses_payload = parsed.get("analyses")
    if not isinstance(analyses_payload, list):
        return {}

    llm_analyses: List[EvidenceAnalysis] = []
    for trial in trials:
        selected: Optional[dict[str, Any]] = None
        for candidate in analyses_payload:
            if isinstance(candidate, dict) and candidate.get("trial_id") in {
                trial["id"],
                str(trial["id"]),
                trial.get("nct_id"),
            }:
                selected = candidate
                break
        if not selected and analyses_payload:
            candidate = analyses_payload.pop(0)
            selected = candidate if isinstance(candidate, dict) else None

        if not selected:
            llm_analyses.append(_synthetic_llm_grade(trial, context))
            continue

        llm_analyses.append(
            EvidenceAnalysis(
                trial_id=trial["id"],
                trial_title=trial["title"],
                pico_grade=str(selected.get("pico_grade", "medium")).lower(),
                benefit_summary=str(selected.get("benefit_summary") or "Benefits unclear."),
                risk_summary=str(selected.get("risk_summary") or "Risks not specified."),
                overall_summary=str(
                    selected.get("overall_summary")
                    or f"{trial['title']} relevance not summarised."
                ),
            )
        )

    notes = parsed.get("notes")
    return {"analyses": llm_analyses, "llm_notes": notes}


def analyze_evidence(state: EvidenceState) -> EvidenceState:
    context = state["context"]
    trials = state.get("trial_matches", [])
    analyses = state.get("analyses") or [
        _synthetic_llm_grade(trial, context) for trial in trials
    ]

    evidence_pack = EvidencePack(
        patient=context,
        analyses=analyses,
        trials=trials,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )
    if API_MANAGER_CHAT_ENDPOINT and state.get("analyses"):
        evidence_pack["llm_model"] = OPENAI_MODEL
    if state.get("llm_notes"):
        evidence_pack["notes"] = str(state["llm_notes"])
    logger.info(
        "Returning evidence pack with %d analyses and %d trials",
        len(analyses),
        len(trials),
    )
    return {"evidence_pack": evidence_pack}


def build_graph() -> StateGraph:
    graph = StateGraph(EvidenceState)
    graph.add_node("fetch_trials", fetch_trials)
    graph.add_node("llm_grade_trials", llm_grade_trials)
    graph.add_node("analyze_evidence", analyze_evidence)
    graph.set_entry_point("fetch_trials")
    graph.add_edge("fetch_trials", "llm_grade_trials")
    graph.add_edge("llm_grade_trials", "analyze_evidence")
    graph.add_edge("analyze_evidence", END)
    return graph.compile()


EVIDENCE_GRAPH = build_graph()


# ---------------------------------------------------------------------------
# FastAPI wiring
# ---------------------------------------------------------------------------
class GeoFilter(BaseModel):
    lat: float
    lon: float
    radius_km: float = Field(25.0, description="Radius (km) for local trial suggestions")


class EvidenceRequest(BaseModel):
    age: int
    diagnosis: str
    egfr: float = Field(..., description="Latest estimated glomerular filtration rate")
    comorbidities: List[str] = Field(default_factory=list)
    geo: Optional[GeoFilter] = None


class PatientContextModel(BaseModel):
    age: int
    diagnosis: str
    egfr: float
    comorbidities: List[str]
    geo: Optional[GeoFilter] = None


class TrialMatchModel(BaseModel):
    id: int
    nct_id: str
    title: str
    condition: str
    phase: str
    status: str
    site_distance_km: Optional[float]
    suitability: float
    why_match: Optional[str]


class EvidenceAnalysisModel(BaseModel):
    trial_id: int
    trial_title: str
    pico_grade: str
    benefit_summary: str
    risk_summary: str
    overall_summary: str


class EvidencePackModel(BaseModel):
    patient: PatientContextModel
    analyses: List[EvidenceAnalysisModel]
    trials: List[TrialMatchModel]
    llm_model: Optional[str] = None
    generated_at: Optional[str] = None
    notes: Optional[str] = None


class EvidenceResponse(BaseModel):
    evidence_pack: EvidencePackModel


app = FastAPI(
    title="Evidence Agent",
    description=(
        "Aggregates clinical trial data, grades relevance, and returns structured evidence packs"
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/agents/evidence/search", response_model=EvidenceResponse)
def evidence_search(payload: EvidenceRequest) -> EvidenceResponse:
    logger.info(
        "Received evidence request: diagnosis=%s age=%s egfr=%s",
        payload.diagnosis,
        payload.age,
        payload.egfr,
    )
    context: PatientContext = {
        "age": payload.age,
        "diagnosis": payload.diagnosis,
        "egfr": payload.egfr,
        "comorbidities": payload.comorbidities,
        "geo": payload.geo.dict() if payload.geo else None,
    }

    try:
        result = EVIDENCE_GRAPH.invoke({"context": context})
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    pack = result["evidence_pack"]
    logger.info(
        "Evidence response ready (llm_model=%s)",
        pack.get("llm_model"),
    )

    return EvidenceResponse(evidence_pack=EvidencePackModel.parse_obj(pack))


def run_demo() -> None:
    """Convenience helper for local smoke tests."""
    demo_request = EvidenceRequest(
        age=62,
        diagnosis="Type 2 diabetes mellitus",
        egfr=44.0,
        comorbidities=["CKD stage 3"],
        geo=GeoFilter(lat=35.15, lon=-90.05, radius_km=25),
    )
    response = evidence_search(demo_request)
    for analysis in response.evidence_pack.analyses:
        print(
            f"Trial {analysis.trial_title} ({analysis.trial_id}) → PICO: {analysis.pico_grade} "
            f"| Benefit: {analysis.benefit_summary}"
        )


if __name__ == "__main__":
    run_demo()
