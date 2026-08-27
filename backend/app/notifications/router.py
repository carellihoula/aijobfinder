from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.notifications import service as notifications_svc
from app.notifications.schemas import NotificationResponse
from app.users.models import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await notifications_svc.list_for_user(db, current_user.id)


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await notifications_svc.get_unread_count(db, current_user.id)
    return {"count": count}


@router.post("/{notification_id}/read", response_model=None)
async def mark_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await notifications_svc.mark_read(db, notification_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await notifications_svc.mark_all_read(db, current_user.id)
    return {"marked": count}


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await notifications_svc.delete_notification(db, notification_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
