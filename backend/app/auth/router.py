from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.dependencies import get_current_user
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.utils import create_typed_token, decode_typed_token, hash_password
from app.config import settings
from app.db.session import get_db
from app.email import send_reset_email, send_verification_email
from app.users.models import User
from app.users.service import get_user_by_email, update_user_password, verify_user

router = APIRouter(prefix="/auth", tags=["Auth"])

_COOKIE_NAME = "token"
_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )


@router.post("/register", status_code=201)
async def register(data: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    token = await service.register(db, data)
    _set_auth_cookie(response, token)
    return {"ok": True}


@router.post("/login")
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    token = await service.login(db, data)
    _set_auth_cookie(response, token)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=_COOKIE_NAME, path="/")
    return {"ok": True}


# ── Email verification ────────────────────────────────────────────────────────

@router.post("/resend-verification")
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_verified:
        return {"ok": True}
    token = create_typed_token(str(current_user.id), "verify", expires_minutes=60 * 24)
    await send_verification_email(current_user.email, token)
    return {"ok": True}


@router.get("/verify-email")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    from uuid import UUID
    user_id = decode_typed_token(token, "verify")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    await verify_user(db, UUID(user_id))
    return {"ok": True}


# ── Password reset ────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, data.email)
    if user:
        token = create_typed_token(str(user.id), "reset", expires_minutes=60)
        await send_reset_email(user.email, token)
    # Always return ok - don't leak whether the email exists
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    from uuid import UUID
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user_id = decode_typed_token(data.token, "reset")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    await update_user_password(db, UUID(user_id), hash_password(data.new_password))
    return {"ok": True}
