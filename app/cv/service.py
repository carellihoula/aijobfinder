from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cv.models import CV


async def create_cv(
    db: AsyncSession,
    user_id: UUID | None = None,
    cv_id: UUID | None = None,
    pdf_path: str | None = None,
) -> CV:
    cv = CV(id=cv_id, user_id=user_id, data={}, pdf_path=pdf_path)
    db.add(cv)
    await db.commit()
    await db.refresh(cv)
    return cv


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