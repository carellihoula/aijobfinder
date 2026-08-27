from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    link: Optional[str] = None
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
