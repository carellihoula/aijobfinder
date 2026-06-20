from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.cortex.ingestion import run_ingestion
from app.cortex.schemas import CortexStatsResponse, IngestionRequest, IngestionResponse
from app.cortex.seeds import SEED_KEYWORDS_BY_DOMAIN
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
    """Synchronous ingestion with custom keywords (admin only)."""
    result = await run_ingestion(body.keywords, body.locations)
    return IngestionResponse(status="done", **result)


@router.post("/ingest/full", response_model=IngestionResponse, status_code=202)
async def ingest_full(
    locations: list[str] | None = None,
    domain: str | None = None,
    _: User = Depends(_require_admin),
):
    """
    Enqueue a full Cortex ingestion via Celery (admin only).
    Covers all seed domains unless `domain` is specified.
    The same task runs automatically every night at 2am via Celery Beat.
    """
    from app.worker.tasks import full_ingestion
    task = full_ingestion.delay(locations=locations or None, domain=domain)
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


@router.get("/domains")
async def list_domains(current_user: User = Depends(get_current_user)):
    """List available seed domains and their keyword counts."""
    return {
        domain: len(keywords)
        for domain, keywords in SEED_KEYWORDS_BY_DOMAIN.items()
    }


@router.get("/stats", response_model=CortexStatsResponse)
async def cortex_stats(current_user: User = Depends(get_current_user)):
    """Stats about the Cortex (total and active jobs)."""
    if CortexSessionLocal is None:
        return CortexStatsResponse(total_jobs=0, active_jobs=0)
    async with CortexSessionLocal() as db:
        stats = await cortex_svc.get_stats(db)
    return CortexStatsResponse(**stats)
