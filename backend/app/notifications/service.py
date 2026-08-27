from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification


async def create_notification(
    db: AsyncSession,
    user_id: UUID,
    type: str,
    title: str,
    body: str,
    link: str | None = None,
) -> Notification:
    notification = Notification(user_id=user_id, type=type, title=title, body=body, link=link)
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def list_for_user(db: AsyncSession, user_id: UUID, limit: int = 50) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read == False)  # noqa: E712
    )
    return result.scalar() or 0


async def mark_read(db: AsyncSession, notification_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(read=True)
    )
    await db.commit()
    return bool(result.rowcount)


async def mark_all_read(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read == False)  # noqa: E712
        .values(read=True)
    )
    await db.commit()
    return result.rowcount or 0


async def delete_notification(db: AsyncSession, notification_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        delete(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    )
    await db.commit()
    return bool(result.rowcount)