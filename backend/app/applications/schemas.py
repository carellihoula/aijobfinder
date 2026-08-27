from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

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

    model_config = {"from_attributes": True}