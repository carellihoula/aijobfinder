from uuid import UUID

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import decode_token
from app.db.session import get_db
from app.users.service import get_user_by_id


async def get_current_user(
    token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await get_user_by_id(db, UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


async def get_admin_user(current_user=Depends(get_current_user)):
    """Restrict access to admin users.

    Admin status is a single source of truth: `users.is_admin` in the DB,
    managed via PATCH /admin/users/{id}/promote (or set directly in the DB for
    the very first admin - deliberately no env-var-based bootstrap here, that
    was a real bypass: an empty/misconfigured env var used to mean "no
    restriction" instead of "no email-based admins").
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
