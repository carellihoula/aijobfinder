from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_admin_user
from app.db.session import get_db
from app.logger import get_logger
from app.users import service as users_svc
from app.users.models import User

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = get_logger(__name__)


class UserSummary(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    is_admin: bool

    model_config = {"from_attributes": True}


@router.get("/users", response_model=list[UserSummary])
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users with their admin status."""
    return await users_svc.get_all_users(db)


@router.patch("/users/{user_id}/promote", response_model=UserSummary)
async def promote_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Grant admin rights to a user."""
    user = await users_svc.set_admin_status(db, user_id, is_admin=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info("[admin] %s promoted to admin by %s", user.email, admin.email)
    return user


@router.patch("/users/{user_id}/demote", response_model=UserSummary)
async def demote_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke admin rights from a user."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin rights")
    user = await users_svc.set_admin_status(db, user_id, is_admin=False)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info("[admin] %s demoted by %s", user.email, admin.email)
    return user