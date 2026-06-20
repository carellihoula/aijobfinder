from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.models import Analysis


async def create_analysis(db: AsyncSession, user_id: UUID, cv_id: UUID | None = None) -> Analysis:
    analysis = Analysis(user_id=user_id, cv_id=cv_id)
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def get_analysis(db: AsyncSession, analysis_id: UUID, user_id: UUID) -> Analysis | None:
    result = await db.execute(
        select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_analyses(db: AsyncSession, user_id: UUID) -> list[Analysis]:
    result = await db.execute(
        select(Analysis).where(Analysis.user_id == user_id).order_by(Analysis.created_at.desc())
    )
    return list(result.scalars().all())


async def update_analysis(db: AsyncSession, analysis_id: UUID, **kwargs) -> Analysis | None:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis:
        for key, value in kwargs.items():
            setattr(analysis, key, value)
        await db.commit()
        await db.refresh(analysis)
    return analysis