from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AnalysisResponse(BaseModel):
    id: UUID
    user_id: UUID
    cv_id: Optional[UUID] = None
    status: str
    search_filters: Optional[dict] = None
    keywords: Optional[list[str]] = None
    matches: Optional[list] = None
    final_report: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}