from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


class CortexBase(DeclarativeBase):
    pass


def _make_engine():
    if not settings.CORTEX_DATABASE_URL:
        return None
    return create_async_engine(
        settings.CORTEX_DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


cortex_engine = _make_engine()
CortexSessionLocal = (
    async_sessionmaker(cortex_engine, expire_on_commit=False)
    if cortex_engine
    else None
)


async def get_cortex_db():
    if CortexSessionLocal is None:
        raise RuntimeError("CORTEX_DATABASE_URL is not configured")
    async with CortexSessionLocal() as session:
        yield session


async def init_cortex() -> None:
    if cortex_engine is None:
        logger.warning("[cortex] CORTEX_DATABASE_URL not set - Cortex disabled")
        return

    from app.cortex.models import CortexJob  # noqa: F401

    async with cortex_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(CortexBase.metadata.create_all)

        # create_all() only creates tables that don't exist yet - it never
        # ALTERs an existing one. This DB has no Alembic tracking (it's a
        # separate CortexBase/engine from the main app's Base, see
        # alembic/env.py), so schema evolutions on an already-existing table
        # need an explicit, idempotent ADD COLUMN here instead.
        await conn.execute(text(
            "ALTER TABLE cortex_jobs ADD COLUMN IF NOT EXISTS embedding_skills vector(1536)"
        ))
        await conn.execute(text(
            "ALTER TABLE cortex_jobs ADD COLUMN IF NOT EXISTS embedding_context vector(1536)"
        ))
        await conn.execute(text(
            "ALTER TABLE cortex_jobs DROP COLUMN IF EXISTS embedding"
        ))

    logger.info("[cortex] Vector DB ready")