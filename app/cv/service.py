from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cv.models import CV


async def create_cv(
    db: AsyncSession,
    user_id: UUID | None = None,
    cv_id: UUID | None = None,
    pdf_path: str | None = None,
    pdf_hash: str | None = None,
) -> CV:
    cv = CV(id=cv_id, user_id=user_id, data={}, pdf_path=pdf_path, pdf_hash=pdf_hash)
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return cv


async def get_latest_cv_for_user(db: AsyncSession, user_id: UUID) -> CV | None:
    """Return the most recent CV with a pdf_path for this user."""
    result = await db.execute(
        select(CV)
        .where(CV.user_id == user_id, CV.pdf_path.isnot(None))
        .order_by(CV.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_cv_by_hash(db: AsyncSession, user_id: UUID, pdf_hash: str) -> CV | None:
    """Find an existing CV for this user by PDF content hash."""
    result = await db.execute(
        select(CV)
        .where(CV.user_id == user_id, CV.pdf_hash == pdf_hash)
        .order_by(CV.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_cv(db: AsyncSession, cv_id: UUID, **kwargs) -> CV | None:
    result = await db.execute(select(CV).where(CV.id == cv_id))
    cv = result.scalar_one_or_none()
    if cv:
        for key, value in kwargs.items():
            setattr(cv, key, value)
        await db.commit()
        await db.refresh(cv)
    return cv


async def get_cv(db: AsyncSession, cv_id: UUID) -> CV | None:
    result = await db.execute(select(CV).where(CV.id == cv_id))
    return result.scalar_one_or_none()