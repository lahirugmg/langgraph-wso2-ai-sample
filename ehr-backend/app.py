"""FastAPI service that mocks basic EHR capabilities for demo workflows."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="EHR Service",
    description=
    "Demo API offering patient summaries, lab retrieval, and medication order drafts.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PatientDemographics(BaseModel):
    name: str
    age: int
    gender: str
    mrn: str = Field(..., description="Medical record number")


class VitalSigns(BaseModel):
    systolic: int
    diastolic: int
    heart_rate: int
    weight_kg: float
    updated_at: datetime


class PatientSummary(BaseModel):
    demographics: PatientDemographics
    problems: List[str]
    medications: List[str]
    vitals: VitalSigns
    last_a1c: float = Field(..., description="Most recent HbA1c value")
    last_egfr: float = Field(..., description="Most recent eGFR value")


class LabValue(BaseModel):
    name: str
    value: float
    unit: str
    collected_at: datetime


class LabResponse(BaseModel):
    patient_id: str
    labs: List[LabValue]


class MedicationOrder(BaseModel):
    patient_id: str
    medication: str
    dose: str
    route: str
    frequency: str
    rationale: Optional[str] = None


class OrderResponse(BaseModel):
    order_id: str
    status: str


class GeoFilter(BaseModel):
    lat: float
    lon: float
    radius_km: float


class EvidenceSearchRequest(BaseModel):
    condition: str
    comorbidity: List[str] = Field(default_factory=list)
    age: int
    geo: GeoFilter


class TrialMatch(BaseModel):
    id: str
    name: str
    distance_km: float
    eligibility_summary: str


class EvidenceSearchResponse(BaseModel):
    guideline_ids: List[str]
    rct_ids: List[str]
    nearby_trials: List[TrialMatch]


# ---------------------------------------------------------------------------
# In-memory demo data
# ---------------------------------------------------------------------------
_PATIENT_SUMMARIES: Dict[str, PatientSummary] = {
    "12345": PatientSummary(
        demographics=PatientDemographics(
            name="Jordan Matthews",
            age=62,
            gender="female",
            mrn="12345",
        ),
        problems=["Type 2 diabetes mellitus", "CKD stage 3", "Hypertension"],
        medications=["Metformin 1000 mg BID", "Lisinopril 20 mg daily"],
        vitals=VitalSigns(
            systolic=128,
            diastolic=78,
            heart_rate=72,
            weight_kg=82.5,
            updated_at=datetime(2024, 9, 12, 9, 45),
        ),
        last_a1c=7.4,
        last_egfr=54.0,
    ),
    "12873": PatientSummary(
        demographics=PatientDemographics(
            name="Avery Patel",
            age=58,
            gender="female",
            mrn="12873",
        ),
        problems=[
            "Type 2 diabetes mellitus",
            "Chronic kidney disease stage 3",
            "Hypertension",
        ],
        medications=["Metformin 1000 mg BID", "Losartan 50 mg daily"],
        vitals=VitalSigns(
            systolic=132,
            diastolic=82,
            heart_rate=76,
            weight_kg=79.8,
            updated_at=datetime(2025, 9, 12, 9, 15),
        ),
        last_a1c=8.2,
        last_egfr=44.0,
    ),
}

_PATIENT_LABS: Dict[str, List[LabValue]] = {
    "12345": [
        LabValue(
            name="HbA1c",
            value=7.4,
            unit="%",
            collected_at=datetime(2024, 9, 10, 8, 30),
        ),
        LabValue(
            name="HbA1c",
            value=7.8,
            unit="%",
            collected_at=datetime(2024, 6, 5, 8, 30),
        ),
        LabValue(
            name="eGFR",
            value=54.0,
            unit="mL/min/1.73m2",
            collected_at=datetime(2024, 9, 10, 8, 35),
        ),
        LabValue(
            name="eGFR",
            value=58.0,
            unit="mL/min/1.73m2",
            collected_at=datetime(2024, 3, 15, 8, 35),
        ),
        LabValue(
            name="LDL",
            value=82,
            unit="mg/dL",
            collected_at=datetime(2024, 9, 1, 8, 0),
        ),
    ],
    "12873": [
        LabValue(
            name="HbA1c",
            value=8.2,
            unit="%",
            collected_at=datetime(2025, 9, 5, 8, 0),
        ),
        LabValue(
            name="HbA1c",
            value=8.6,
            unit="%",
            collected_at=datetime(2025, 6, 2, 8, 10),
        ),
        LabValue(
            name="HbA1c",
            value=8.9,
            unit="%",
            collected_at=datetime(2025, 3, 3, 8, 5),
        ),
        LabValue(
            name="eGFR",
            value=44.0,
            unit="mL/min/1.73m2",
            collected_at=datetime(2025, 9, 12, 7, 55),
        ),
        LabValue(
            name="eGFR",
            value=46.0,
            unit="mL/min/1.73m2",
            collected_at=datetime(2025, 6, 9, 7, 50),
        ),
        LabValue(
            name="eGFR",
            value=48.0,
            unit="mL/min/1.73m2",
            collected_at=datetime(2025, 3, 10, 7, 45),
        ),
    ],
}


# ---------------------------------------------------------------------------
# EHR service endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/patients/{patient_id}/summary",
    response_model=PatientSummary,
    summary="Get demographics, problem list, meds, vitals, and key labs",
)
def get_patient_summary(patient_id: str) -> PatientSummary:
    summary = _PATIENT_SUMMARIES.get(patient_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Patient not found")
    return summary


@app.get(
    "/patients/{patient_id}/labs",
    response_model=LabResponse,
    summary="Retrieve lab history for a patient",
)
def get_patient_labs(
    patient_id: str,
    names: Optional[str] = Query(
        default=None,
        description="Comma-separated list of lab names to filter",
    ),
    last_n: Optional[int] = Query(
        default=None,
        ge=1,
        description="Return only the most recent N lab results after filtering",
    ),
) -> LabResponse:
    lab_history = _PATIENT_LABS.get(patient_id)
    if not lab_history:
        raise HTTPException(status_code=404, detail="Patient not found or no lab history")

    filtered = list(lab_history)
    if names:
        allowed = {name.strip().lower() for name in names.split(",") if name.strip()}
        filtered = [lab for lab in filtered if lab.name.lower() in allowed]

    # Sort newest first for consistent slicing
    filtered.sort(key=lambda lab: lab.collected_at, reverse=True)

    if last_n is not None:
        filtered = filtered[:last_n]

    return LabResponse(patient_id=patient_id, labs=filtered)


@app.post(
    "/orders/medication",
    response_model=OrderResponse,
    status_code=201,
    summary="Create a draft medication order",
)
def create_medication_order(order: MedicationOrder) -> OrderResponse:
    # No persistence in the demo—just echo success with a generated draft id.
    order_id = f"draft-{uuid4()}"
    return OrderResponse(order_id=order_id, status="draft created")


# ---------------------------------------------------------------------------
# Trial registry endpoint
# ---------------------------------------------------------------------------
@app.post(
    "/evidence/search",
    response_model=EvidenceSearchResponse,
    summary="Search for supporting evidence and nearby trials",
)
def search_evidence(request: EvidenceSearchRequest) -> EvidenceSearchResponse:
    # Simple mock logic to return canned evidence ids and filtered trials
    guideline_ids = ["ADA-2024-DM2"]
    rct_ids = ["NCT01234567", "NCT07654321"]

    # Demo nearby trial filters using naive distance check (not great-circle)
    all_trials = [
        TrialMatch(
            id="NCT05566789",
            name="Renal Outcomes in Diabetes",
            distance_km=12.4,
            eligibility_summary="Adults 40-75 with type 2 diabetes and eGFR 45-60",
        ),
        TrialMatch(
            id="NCT08899881",
            name="Cardiometabolic Risk Reduction Study",
            distance_km=48.0,
            eligibility_summary="Type 2 diabetes with uncontrolled A1c > 7 despite therapy",
        ),
    ]

    # Limit to trials within the requested radius if specified
    nearby_trials = [
        trial for trial in all_trials if trial.distance_km <= request.geo.radius_km
    ][:2]

    return EvidenceSearchResponse(
        guideline_ids=guideline_ids,
        rct_ids=rct_ids,
        nearby_trials=nearby_trials,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
