from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.dependencies import get_current_user
from app.auth.rate_limit import check_login_rate_limit, clear_login_rate_limit, record_failed_login
from app.auth.schemas import GoogleAuthRequest, LoginRequest, RegisterRequest
from app.auth.utils import (
    create_access_token,
    create_reset_token,
    create_typed_token,
    decode_token,
    decode_typed_token,
    hash_password,
    password_reset_fingerprint,
)
from app.config import settings
from app.db.session import get_db
from app.email import send_reset_email, send_verification_email
from app.users.models import User
from app.users.service import get_user_by_email, get_user_by_id, update_user_password, verify_user

router = APIRouter(prefix="/auth", tags=["Auth"])

_ACCESS_COOKIE  = "token"
_REFRESH_COOKIE = "refresh_token"


def _set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        # Only sent back to /auth/* (refresh, logout) - never exposed to every
        # other request, unlike the access token.
        path="/auth",
    )


async def _issue_tokens(response: Response, db: AsyncSession, user: User) -> None:
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = await service.issue_refresh_token(db, user.id)
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token)


@router.post("/register", status_code=201)
async def register(data: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await service.register(db, data)
    await _issue_tokens(response, db, user)
    return {"ok": True}


@router.post("/login")
async def login(data: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    await check_login_rate_limit(data.email, ip)
    try:
        user = await service.login(db, data)
    except HTTPException:
        await record_failed_login(data.email, ip)
        raise
    await clear_login_rate_limit(data.email)
    await _issue_tokens(response, db, user)
    return {"ok": True}


@router.post("/google")
async def google_auth(data: GoogleAuthRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user, is_new_user = await service.google_login(db, data.id_token)
    await _issue_tokens(response, db, user)
    return {"ok": True, "is_new_user": is_new_user}


@router.post("/refresh")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw_token = request.cookies.get(_REFRESH_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await service.rotate_refresh_token(db, raw_token)
    if not result:
        response.delete_cookie(key=_ACCESS_COOKIE, path="/")
        response.delete_cookie(key=_REFRESH_COOKIE, path="/auth")
        raise HTTPException(status_code=401, detail="Session expired - please log in again")

    new_refresh_token, user_id = result
    access_token = create_access_token({"sub": str(user_id)})
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, new_refresh_token)
    return {"ok": True}


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw_token = request.cookies.get(_REFRESH_COOKIE)
    if raw_token:
        await service.revoke_refresh_token(db, raw_token)
    response.delete_cookie(key=_ACCESS_COOKIE, path="/")
    response.delete_cookie(key=_REFRESH_COOKIE, path="/auth")
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
        # Fingerprints the *current* password hash into the token so it stops
        # validating the instant the password actually changes - see
        # reset_password below and password_reset_fingerprint's docstring.
        token = create_reset_token(str(user.id), user.hashed_password)
        await send_reset_email(user.email, token)
    # Always return ok - don't leak whether the email exists
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    from uuid import UUID
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    payload = decode_token(data.token)
    if not payload or payload.get("type") != "reset":
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    user = await get_user_by_id(db, UUID(payload["sub"]))
    # Effectively single-use: this link's fingerprint only matches the
    # password hash that was current when it was issued. Once a reset
    # succeeds (via this link or another one requested earlier), the hash
    # changes and every outstanding reset link for this user stops working.
    if not user or payload.get("pwfp") != password_reset_fingerprint(user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")

    await update_user_password(db, user.id, hash_password(data.new_password))
    return {"ok": True}
