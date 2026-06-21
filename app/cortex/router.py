from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.cortex.ingestion import run_ingestion, run_seed_ingestion
from app.cortex.schemas import CortexStatsResponse, IngestionRequest, IngestionResponse
from app.logger import get_logger
from app.users.models import User

router = APIRouter(prefix="/cortex", tags=["Cortex"])
logger = get_logger(__name__)


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow only users whose email is listed in ADMIN_EMAILS env var."""
    admin_emails = [e.strip() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]
    if admin_emails and current_user.email not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/ingest", response_model=IngestionResponse)
async def ingest_sync(
    body: IngestionRequest,
    _: User = Depends(_require_admin),
):
    """Synchronous ingestion with explicit keywords — also registers them for future crons."""
    from app.cortex.registry import register_keywords
    await register_keywords(body.keywords)
    result = await run_seed_ingestion(body.keywords, body.locations)
    return IngestionResponse(status="done", **result)


@router.post("/ingest/full", response_model=IngestionResponse, status_code=202)
async def ingest_full(
    locations: list[str] | None = None,
    _: User = Depends(_require_admin),
):
    """
    Enqueue a Cortex refresh via Celery (admin only).
    Uses the keyword registry built from real user pipelines.
    The same task runs automatically every night at 2am via Celery Beat.
    """
    from app.worker.tasks import full_ingestion
    task = full_ingestion.delay(locations=locations or None)
    logger.info("[cortex] full_ingestion enqueued — task_id=%s", task.id)
    return IngestionResponse(status="queued", **{"fetched": 0, "new": 0, "stored": 0})


@router.delete("/jobs/cleanup", response_model=dict)
async def cleanup_old_jobs(
    days: int = 30,
    _: User = Depends(_require_admin),
):
    """Enqueue cleanup of jobs not seen in the last N days via Celery (admin only)."""
    from app.worker.tasks import cleanup_old_jobs as cleanup_task
    task = cleanup_task.delay(days=days)
    logger.info("[cortex] cleanup enqueued — task_id=%s", task.id)
    return {"status": "queued", "task_id": task.id}


@router.get("/registry")
async def list_registry(_: User = Depends(_require_admin)):
    """List all keywords registered from user pipelines."""
    from app.cortex.registry import get_all_keywords
    keywords = await get_all_keywords()
    return {"count": len(keywords), "keywords": sorted(keywords)}


@router.get("/stats", response_model=CortexStatsResponse)
async def cortex_stats(current_user: User = Depends(get_current_user)):
    """Stats about the Cortex (total and active jobs)."""
    if CortexSessionLocal is None:
        return CortexStatsResponse(total_jobs=0, active_jobs=0)
    async with CortexSessionLocal() as db:
        stats = await cortex_svc.get_stats(db)
    return CortexStatsResponse(**stats)
