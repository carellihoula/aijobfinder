from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.applications.models import Application, ApplicationStep


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
    await db.refresh(application, attribute_names=["steps"])
    return application


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
    await db.commit()


async def list_applications_for_user(db: AsyncSession, user_id: UUID) -> list[Application]:
    result = await db.execute(
        select(Application)
        .where(Application.user_id == user_id)
        .options(selectinload(Application.steps))
        .order_by(Application.created_at.desc())
    )
    return list(result.scalars().all())


async def get_application(db: AsyncSession, application_id: UUID, user_id: UUID) -> Application | None:
    result = await db.execute(
        select(Application)
        .where(Application.id == application_id, Application.user_id == user_id)
        .options(selectinload(Application.steps))
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
    await db.refresh(application, attribute_names=["steps"])
    return application


async def delete_application(db: AsyncSession, application_id: UUID, user_id: UUID) -> bool:
    application = await get_application(db, application_id, user_id)
    if not application:
        return False
    await db.delete(application)
    await db.commit()
    return True


async def add_step(
    db: AsyncSession,
    application_id: UUID,
    user_id: UUID,
    label: str,
    status: str,
    date=None,
    notes: str | None = None,
) -> ApplicationStep | None:
    application = await get_application(db, application_id, user_id)
    if not application:
        return None
    step = ApplicationStep(
        application_id=application_id, label=label, status=status, date=date, notes=notes,
    )
    db.add(step)
    application.status = status
    await db.commit()
    await db.refresh(step)
    return step


async def update_step(
    db: AsyncSession,
    application_id: UUID,
    step_id: UUID,
    user_id: UUID,
    label: str | None = None,
    status: str | None = None,
    date=None,
    notes: str | None = None,
) -> ApplicationStep | None:
    application = await get_application(db, application_id, user_id)
    if not application:
        return None
    result = await db.execute(
        select(ApplicationStep).where(
            ApplicationStep.id == step_id, ApplicationStep.application_id == application_id
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        return None
    if label is not None:
        step.label = label
    if status is not None:
        step.status = status
        application.status = status
    if date is not None:
        step.date = date
    if notes is not None:
        step.notes = notes
    await db.commit()
    await db.refresh(step)
    return step


async def delete_step(db: AsyncSession, application_id: UUID, step_id: UUID, user_id: UUID) -> bool:
    application = await get_application(db, application_id, user_id)
    if not application:
        return False
    result = await db.execute(
        select(ApplicationStep).where(
            ApplicationStep.id == step_id, ApplicationStep.application_id == application_id
        )
    )
    step = result.scalar_one_or_none()
    if not step:
        return False
    await db.delete(step)
    await db.commit()
    return True
