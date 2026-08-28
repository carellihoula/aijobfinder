from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.applications.models import Application


async def create_application(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    company: str,
    description: str,
    url: str | None = None,
    summary: str | None = None,
) -> Application:
    application = Application(
        user_id=user_id, title=title, company=company, url=url, summary=summary,
        description=description, cover_letter_status="processing",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


async def fail_stale_cover_letters(db: AsyncSession, older_than_minutes: int = 15) -> list[tuple]:
    """
    Mark cover letters stuck in "processing"/"pending" as failed.

    generate_application_cover_letter only ever reaches "completed"/"failed" from
    inside its Celery task - if the worker is killed mid-task (reboot, broker
    state lost) the row is orphaned forever, exactly like the analysis pipeline's
    equivalent failure mode. Scheduled periodically to reconcile these.

    Returns (user_id, application_id, title) for each affected row, so the caller
    can notify the right user.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    result = await db.execute(
        update(Application)
        .where(Application.cover_letter_status.in_(["processing", "pending"]), Application.updated_at < cutoff)
        .values(cover_letter_status="failed")
        .returning(Application.user_id, Application.id, Application.title)
    )
    await db.commit()
    return list(result.all())


async def set_cover_letter_result(
    db: AsyncSession,
    application_id: UUID,
    status: str,
    content: dict | None,
) -> None:
    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        return
    application.cover_letter_status = status
    application.cover_letter_content = content
    if status == "completed":
        application.edited_body = None  # a fresh AI generation supersedes any manual edit
    await db.commit()


async def update_edited_body(db: AsyncSession, application_id: UUID, text: str) -> Application | None:
    result = await db.execute(select(Application).where(Application.id == application_id))
    application = result.scalar_one_or_none()
    if not application:
        return None
    application.edited_body = text
    await db.commit()
    await db.refresh(application)
    return application


async def list_applications_for_user(db: AsyncSession, user_id: UUID) -> list[Application]:
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
    )
    return list(result.scalars().all())


async def get_application(db: AsyncSession, application_id: UUID, user_id: UUID) -> Application | None:
    result = await db.execute(
        select(Application).where(Application.id == application_id, Application.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_application(
    db: AsyncSession,
    application_id: UUID,
    user_id: UUID,
    title: str | None = None,
    company: str | None = None,
    status: str | None = None,
) -> Application | None:
    application = await get_application(db, application_id, user_id)
    if not application:
        return None
    if title is not None:
        application.title = title
    if company is not None:
        application.company = company
    if status is not None:
        application.status = status
    await db.commit()
    await db.refresh(application)
    return application


async def delete_application(db: AsyncSession, application_id: UUID, user_id: UUID) -> bool:
    application = await get_application(db, application_id, user_id)
    if not application:
        return False
    await db.delete(application)
    await db.commit()
    return True
