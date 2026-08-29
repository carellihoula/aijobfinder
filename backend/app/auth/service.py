import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.utils import (
    create_access_token,
    create_refresh_token_raw,
    create_typed_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.config import settings
from app.email import send_verification_email
from app.logger import get_logger
from app.users.models import User
from app.users.service import (
    create_google_user,
    create_user,
    get_user_by_email,
    get_user_by_google_id,
    link_google_account,
)

logger = get_logger(__name__)


async def register(db: AsyncSession, data: RegisterRequest) -> User:
    if await get_user_by_email(db, data.email):
        logger.warning("[auth] Registration failed - email already exists: %s", data.email)
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await create_user(db, data.email, hash_password(data.password), data.full_name)
    logger.info("[auth] New user registered: %s (id=%s)", data.email, user.id)

    verify_token = create_typed_token(str(user.id), "verify", expires_minutes=60 * 24)
    await send_verification_email(user.email, verify_token)

    return user


async def login(db: AsyncSession, data: LoginRequest) -> User:
    user = await get_user_by_email(db, data.email)
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        logger.warning("[auth] Failed login attempt: %s", data.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    logger.info("[auth] User logged in: %s (id=%s)", data.email, user.id)
    return user


async def google_login(db: AsyncSession, id_token_str: str) -> tuple[User, bool]:
    """Verifies the Google ID token's signature/audience (no client secret, no
    server-side redirect - the token already came straight from Google to the
    browser via Google Identity Services), then finds-or-creates the user.

    Returns (user, is_new_user) - the frontend needs to know if this is a brand
    new account, since every new user must upload a CV before anything else works."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google sign-in is not configured")

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    google_id = claims["sub"]
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")
    full_name = claims.get("name")
    avatar_url = claims.get("picture")

    user = await get_user_by_google_id(db, google_id)
    if user:
        return user, False

    user = await get_user_by_email(db, email)
    if user:
        logger.info("[auth] Linked Google account to existing user: %s (id=%s)", email, user.id)
        return await link_google_account(db, user, google_id, avatar_url), False

    user = await create_google_user(db, email, google_id, full_name, avatar_url)
    logger.info("[auth] New user registered via Google: %s (id=%s)", email, user.id)
    return user, True


# ── Refresh tokens ──────────────────────────────────────────────────────────

async def issue_refresh_token(db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID | None = None) -> str:
    """Issues a new refresh token, starting a new rotation family unless one is
    passed in (rotation continues the same family so reuse-detection can revoke
    it as a whole)."""
    raw = create_refresh_token_raw()
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=hash_refresh_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(row)
    await db.commit()
    return raw


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[str, uuid.UUID] | None:
    """Validates + rotates a refresh token. Returns (new_raw_token, user_id), or
    None if the token is unknown/expired/already-revoked-and-reused (in which
    case the whole family is revoked as a precaution)."""
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one_or_none()
    if not row:
        return None

    if row.revoked:
        # This exact (already-rotated-out) token is being replayed - likely theft.
        logger.warning("[auth] Revoked refresh token reused - revoking family %s", row.family_id)
        await _revoke_family(db, row.family_id)
        return None

    if row.expires_at < datetime.now(timezone.utc):
        return None

    row.revoked = True
    new_raw = await issue_refresh_token(db, row.user_id, family_id=row.family_id)
    await db.commit()
    return new_raw, row.user_id


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    token_hash = hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one_or_none()
    if row:
        row.revoked = True
        await db.commit()


async def _revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked.is_(False)))
    for row in result.scalars().all():
        row.revoked = True
    await db.commit()