"""Simple FastAPI service for managing clinical trial information."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Clinical Research Services API",
    description="Minimal REST API for managing clinical trials",
    version="0.1.0",
)


class Trial(BaseModel):
    """Represents a clinical trial tracked by the service."""

    id: int = Field(..., example=1)
    title: str = Field(..., example="Immunotherapy Study for Lung Cancer")
    condition: str = Field(..., example="Non-small cell lung cancer")
    phase: str = Field(..., example="Phase II")
    status: str = Field(..., example="Recruiting")
    principal_investigator: str = Field(..., example="Dr. Jane Doe")
    start_date: date = Field(..., example="2024-01-15")
    end_date: Optional[date] = Field(None, example="2025-06-30")


class TrialCreate(BaseModel):
    """Payload for creating a new clinical trial."""

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
        title="CardioHealth Outcomes Study",
        condition="Hypertension",
        phase="Phase III",
        status="Active",
        principal_investigator="Dr. Amina Perera",
        start_date=date(2023, 9, 1),
        end_date=None,
    ),
    Trial(
        id=2,
        title="NeuroBalance Cognitive Therapy",
        condition="Parkinson's Disease",
        phase="Phase II",
        status="Recruiting",
        principal_investigator="Dr. Liam Chen",
        start_date=date(2024, 2, 12),
        end_date=date(2025, 5, 30),
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
    trial = Trial(id=next_id, **payload.dict())
    _trials.append(trial)
    return trial
