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


async def list_cover_letters(db: AsyncSession, analysis_id: UUID) -> list[AnalysisCoverLetter]:
    result = await db.execute(
        select(AnalysisCoverLetter).where(AnalysisCoverLetter.analysis_id == analysis_id)
    )
    return list(result.scalars().all())


async def upsert_cover_letter(
    db: AsyncSession, analysis_id: UUID, job_index: int, content: dict
) -> AnalysisCoverLetter:
    existing = await get_cover_letter(db, analysis_id, job_index)
    if existing:
        existing.content = content
        existing.edited_body = None  # a fresh AI generation supersedes any manual edit
        await db.commit()
        await db.refresh(existing)
        return existing

    row = AnalysisCoverLetter(analysis_id=analysis_id, job_index=job_index, content=content)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_edited_body(
    db: AsyncSession, analysis_id: UUID, job_index: int, text: str
) -> AnalysisCoverLetter | None:
    existing = await get_cover_letter(db, analysis_id, job_index)
    if not existing:
        return None
    existing.edited_body = text
    await db.commit()
    await db.refresh(existing)
    return existing