from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select, update
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


async def get_latest_analysis_for_user(db: AsyncSession, user_id: UUID) -> Analysis | None:
    """Return the active analysis for this user, or the most recent if none is active."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.user_id == user_id, Analysis.is_active == True)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    active = result.scalar_one_or_none()
    if active:
        return active
    # Fallback for existing rows that predate the is_active column
    result = await db.execute(
        select(Analysis)
        .where(Analysis.user_id == user_id)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def deactivate_user_analyses(db: AsyncSession, user_id: UUID) -> None:
    """Mark all existing analyses for this user as inactive before creating a new one."""
    await db.execute(
        update(Analysis)
        .where(Analysis.user_id == user_id)
        .values(is_active=False)
    )
    await db.commit()


async def get_stale_analyses(db: AsyncSession, cortex_updated_at: datetime) -> list[Analysis]:
    """Return active completed analyses whose cortex snapshot is older than cortex_updated_at."""
    result = await db.execute(
        select(Analysis).where(
            Analysis.status == "completed",
            Analysis.is_active == True,
            Analysis.cv_id.isnot(None),
            or_(
                Analysis.cortex_snapshot_at.is_(None),
                Analysis.cortex_snapshot_at < cortex_updated_at,
            ),
        )
    )
    return list(result.scalars().all())


async def get_analysis_by_id(db: AsyncSession, analysis_id: UUID) -> Analysis | None:
    """Admin-level lookup — no user_id filter."""
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    return result.scalar_one_or_none()


async def get_all_analyses(db: AsyncSession) -> list[Analysis]:
    """Return all analyses ordered by most recent. Admin only."""
    result = await db.execute(select(Analysis).order_by(Analysis.created_at.desc()))
    return list(result.scalars().all())


async def get_latest_completed_analysis_for_cv(db: AsyncSession, cv_id: UUID) -> Analysis | None:
    result = await db.execute(
        select(Analysis)
        .where(Analysis.cv_id == cv_id, Analysis.status == "completed")
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_analysis(db: AsyncSession, analysis_id: UUID, **kwargs) -> Analysis | None:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis:
        for key, value in kwargs.items():
            setattr(analysis, key, value)
        await db.commit()
        await db.refresh(analysis)
    return analysis