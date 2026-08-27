from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=1800,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    from app.users.models import User                              # noqa: F401
    from app.cv.models import CV                                   # noqa: F401
    from app.analysis.models import Analysis                       # noqa: F401
    from app.applications.models import Application  # noqa: F401
    from app.notifications.models import Notification              # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)