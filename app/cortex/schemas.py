from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CortexJobSchema(BaseModel):
    id: UUID
    job_hash: str
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    contract_type: str
    remote: bool
    skills: list[str]
    seniority: str
    is_active: bool
    created_at: datetime
    last_seen: datetime

    model_config = {"from_attributes": True}


class IngestionRequest(BaseModel):
    keywords: list[str]
    locations: list[str] = []


class IngestionResponse(BaseModel):
    status: str
    fetched: int = 0
    new: int = 0
    stored: int = 0


class CortexStatsResponse(BaseModel):
    total_jobs: int
    active_jobs: int