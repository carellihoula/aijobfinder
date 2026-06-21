"""
Keyword registry — Redis SET that accumulates job search queries from real user pipelines.
The nightly cron reads from here instead of static seed keywords.
"""
import redis.asyncio as aioredis

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

_KEY = "cortex:keyword_registry"


def _r() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def register_keywords(keywords: list[str]) -> None:
    """Add keywords to the registry. Duplicates are ignored (SET semantics)."""
    if not keywords:
        return
    async with _r() as r:
        await r.sadd(_KEY, *keywords)
    logger.debug("[registry] registered %d keywords", len(keywords))


async def get_all_keywords() -> list[str]:
    """Return all registered keywords."""
    async with _r() as r:
        members = await r.smembers(_KEY)
    return list(members)


async def keyword_count() -> int:
    async with _r() as r:
        return await r.scard(_KEY)
