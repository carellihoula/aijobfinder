from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.cortex.schemas import CortexStatsResponse, IngestionResponse
from app.logger import get_logger
from app.users.models import User

router = APIRouter(prefix="/cortex", tags=["Cortex"])
logger = get_logger(__name__)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    admin_emails = [e.strip() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
    if admin_emails and current_user.email not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/ingest/full", response_model=IngestionResponse, status_code=202)
async def ingest_full(_: User = Depends(_require_admin)):
    """Enqueue a full Cortex ingestion via Celery (all providers). Admin only."""
    from app.worker.tasks import full_ingestion
    task = full_ingestion.delay()
    logger.info("[cortex] full_ingestion enqueued — task_id=%s", task.id)
    return IngestionResponse(status="queued")


@router.delete("/jobs/cleanup", response_model=dict)
async def cleanup_old_jobs(
    days: int = 30,
    _: User = Depends(_require_admin),
):
    """Enqueue cleanup of jobs not seen in the last N days. Admin only."""
    from app.worker.tasks import cleanup_old_jobs as cleanup_task
    task = cleanup_task.delay(days=days)
    logger.info("[cortex] cleanup enqueued — task_id=%s", task.id)
    return {"status": "queued", "task_id": task.id}


@router.get("/stats", response_model=CortexStatsResponse)
async def cortex_stats(current_user: User = Depends(get_current_user)):
    """Stats about the Cortex (total and active jobs)."""
    if CortexSessionLocal is None:
        return CortexStatsResponse(total_jobs=0, active_jobs=0)
    async with CortexSessionLocal() as db:
        stats = await cortex_svc.get_stats(db)
    return CortexStatsResponse(**stats)