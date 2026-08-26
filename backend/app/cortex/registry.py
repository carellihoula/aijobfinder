"""
Keyword registry — Redis SET that accumulates job search queries from real user pipelines.
The nightly cron reads from here instead of static seed keywords.

Also tracks cortex_updated_at: the last time the ingestion actually stored new jobs.
Used to decide whether to re-run per-user analyses or skip (nothing new).
"""
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

_KEYWORDS_KEY   = "cortex:keyword_registry"
_UPDATED_AT_KEY = "cortex:updated_at"


def _r() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def register_keywords(keywords: list[str]) -> None:
    """Add keywords to the registry. Duplicates are ignored (SET semantics)."""
    if not keywords:
        return
    async with _r() as r:
        await r.sadd(_KEYWORDS_KEY, *keywords)
    logger.debug("[registry] registered %d keywords", len(keywords))


async def get_all_keywords() -> list[str]:
    """Return all registered keywords."""
    async with _r() as r:
        members = await r.smembers(_KEYWORDS_KEY)
    return list(members)


async def set_cortex_updated_at() -> None:
    """Called by ingestion when new jobs are actually stored in the Cortex."""
    now = datetime.now(timezone.utc).isoformat()
    async with _r() as r:
        await r.set(_UPDATED_AT_KEY, now)
    logger.info("[registry] cortex_updated_at set to %s", now)


async def get_cortex_updated_at() -> datetime | None:
    """Return the last time the Cortex received new jobs, or None if never."""
    async with _r() as r:
        val = await r.get(_UPDATED_AT_KEY)
    if not val:
        return None
    return datetime.fromisoformat(val)
