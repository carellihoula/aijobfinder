from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cover_letter.models import AnalysisCoverLetter


async def get_cover_letter(db: AsyncSession, analysis_id: UUID, job_index: int) -> AnalysisCoverLetter | None:
    result = await db.execute(
        select(AnalysisCoverLetter).where(
            AnalysisCoverLetter.analysis_id == analysis_id,
            AnalysisCoverLetter.job_index == job_index,
        )
    )
    return result.scalar_one_or_none()


async def upsert_cover_letter(
    db: AsyncSession, analysis_id: UUID, job_index: int, content: dict
) -> AnalysisCoverLetter:
    existing = await get_cover_letter(db, analysis_id, job_index)
    if existing:
        existing.content = content
        await db.commit()
        await db.refresh(existing)
        return existing

    row = AnalysisCoverLetter(analysis_id=analysis_id, job_index=job_index, content=content)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row