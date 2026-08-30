import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    to_encode.setdefault("type", "access")  # distinguishes it from verify/reset tokens below
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token_raw() -> str:
    """Opaque random token - not a JWT. Validity is checked via DB lookup (see
    app/auth/service.py), not by decoding it, so it doesn't need to carry claims."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """Only this hash is ever stored - the raw token itself is never persisted."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def create_typed_token(user_id: str, token_type: str, expires_minutes: int) -> str:
    return create_access_token(
        {"sub": user_id, "type": token_type},
        expires_delta=timedelta(minutes=expires_minutes),
    )


def decode_typed_token(token: str, expected_type: str) -> Optional[str]:
    payload = decode_token(token)
    if not payload:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload.get("sub")


def password_reset_fingerprint(password_hash: str | None) -> str:
    """One-way fingerprint of a password hash - embedded in reset tokens
    instead of the hash itself (which must never end up inside a token that
    can land in email logs, proxies, or browser history). Comparing this
    fingerprint at redemption time against the user's *current* hash makes a
    reset token invalidate itself the instant the password actually changes -
    whether via this token or a different one issued earlier - without
    needing a DB table to track which tokens were already redeemed."""
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def create_reset_token(user_id: str, current_password_hash: str | None) -> str:
    return create_access_token(
        {
            "sub": user_id,
            "type": "reset",
            "pwfp": password_reset_fingerprint(current_password_hash),
        },
        expires_delta=timedelta(minutes=60),
    )