"""Brute-force protection for /auth/login - Redis-backed fixed-window
counters, checked before the password is even verified so a locked-out
attempt doesn't pay bcrypt's cost either.

Two independent counters:
- per email: stops repeated guessing against one known account
- per source IP: stops credential stuffing across many accounts from one
  source (a much higher threshold, since one IP can legitimately represent
  many users behind NAT/a corporate network)

A successful login clears the email counter (not the IP one - one successful
login doesn't vindicate everything else that IP has been trying).
"""
import redis.asyncio as aioredis
from fastapi import HTTPException

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

EMAIL_MAX_ATTEMPTS = 5
IP_MAX_ATTEMPTS = 20
WINDOW_SECONDS = 15 * 60


def _r() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _email_key(email: str) -> str:
    return f"login_fail:email:{email.strip().lower()}"


def _ip_key(ip: str) -> str:
    return f"login_fail:ip:{ip}"


async def check_login_rate_limit(email: str, ip: str) -> None:
    """Raise 429 if either counter is already at its limit. Fails open (logs
    and allows the attempt) if Redis itself is unreachable - a Redis hiccup
    must not turn into a full login outage."""
    try:
        r = _r()
        email_count, ip_count = await r.mget(_email_key(email), _ip_key(ip))
        email_count = int(email_count or 0)
        ip_count = int(ip_count or 0)
    except Exception as exc:
        logger.warning("[auth] Rate limit check failed (Redis unreachable?): %s", exc)
        return

    if email_count >= EMAIL_MAX_ATTEMPTS or ip_count >= IP_MAX_ATTEMPTS:
        ttl = await r.ttl(_email_key(email) if email_count >= EMAIL_MAX_ATTEMPTS else _ip_key(ip))
        wait_min = max(1, (ttl if ttl and ttl > 0 else WINDOW_SECONDS) // 60)
        raise HTTPException(
            status_code=429,
            detail=f"Trop de tentatives échouées. Réessayez dans {wait_min} min.",
        )


async def record_failed_login(email: str, ip: str) -> None:
    try:
        r = _r()
        for key in (_email_key(email), _ip_key(ip)):
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, WINDOW_SECONDS)
    except Exception as exc:
        logger.warning("[auth] Failed to record login failure (Redis unreachable?): %s", exc)


async def clear_login_rate_limit(email: str) -> None:
    try:
        await _r().delete(_email_key(email))
    except Exception as exc:
        logger.warning("[auth] Failed to clear login rate limit (Redis unreachable?): %s", exc)