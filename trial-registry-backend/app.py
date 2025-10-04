"""Simple FastAPI service for managing clinical trial information."""
from __future__ import annotations

import os
from datetime import date
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("TRIAL_REGISTRY_ALLOW_ORIGINS", "*").split(",")
    if origin.strip()
]
if not ALLOW_ORIGINS:
    ALLOW_ORIGINS = ["*"]

app = FastAPI(
    title=os.getenv("TRIAL_REGISTRY_TITLE", "Clinical Research Services API"),
    description=os.getenv(
        "TRIAL_REGISTRY_DESCRIPTION",
        "Minimal REST API for managing clinical trials",
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Trial(BaseModel):
    """Represents a clinical trial tracked by the service."""

    id: int = Field(..., example=1)
    nct_id: str = Field(..., example="NCT01234567")
    title: str = Field(..., example="Immunotherapy Study for Lung Cancer")
    condition: str = Field(..., example="Non-small cell lung cancer")
    phase: str = Field(..., example="Phase II")
    status: str = Field(..., example="Recruiting")
    principal_investigator: str = Field(..., example="Dr. Jane Doe")
    start_date: date = Field(..., example="2024-01-15")
    end_date: Optional[date] = Field(None, example="2025-06-30")
    site_distance_km: Optional[float] = Field(
        None, example=12.5, description="Approximate distance from patient in km"
    )
    eligibility_summary: Optional[str] = Field(
        None,
        example="Adults 40-75 with type 2 diabetes and eGFR 45-60",
    )


class TrialCreate(BaseModel):
    """Payload for creating a new clinical trial."""

    nct_id: Optional[str] = None
    title: str
    condition: str
    phase: str
    status: str
    principal_investigator: str
    start_date: date
    end_date: Optional[date] = None


# Seed with a couple of sample trials so the API is self-documenting.
_trials: List[Trial] = [
    Trial(
        id=1,
        nct_id="NCT05566789",
        title="SGLT2i Outcomes in CKD Stage 3",
        condition="Type 2 diabetes mellitus",
        phase="Phase III",
        status="Recruiting",
        principal_investigator="Dr. Amina Perera",
        start_date=date(2023, 9, 1),
        end_date=None,
        site_distance_km=12.4,
        eligibility_summary="Adults 40-75 with type 2 diabetes and eGFR 45-60",
    ),
    Trial(
        id=2,
        nct_id="NCT07654321",
        title="GLP-1 RA Renal Outcomes Registry",
        condition="Type 2 diabetes mellitus",
        phase="Phase II",
        status="Recruiting",
        principal_investigator="Dr. Liam Chen",
        start_date=date(2024, 2, 12),
        end_date=date(2025, 5, 30),
        site_distance_km=14.9,
        eligibility_summary="T2D adults with eGFR 30-60 on stable metformin",
    ),
    Trial(
        id=3,
        nct_id="NCT09999888",
        title="CardioHealth Outcomes Study",
        condition="Hypertension",
        phase="Phase III",
        status="Completed",
        principal_investigator="Dr. Amina Perera",
        start_date=date(2021, 5, 1),
        end_date=date(2023, 3, 10),
        site_distance_km=52.0,
        eligibility_summary="Adults with resistant hypertension",
    ),
]


@app.get("/services", summary="Describe the clinical research services")
def get_services() -> dict:
    return {
        "name": "Clinical Research Services",
        "description": "Provides planning and day-to-day management for clinical trials.",
        "capabilities": [
            "Study design consultation",
            "Site coordination",
            "Regulatory submission support",
            "Participant recruitment",
        ],
    }


@app.get("/trials", response_model=List[Trial], summary="List clinical trials")
def list_trials() -> List[Trial]:
    return _trials


@app.get("/trials/{trial_id}", response_model=Trial, summary="Get a single trial by id")
def get_trial(trial_id: int) -> Trial:
    for trial in _trials:
        if trial.id == trial_id:
            return trial
    raise HTTPException(status_code=404, detail="Trial not found")


@app.post(
    "/trials",
    response_model=Trial,
    status_code=201,
    summary="Create a new clinical trial",
)
def create_trial(payload: TrialCreate) -> Trial:
    next_id = max((trial.id for trial in _trials), default=0) + 1
    data = payload.dict()
    nct_id = data.pop("nct_id") or f"NCT{next_id:08d}"
    trial = Trial(id=next_id, nct_id=nct_id, **data)
    _trials.append(trial)
    return trial
