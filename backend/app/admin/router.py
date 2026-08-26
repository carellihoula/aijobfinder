from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import service as analysis_svc
from app.auth.dependencies import get_admin_user
from app.cv import service as cv_svc
from app.db.session import get_db
from app.logger import get_logger
from app.users import service as users_svc
from app.users.models import User

router = APIRouter(prefix="/admin", tags=["Admin"])
logger = get_logger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserSummary(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    is_admin: bool

    model_config = {"from_attributes": True}


class AnalysisSummary(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    keywords: list[str] | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class TaskResult(BaseModel):
    task_id: str
    status: str
    detail: str


class IngestRequest(BaseModel):
    locations: list[str] | None = None


class CleanupRequest(BaseModel):
    days: int = 30


# ── User management ───────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserSummary])
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users."""
    return await users_svc.get_all_users(db)


@router.patch("/users/{user_id}/promote", response_model=UserSummary)
async def promote_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Grant admin rights to a user."""
    user = await users_svc.set_admin_status(db, user_id, is_admin=True)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info("[admin] %s promoted by %s", user.email, admin.email)
    return user


@router.patch("/users/{user_id}/demote", response_model=UserSummary)
async def demote_user(
    user_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke admin rights from a user."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin rights")
    user = await users_svc.set_admin_status(db, user_id, is_admin=False)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info("[admin] %s demoted by %s", user.email, admin.email)
    return user


# ── Analysis management ───────────────────────────────────────────────────────

@router.get("/analyses", response_model=list[AnalysisSummary])
async def list_analyses(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all analyses across all users."""
    return await analysis_svc.get_all_analyses(db)


@router.post("/analyses/{analysis_id}/rerun", response_model=TaskResult)
async def rerun_analysis(
    analysis_id: UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-trigger the full LangGraph pipeline for any analysis.
    The analysis status is reset to 'pending' before dispatching.
    Useful to fix a failed analysis or refresh one manually.
    """
    from app.worker.tasks import run_pipeline

    analysis = await analysis_svc.get_analysis_by_id(db, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not analysis.cv_id:
        raise HTTPException(status_code=400, detail="This analysis has no linked CV")

    cv = await cv_svc.get_cv(db, analysis.cv_id)
    if not cv or not cv.pdf_path:
        raise HTTPException(status_code=400, detail="CV file not found — cannot re-run pipeline")

    filters = analysis.search_filters or {}

    # Reset status so SSE polling picks it up
    await analysis_svc.update_analysis(db, analysis_id, status="pending", error=None)

    task = run_pipeline.delay(
        analysis_id=str(analysis_id),
        pdf_path=cv.pdf_path,
        cv_id=str(cv.id),
        user_keywords=filters.get("user_keywords", []),
        user_locations=filters.get("locations", []),
        contract_type=filters.get("contract_type", ""),
        remote=filters.get("remote", False),
        date_posted=filters.get("date_posted", ""),
        experience_level=filters.get("experience_level", ""),
    )

    logger.info(
        "[admin] rerun triggered — analysis=%s cv=%s by admin=%s task=%s",
        analysis_id, cv.id, admin.email, task.id,
    )
    return TaskResult(
        task_id=task.id,
        status="queued",
        detail=f"Pipeline re-queued for analysis {analysis_id}",
    )


# ── Cortex / cron controls ────────────────────────────────────────────────────

@router.post("/cortex/ingest", response_model=TaskResult)
async def trigger_ingestion(
    body: IngestRequest = IngestRequest(),
    admin: User = Depends(get_admin_user),
):
    """
    Manually trigger full Cortex ingestion without waiting for the nightly cron.
    Optionally filter to specific locations.
    """
    from app.worker.tasks import full_ingestion

    task = full_ingestion.delay(locations=body.locations or None)
    logger.info("[admin] full_ingestion triggered by %s — task=%s", admin.email, task.id)
    return TaskResult(
        task_id=task.id,
        status="queued",
        detail="Full ingestion queued — check Flower for progress",
    )


@router.post("/cortex/refresh", response_model=TaskResult)
async def trigger_refresh(
    admin: User = Depends(get_admin_user),
):
    """
    Manually trigger per-user analysis refresh (re-match against current Cortex).
    Normally runs nightly at 3h, after ingestion.
    """
    from app.worker.tasks import refresh_user_analyses

    task = refresh_user_analyses.delay()
    logger.info("[admin] refresh_user_analyses triggered by %s — task=%s", admin.email, task.id)
    return TaskResult(
        task_id=task.id,
        status="queued",
        detail="User analyses refresh queued",
    )


@router.post("/cortex/cleanup", response_model=TaskResult)
async def trigger_cleanup(
    body: CleanupRequest = CleanupRequest(),
    admin: User = Depends(get_admin_user),
):
    """
    Manually trigger Cortex cleanup — deactivate jobs not seen in the last N days.
    Default: 30 days.
    """
    from app.worker.tasks import cleanup_old_jobs

    task = cleanup_old_jobs.delay(days=body.days)
    logger.info("[admin] cleanup triggered by %s — days=%d task=%s", admin.email, body.days, task.id)
    return TaskResult(
        task_id=task.id,
        status="queued",
        detail=f"Cleanup queued — jobs older than {body.days} days will be deactivated",
    )
