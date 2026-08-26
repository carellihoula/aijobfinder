from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

ApplicationStatus = Literal["applied", "in_progress", "rejected", "accepted"]
CoverLetterStatus = Literal["pending", "processing", "completed", "failed"]


class PreviewRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None


class PreviewResponse(BaseModel):
    title: str
    company: str
    location: str = ""
    description: str
    url: Optional[str] = None


class CreateApplicationRequest(BaseModel):
    title: str
    company: str
    location: str = ""
    description: str
    url: Optional[str] = None
    suggestion: str = ""


class RefineCoverLetterRequest(BaseModel):
    suggestion: str = ""


class UpdateApplicationRequest(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    status: Optional[ApplicationStatus] = None


def _empty_str_to_none(v):
    return None if v == "" else v


class CreateStepRequest(BaseModel):
    label: str
    status: ApplicationStatus = "applied"
    date: Optional[date] = None
    notes: Optional[str] = None

    _blank_date = field_validator("date", mode="before")(_empty_str_to_none)
    _blank_notes = field_validator("notes", mode="before")(_empty_str_to_none)


class UpdateStepRequest(BaseModel):
    label: Optional[str] = None
    status: Optional[ApplicationStatus] = None
    date: Optional[date] = None
    notes: Optional[str] = None

    _blank_date = field_validator("date", mode="before")(_empty_str_to_none)
    _blank_notes = field_validator("notes", mode="before")(_empty_str_to_none)


class ApplicationStepResponse(BaseModel):
    id: UUID
    label: str
    status: ApplicationStatus
    date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationResponse(BaseModel):
    id: UUID
    title: str
    company: str
    url: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    status: ApplicationStatus
    cover_letter_status: CoverLetterStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    steps: list[ApplicationStepResponse] = []

    model_config = {"from_attributes": True}