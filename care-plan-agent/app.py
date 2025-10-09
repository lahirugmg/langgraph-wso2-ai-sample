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

def _strip_quotes(value: Optional[str]) -> Optional[str]:
    """Strip quotes from environment variable values."""
    if value is None:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value

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
API_MANAGER_OPENAI_PROXY_URL = os.environ.get("API_MANAGER_OPENAI_PROXY_URL")
API_MANAGER_CLIENT_ID = os.environ.get("API_MANAGER_CLIENT_ID")
API_MANAGER_CLIENT_SECRET = os.environ.get("API_MANAGER_CLIENT_SECRET")
API_MANAGER_TOKEN_ENDPOINT = os.environ.get(
    "API_MANAGER_TOKEN_ENDPOINT",
    f"{API_MANAGER_BASE_URL}/oauth2/token" if API_MANAGER_BASE_URL else None
)
API_MANAGER_CHAT_ENDPOINT = os.environ.get(
    "API_MANAGER_CHAT_ENDPOINT",
    f"{API_MANAGER_OPENAI_PROXY_URL}/chat/completions" if API_MANAGER_OPENAI_PROXY_URL else None
)

# MCP Gateway configuration
MCP_GATEWAY_CLIENT_ID = _strip_quotes(os.environ.get("MCP_GATEWAY_CLIENT_ID"))
MCP_GATEWAY_CLIENT_SECRET = _strip_quotes(os.environ.get("MCP_GATEWAY_CLIENT_SECRET"))
MCP_GATEWAY_TOKEN_ENDPOINT = _strip_quotes(os.environ.get("MCP_GATEWAY_TOKEN_ENDPOINT"))

# MCP Server URLs
EHR_MCP_URL = _strip_quotes(os.environ.get("EHR_MCP_URL"))

# Cache for access tokens
_access_token_cache = {"token": None, "expires_at": 0}
_mcp_access_token_cache = {"token": None, "expires_at": 0}

# Global cache for MCP tools list (cached for 5 minutes)
_mcp_tools_cache = {
    "ehr": {"tools": [], "timestamp": 0},
    "trial_registry": {"tools": [], "timestamp": 0}
}


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
            timeout=180,
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
            timeout=180,
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


def _list_mcp_tools(server_url: str, cache_key: str) -> List[Dict[str, Any]]:
    """List available tools from MCP server with caching."""
    import time
    
    # Check cache (valid for 5 minutes)
    cache_entry = _mcp_tools_cache.get(cache_key, {"tools": [], "timestamp": 0})
    if cache_entry["tools"] and (time.time() - cache_entry["timestamp"]) < 300:
        logger.info("📦 Using cached tools list for %s (%d tools)", cache_key, len(cache_entry["tools"]))
        return cache_entry["tools"]
    
    access_token = _get_mcp_access_token()
    if not access_token:
        logger.error("Failed to obtain MCP access token for listing tools")
        return []
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    try:
        logger.info("🔍 Discovering available MCP tools from %s...", server_url)
        response = requests.post(
            server_url,
            headers=headers,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            logger.error("MCP tools/list error: %s", result["error"])
            return []
        
        tools = result.get("result", {}).get("tools", [])
        logger.info("✅ Discovered %d MCP tools from %s:", len(tools), cache_key)
        for tool in tools:
            logger.info("   • %s - %s", tool.get("name"), tool.get("description", "No description"))
        
        # Update cache
        _mcp_tools_cache[cache_key] = {
            "tools": tools,
            "timestamp": time.time()
        }
        
        return tools
    except Exception as e:
        logger.error("Failed to list MCP tools: %s", e)
        return []


def _find_best_mcp_tool(tools: List[Dict[str, Any]], purpose: str, keywords: List[str]) -> Optional[Dict[str, Any]]:
    """
    Intelligently find the best matching MCP tool based on purpose and keywords.
    
    Args:
        tools: List of available MCP tools
        purpose: Human-readable description of what we want to do
        keywords: List of keywords to search for in tool name/description
    
    Returns:
        Best matching tool dict or None
    """
    logger.info("🤔 Selecting best tool for purpose: '%s'", purpose)
    logger.info("   Search keywords: %s", ", ".join(keywords))
    
    best_match = None
    best_score = 0
    
    for tool in tools:
        name = tool.get("name", "").lower()
        description = tool.get("description", "").lower()
        score = 0
        
        # Score based on keyword matches
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in name:
                score += 10  # Name match is highest priority
            if keyword_lower in description:
                score += 5   # Description match is secondary
        
        if score > best_score:
            best_score = score
            best_match = tool
            logger.info("   📊 Candidate: '%s' (score: %d)", name, score)
    
    if best_match:
        logger.info("✅ Selected tool: '%s' - %s", 
                   best_match.get("name"), 
                   best_match.get("description", ""))
        return best_match
    else:
        logger.warning("⚠️  No matching tool found for purpose: '%s'", purpose)
        return None


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
    
    try:
        response = requests.post(
            MCP_GATEWAY_TOKEN_ENDPOINT,
            data={
                "grant_type": "client_credentials",
                "client_id": MCP_GATEWAY_CLIENT_ID,
                "client_secret": MCP_GATEWAY_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=180,
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
        return access_token
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.exception("✗ Failed to obtain MCP access token: %s", exc)
        return None


def _call_mcp_tool(server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Call an MCP tool."""
    access_token = _get_mcp_access_token()
    if not access_token:
        logger.error("Failed to obtain MCP access token")
        return None
    
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
        "Authorization": f"Bearer {access_token[:20]}...{access_token[-10:]}",  # Masked for logging
        "Content-Type": "application/json",
    }
    
    try:
        logger.info("=" * 80)
        logger.info("MCP REQUEST - Calling tool '%s' at %s", tool_name, server_url)
        logger.info("JSON-RPC Request Payload:")
        logger.info(json.dumps(payload, indent=2))
        logger.info("Request Headers: %s", json.dumps({k: v for k, v in headers.items()}, indent=2))
        logger.info("-" * 80)
        
        # Use actual token (not masked) for the request
        actual_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        
        response = requests.post(
            server_url,
            headers=actual_headers,
            json=payload,
            timeout=180,
        )
        
        logger.info("MCP RESPONSE - Status Code: %d", response.status_code)
        logger.info("Response Headers: %s", json.dumps(dict(response.headers), indent=2))
        
        try:
            result = response.json()
            logger.info("JSON-RPC Response:")
            logger.info(json.dumps(result, indent=2))
        except json.JSONDecodeError:
            logger.error("Failed to parse response as JSON. Raw response text:")
            logger.error(response.text[:1000])  # Log first 1000 chars
            raise
        
        logger.info("=" * 80)
        
        response.raise_for_status()
        
        if "error" in result:
            logger.error("❌ MCP tool error detected in response")
            logger.error("Error details: %s", json.dumps(result["error"], indent=2))
            return None
        
        logger.info("✓ MCP tool '%s' executed successfully", tool_name)
        return result.get("result")
        
    except Exception as e:
        logger.error("✗ MCP tool call exception: %s", e)
        logger.exception("Full exception traceback:")
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


def _calculate_age(date_of_birth: str) -> int:
    """Calculate age from date of birth string (YYYY-MM-DD)."""
    try:
        from datetime import datetime
        dob = datetime.strptime(date_of_birth, "%Y-%m-%d")
        today = datetime.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    except (ValueError, AttributeError):
        return 0


def _transform_mcp_to_python_format(mcp_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform Ballerina MCP response format to match Python EHR backend format.
    
    Handles:
    - Field naming: camelCase → snake_case (lastA1c → last_a1c)
    - Data structure: nested objects → primitives (lastA1c.value → float)
    - Arrays: object arrays → string arrays for problems/medications
    - Demographics: firstName+lastName → name, dateOfBirth → age
    """
    try:
        # Transform demographics
        demographics_in = mcp_data.get("demographics", {})
        demographics_out = {
            "name": f"{demographics_in.get('firstName', '')} {demographics_in.get('lastName', '')}".strip(),
            "age": _calculate_age(demographics_in.get("dateOfBirth", "")) if demographics_in.get("dateOfBirth") else 0,
            "gender": demographics_in.get("gender", "").lower(),
            "mrn": demographics_in.get("patientId", "")
        }
        
        # Transform problems: array of objects → array of strings
        problems_in = mcp_data.get("problems", [])
        problems_out = [
            p.get("description", "") if isinstance(p, dict) else str(p)
            for p in problems_in
        ]
        
        # Transform medications: array of objects → array of strings
        medications_in = mcp_data.get("medications", [])
        medications_out = []
        for m in medications_in:
            if isinstance(m, dict):
                name = m.get("name", "")
                dosage = m.get("dosage", "")
                frequency = m.get("frequency", "")
                medications_out.append(f"{name} {dosage} {frequency}".strip())
            else:
                medications_out.append(str(m))
        
        # Transform vitals: array → single object with latest values
        vitals_in = mcp_data.get("vitals", [])
        if vitals_in and isinstance(vitals_in, list) and len(vitals_in) > 0:
            latest_vitals = vitals_in[0]  # Assume first is latest
            vitals_out = {
                "systolic": latest_vitals.get("bloodPressureSystolic", 0),
                "diastolic": latest_vitals.get("bloodPressureDiastolic", 0),
                "heart_rate": latest_vitals.get("heartRate", 0),
                "weight_kg": latest_vitals.get("weight", 0),
                "updated_at": latest_vitals.get("recordDate", "")
            }
        else:
            vitals_out = {
                "systolic": 0,
                "diastolic": 0,
                "heart_rate": 0,
                "weight_kg": 0,
                "updated_at": ""
            }
        
        # Transform lab values: object → float (extract .value field)
        last_a1c_in = mcp_data.get("lastA1c", {})
        last_a1c_out = last_a1c_in.get("value", 0.0) if isinstance(last_a1c_in, dict) else float(last_a1c_in or 0)
        
        last_egfr_in = mcp_data.get("lastEgfr", {})
        last_egfr_out = last_egfr_in.get("value", 0.0) if isinstance(last_egfr_in, dict) else float(last_egfr_in or 0)
        
        # Build transformed response
        transformed = {
            "demographics": demographics_out,
            "problems": problems_out,
            "medications": medications_out,
            "vitals": vitals_out,
            "last_a1c": last_a1c_out,
            "last_egfr": last_egfr_out
        }
        
        logger.info("✓ Transformed MCP response: last_a1c=%s, last_egfr=%s, problems=%d, medications=%d",
                   last_a1c_out, last_egfr_out, len(problems_out), len(medications_out))
        
        return transformed
        
    except Exception as e:
        logger.error("✗ Failed to transform MCP response: %s", e)
        logger.exception("Transformation error details:")
        return mcp_data  # Return original if transformation fails


def fetch_patient_summary(state: CarePlanState) -> CarePlanState:
    patient_id = state["request"]["patient_id"]
    logger.info("=" * 100)
    logger.info("🔍 STEP 1: FETCH PATIENT SUMMARY")
    logger.info("=" * 100)
    logger.info("📋 REASON: Need comprehensive patient data (demographics, conditions, labs, medications)")
    logger.info("           to make informed clinical decisions about care plan recommendations")
    logger.info("👤 Patient ID: %s", patient_id)
    logger.info("-" * 100)
    
    if not EHR_MCP_URL:
        logger.error("❌ CRITICAL: EHR_MCP_URL is not configured - cannot proceed")
        raise RuntimeError("EHR_MCP_URL is not configured")
    
    logger.info("🌐 EHR MCP Endpoint: %s", EHR_MCP_URL)
    
    # Step 1: Discover available tools
    available_tools = _list_mcp_tools(EHR_MCP_URL, "ehr")
    if not available_tools:
        raise RuntimeError("Failed to discover EHR MCP tools")
    
    # Step 2: Find best tool for getting patient summary
    best_tool = _find_best_mcp_tool(
        available_tools,
        purpose="Retrieve comprehensive patient summary including demographics, conditions, medications, and labs",
        keywords=["patient", "summary", "get"]
    )
    
    if not best_tool:
        raise RuntimeError("No suitable MCP tool found for fetching patient summary")
    
    tool_name = best_tool["name"]
    logger.info("🔧 SELECTED TOOL: '%s'", tool_name)
    logger.info("   Description: %s", best_tool.get("description", "N/A"))
    logger.info("   WHY THIS TOOL?: Best match for retrieving patient summary data")
    
    # Step 3: Determine the correct parameter name from the tool's input schema
    input_schema = best_tool.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    required_params = input_schema.get("required", [])
    
    # Find the parameter name for patient ID (could be 'patient_id', 'id', 'patientId', etc.)
    patient_id_param = None
    for param_name in properties.keys():
        if "patient" in param_name.lower() and "id" in param_name.lower():
            patient_id_param = param_name
            break
    
    if not patient_id_param and required_params:
        # If we didn't find a patient_id param, use the first required param
        patient_id_param = required_params[0]
    
    if not patient_id_param:
        patient_id_param = "patient_id"  # Default fallback
    
    logger.info("   Parameter mapping: '%s' = '%s'", patient_id_param, patient_id)
    
    # Step 4: Call the selected tool
    mcp_result = _call_mcp_tool(EHR_MCP_URL, tool_name, {patient_id_param: patient_id})    
    if not mcp_result:
        raise RuntimeError(f"MCP call failed for patient {patient_id}")
    
    # Extract summary from MCP response
    content = mcp_result.get("content", [])
    if not content or not isinstance(content, list) or len(content) == 0:
        raise RuntimeError(f"Invalid MCP response structure for patient {patient_id}")
    
    text_content = content[0].get("text", "")
    try:
        mcp_data = json.loads(text_content)
        logger.info("✓ Raw MCP response received for patient_id=%s", patient_id)
        
        # Transform Ballerina MCP format to Python backend format
        logger.info("🔄 Transforming MCP response from Ballerina format to Python format")
        summary = _transform_mcp_to_python_format(mcp_data)
        
        # Extract key clinical indicators
        demographics = summary.get("demographics", {})
        age = demographics.get("age")
        problems = summary.get("problems", [])
        medications = summary.get("medications", [])
        last_a1c = summary.get("last_a1c")
        last_egfr = summary.get("last_egfr")
        
        logger.info("✅ STEP 1 COMPLETE: Patient summary successfully retrieved")
        logger.info("📊 KEY CLINICAL DATA EXTRACTED:")
        logger.info("   • Age: %s years", age)
        logger.info("   • Active Problems: %s", ", ".join(problems) if problems else "None")
        logger.info("   • Current Medications: %s", ", ".join(medications) if medications else "None")
        logger.info("   • HbA1c: %s%%", last_a1c if last_a1c else "N/A")
        logger.info("   • eGFR: %s mL/min/1.73m²", last_egfr if last_egfr else "N/A")
        logger.info("💡 ANALYSIS: Patient data ready for evidence-based recommendation generation")
        logger.info("=" * 100)
        logger.info("")
        
        return {"patient_summary": summary}
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse MCP response as JSON for patient {patient_id}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to process MCP response for patient {patient_id}") from e


def call_evidence_agent(state: CarePlanState) -> CarePlanState:
    logger.info("=" * 100)
    logger.info("🔬 STEP 2: FETCH CLINICAL EVIDENCE & TRIALS")
    logger.info("=" * 100)
    logger.info("📋 REASON: Need evidence-based clinical trial data and research to support")
    logger.info("           personalized care plan recommendations for this specific patient")
    logger.info("-" * 100)
    
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
        logger.error("❌ CRITICAL: Missing required patient data (age or eGFR)")
        raise RuntimeError("Patient summary missing age or eGFR for evidence lookup")

    logger.info("🎯 PATIENT CLINICAL PROFILE FOR EVIDENCE MATCHING:")
    logger.info("   • Patient ID: %s", state["request"]["patient_id"])
    logger.info("   • Primary Diagnosis: %s", diagnosis)
    logger.info("   • Age: %s years", payload["age"])
    logger.info("   • eGFR: %s mL/min/1.73m²", payload["egfr"])
    logger.info("   • Comorbidities: %s", ", ".join(payload["comorbidities"]) if payload["comorbidities"] else "None")
    logger.info("   • Geographic Search: %s km radius", DEFAULT_GEO.get("radius_km", "N/A"))
    logger.info("-" * 100)
    logger.info("🔧 TOOL CHOICE: Calling Evidence Agent Service")
    logger.info("   WHY EVIDENCE AGENT?: Specialized service that:")
    logger.info("   1. Retrieves relevant clinical trials via MCP (Trial Registry)")
    logger.info("   2. Filters trials based on patient's clinical profile")
    logger.info("   3. Uses LLM to analyze trial eligibility and relevance")
    logger.info("   4. Returns ranked evidence with suitability scores")
    logger.info("-" * 100)
    try:
        response = requests.post(
            f"{EVIDENCE_AGENT_URL.rstrip('/')}/agents/evidence/search",
            json=payload,
            timeout=180,  # MCP call may take time for Trial Registry retrieval + LLM grading
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Failed to reach Evidence Agent") from exc

    data = response.json()
    pack = data.get("evidence_pack", {})
    analyses = pack.get("analyses", [])
    trials = pack.get("trials", [])
    
    logger.info("✅ STEP 2 COMPLETE: Evidence pack successfully retrieved")
    logger.info("📊 EVIDENCE SUMMARY:")
    logger.info("   • Clinical Trial Analyses: %d", len(analyses))
    logger.info("   • Matching Trials Found: %d", len(trials))
    
    if trials:
        logger.info("   • Top Matching Trials:")
        for i, trial in enumerate(trials[:3], 1):
            logger.info("     %d. %s (NCT: %s)", i, trial.get("title", "Unknown"), trial.get("nct_id", "N/A"))
            logger.info("        Distance: %s km | Status: %s", 
                       trial.get("site_distance_km", "N/A"), 
                       trial.get("status", "Unknown"))
    
    if analyses:
        logger.info("   • Evidence Quality Assessment:")
        for i, analysis in enumerate(analyses[:2], 1):
            logger.info("     %d. Trial: %s", i, analysis.get("trial_title", "Unknown"))
            logger.info("        Grade: %s | Summary: %s...", 
                       analysis.get("pico_grade", "N/A"),
                       (analysis.get("overall_summary", "")[:80] + "...") if analysis.get("overall_summary") else "N/A")
    
    logger.info("💡 ANALYSIS: Evidence data ready for LLM-assisted care plan generation")
    logger.info("=" * 100)
    logger.info("")
    
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
    logger.info("=" * 100)
    logger.info("🤖 STEP 3: LLM-ASSISTED CARE PLAN GENERATION")
    logger.info("=" * 100)
    logger.info("📋 REASON: Generate personalized, evidence-based clinical recommendations")
    logger.info("           using AI to synthesize patient data + clinical evidence")
    logger.info("-" * 100)
    
    summary = state.get("patient_summary")
    evidence_pack = state.get("evidence_pack", {})
    
    if not summary:
        logger.warning("⚠️  No patient summary available - skipping LLM generation")
        return {}

    # Check if we have LLM configured
    if not API_MANAGER_CHAT_ENDPOINT:
        logger.info("ℹ️  LLM DECISION: Skipping LLM call")
        logger.info("   REASON: API Manager chat endpoint not configured (API_MANAGER_CHAT_ENDPOINT)")
        logger.info("   FALLBACK: Will use heuristic-based plan card generation instead")
        logger.info("-" * 100)
        return {}
    
    logger.info("🔧 TOOL CHOICE: Using Large Language Model (LLM)")
    logger.info("   WHY LLM?: LLMs excel at:")
    logger.info("   1. Synthesizing complex clinical data (patient + evidence)")
    logger.info("   2. Generating context-aware, personalized recommendations")
    logger.info("   3. Providing clinical rationale based on evidence")
    logger.info("   4. Suggesting appropriate alternatives and safety checks")
    logger.info("   Model: %s", OPENAI_MODEL or "gpt-4")
    logger.info("-" * 100)
    logger.info("📤 INPUT TO LLM:")
    logger.info("   • Patient Summary: Demographics, diagnoses, medications, labs")
    logger.info("   • Evidence Pack: %d trial analyses, %d matching trials", 
                len(evidence_pack.get("analyses", [])),
                len(evidence_pack.get("trials", [])))
    logger.info("   • Expected Output: Structured JSON with recommendation, rationale, orders, citations")
    logger.info("-" * 100)

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

    logger.info("⏳ Calling LLM... (this may take 5-15 seconds)")
    raw = _call_llm(messages)
    
    if not raw:
        logger.warning("⚠️  LLM returned empty response - will use heuristic fallback")
        return {}

    parsed = _extract_json_block(raw) or {}
    logger.info("✅ LLM response received and parsed")
    logger.info("   Parsed keys: %s", list(parsed.keys()))
    
    plan_candidate = parsed.get("plan_card") or parsed
    if not isinstance(plan_candidate, dict):
        logger.warning("⚠️  LLM response format invalid - expected dict, got %s", type(plan_candidate))
        return {}

    plan_candidate.setdefault("llm_model", OPENAI_MODEL)
    plan_candidate.setdefault("generated_at", datetime.utcnow().isoformat() + "Z")
    if parsed.get("notes"):
        plan_candidate.setdefault("notes", parsed["notes"])

    logger.info("📊 LLM PLAN CARD COMPONENTS:")
    logger.info("   • Recommendation: %s", "✓" if plan_candidate.get("recommendation") else "✗")
    logger.info("   • Rationale: %s", "✓" if plan_candidate.get("rationale") else "✗")
    logger.info("   • Alternatives: %d items", len(plan_candidate.get("alternatives", [])))
    logger.info("   • Safety Checks: %d items", len(plan_candidate.get("safety_checks", [])))
    logger.info("   • Medication Orders: %s", "✓" if plan_candidate.get("orders", {}).get("medication") else "✗")
    logger.info("   • Lab Orders: %d items", len(plan_candidate.get("orders", {}).get("labs", [])))
    logger.info("   • Citations: %d items", len(plan_candidate.get("citations", [])))
    logger.info("💡 ANALYSIS: LLM successfully generated personalized care plan")
    logger.info("=" * 100)
    logger.info("")
    
    return {"llm_plan_card": plan_candidate}


def assemble_plan(state: CarePlanState) -> CarePlanState:
    logger.info("=" * 100)
    logger.info("🔨 STEP 4: ASSEMBLE FINAL CARE PLAN")
    logger.info("=" * 100)
    logger.info("📋 REASON: Combine LLM-generated plan with rule-based heuristics")
    logger.info("           to ensure completeness and clinical validity")
    logger.info("-" * 100)
    
    logger.info("🔧 Generating heuristic-based plan card (rule-based fallback)...")
    heuristic = _draft_plan_card(state)
    logger.info("   ✓ Heuristic plan ready with standard recommendations")
    
    llm_card = state.get("llm_plan_card")
    
    if llm_card:
        logger.info("🎯 MERGE STRATEGY: Combining LLM + Heuristic")
        logger.info("   REASON: LLM provides personalized content, heuristic ensures completeness")
        logger.info("   MERGE LOGIC:")
        logger.info("   • Use LLM values where available (more context-aware)")
        logger.info("   • Fall back to heuristic values for missing fields")
        logger.info("   • Merge trial matches intelligently (by NCT ID or title)")
        logger.info("   • Preserve all citations and evidence highlights")
        logger.info("-" * 100)
        plan_card = _merge_plan_cards(llm_card, heuristic)
        logger.info("✅ MERGE COMPLETE: LLM + heuristic plan cards combined")
        logger.info("   Patient: %s", state["request"]["patient_id"])
        logger.info("   Source: LLM-enhanced (AI-generated + rule-based)")
    else:
        logger.info("🎯 FALLBACK STRATEGY: Using Heuristic-Only Plan")
        logger.info("   REASON: No LLM card available (LLM skipped or failed)")
        logger.info("   CONTENT: Rule-based clinical recommendations")
        logger.info("   QUALITY: Valid but less personalized than LLM-enhanced")
        logger.info("-" * 100)
        plan_card = heuristic
        logger.info("✅ HEURISTIC PLAN READY")
        logger.info("   Patient: %s", state["request"]["patient_id"])
        logger.info("   Source: Heuristic-only (rule-based)")
    
    logger.info("-" * 100)
    logger.info("📊 FINAL CARE PLAN SUMMARY:")
    logger.info("   • Primary Recommendation: %s", 
                (plan_card.get("recommendation", "")[:80] + "...") if len(plan_card.get("recommendation", "")) > 80 
                else plan_card.get("recommendation", "N/A"))
    logger.info("   • Clinical Rationale: %s", 
                (plan_card.get("rationale", "")[:80] + "...") if len(plan_card.get("rationale", "")) > 80 
                else plan_card.get("rationale", "N/A"))
    logger.info("   • Alternative Options: %d", len(plan_card.get("alternatives", [])))
    logger.info("   • Safety Considerations: %d", len(plan_card.get("safety_checks", [])))
    logger.info("   • Medication Orders: %s", 
                plan_card.get("orders", {}).get("medication", {}).get("name", "None"))
    logger.info("   • Lab Orders: %d", len(plan_card.get("orders", {}).get("labs", [])))
    logger.info("   • Trial Matches: %d", len(plan_card.get("trial_matches", [])))
    logger.info("   • Evidence Citations: %d", len(plan_card.get("citations", [])))
    logger.info("=" * 100)
    logger.info("✅ CARE PLAN GENERATION COMPLETE - Ready for delivery")
    logger.info("=" * 100)
    logger.info("")

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
