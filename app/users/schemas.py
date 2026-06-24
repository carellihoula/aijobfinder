from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    avatar_key: str | None = None

    model_config = {"from_attributes": True}