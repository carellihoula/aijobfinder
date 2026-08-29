from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    is_verified: bool
    created_at: datetime
    avatar_key: str | None = None
    avatar_url: str | None = None  # Google-provided profile picture, when no avatar_key is set
    has_password: bool = False     # false for Google-only accounts - hides "change password" UI

    model_config = {"from_attributes": True}