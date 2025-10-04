"""LangGraph-driven Evidence Agent exposed via FastAPI.

The agent queries the Trial Registry service, applies a lightweight heuristic
"LLM" grading step, and returns a structured evidence pack that downstream
services (e.g., care-plan agent) can consume.
"""
from __future__ import annotations

import os
import json
import os
import re
from datetime import datetime
from typing import Any, List, Optional, TypedDict

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

TRIAL_REGISTRY_URL = os.environ.get("TRIAL_REGISTRY_URL", "http://127.0.0.1:8002")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


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


def _call_llm(messages: List[dict[str, str]]) -> Optional[str]:
    """Call a chat-completions style LLM endpoint if credentials exist.

    Returns the raw model string or ``None`` when unavailable/failing so callers
    can gracefully fall back to heuristic behaviour.
    """

    if not OPENAI_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    try:
        response = requests.post(
            f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, ValueError):
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
    try:
        response = requests.get(f"{TRIAL_REGISTRY_URL.rstrip('/')}/trials", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Failed to reach Trial Registry service") from exc

    trials: List[dict] = response.json()
    diagnosis = context["diagnosis"].lower()
    egfr = context["egfr"]
    geo = context.get("geo")

    scored: List[TrialMatch] = []
    for trial in trials:
        title = trial.get("title", "")
        condition = trial.get("condition", "")
        eligibility = trial.get("eligibility_summary")
        score = 0.0

        if diagnosis in condition.lower():
            score += 2.0
        if "ckd" in condition.lower() or "renal" in title.lower():
            score += 0.8
        if egfr <= 45 and eligibility and "eGFR" in eligibility:
            score += 0.7
        if context["age"] >= 60:
            score += 0.3

        distance = trial.get("site_distance_km")
        if geo and distance is not None and distance > geo["radius_km"]:
            continue

        scored.append(
            TrialMatch(
                id=int(trial["id"]),
                nct_id=trial.get("nct_id", f"NCT{trial['id']:08d}"),
                title=title,
                condition=condition,
                phase=trial.get("phase", ""),
                status=trial.get("status", ""),
                site_distance_km=trial.get("site_distance_km"),
                suitability=round(score, 2),
                why_match=eligibility or f"Matches diagnosis {context['diagnosis']}",
            )
        )

    scored.sort(key=lambda item: item["suitability"], reverse=True)
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
        return {}

    parsed = _extract_json_block(raw) or {}
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
    if OPENAI_API_KEY and state.get("analyses"):
        evidence_pack["llm_model"] = OPENAI_MODEL
    if state.get("llm_notes"):
        evidence_pack["notes"] = str(state["llm_notes"])
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
