import hashlib
import json
import uuid as uuid_lib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import progress as prog
from app.analysis import service as analysis_svc
from app.analysis.schemas import AnalysisResponse
from app.auth.dependencies import get_admin_user, get_current_user
from app.config import settings
from app.cv import service as cv_svc
from app.db.session import get_db
from app.logger import get_logger
from app.storage import save_cv
from app.users.models import User

router = APIRouter(prefix="/analysis", tags=["Analysis"])
logger = get_logger(__name__)

_VALID_CONTRACT_TYPES = {"cdi", "cdd", "stage", "alternance", "freelance", "temps_partiel", ""}
_VALID_DATE_POSTED    = {"today", "3days", "week", "month", ""}
_VALID_EXPERIENCE     = {"junior", "mid", "senior", ""}


@router.post("/upload", response_model=AnalysisResponse, status_code=202)
async def upload_cv(
    file: UploadFile = File(...),
    keywords: str = Form(default=""),
    locations: str = Form(default=""),
    contract_type: str = Form(default=""),
    remote: bool = Form(default=False),
    date_posted: str = Form(default=""),
    experience_level: str = Form(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit")

    if contract_type not in _VALID_CONTRACT_TYPES:
        raise HTTPException(status_code=422, detail=f"contract_type must be one of: {', '.join(_VALID_CONTRACT_TYPES - {''})}")
    if date_posted not in _VALID_DATE_POSTED:
        raise HTTPException(status_code=422, detail=f"date_posted must be one of: {', '.join(_VALID_DATE_POSTED - {''})}")
    if experience_level not in _VALID_EXPERIENCE:
        raise HTTPException(status_code=422, detail=f"experience_level must be one of: {', '.join(_VALID_EXPERIENCE - {''})}")

    user_keywords  = [kw.strip()  for kw  in keywords.split(",")  if kw.strip()][:10]
    user_locations = [loc.strip() for loc in locations.split(",") if loc.strip()][:5]

    # C — Dedup: same CV already analysed → always return cache.
    # New Cortex jobs may be irrelevant to this profile; the nightly
    # refresh_user_analyses does the proper hash comparison and updates
    # the cache only when relevant jobs actually changed.
    pdf_hash = hashlib.sha256(content).hexdigest()
    existing_cv = await cv_svc.get_cv_by_hash(db, current_user.id, pdf_hash)
    if existing_cv:
        existing_analysis = await analysis_svc.get_latest_completed_analysis_for_cv(db, existing_cv.id)
        if existing_analysis:
            logger.info("[analysis] Same CV — returning cached analysis %s", existing_analysis.id)
            return existing_analysis

    # Rate limit — 3 cases:
    #   1. No previous analysis → first profile config → always allowed
    #   2. Previous analysis processing → pipeline already running → 409
    #   3. Previous analysis completed < 24h ago → 429 with time remaining
    #   4. Previous analysis failed → allow retry (bad UX to block on errors)
    _PIPELINE_COOLDOWN = 86_400  # 24 hours in seconds
    latest = await analysis_svc.get_latest_analysis_for_user(db, current_user.id)
    if latest:
        if latest.status == "processing":
            raise HTTPException(
                status_code=409,
                detail="An analysis is already running. Wait for it to complete before launching a new one.",
            )
        if latest.status == "completed":
            created = latest.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
            if age_seconds < _PIPELINE_COOLDOWN:
                wait_hours = round((_PIPELINE_COOLDOWN - age_seconds) / 3600, 1)
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit: your next analysis will be available in {wait_hours}h. "
                           "Your results are refreshed automatically every night.",
                )

    search_filters = {
        "locations":        user_locations,
        "contract_type":    contract_type,
        "remote":           remote,
        "date_posted":      date_posted,
        "experience_level": experience_level,
    }

    logger.info(
        "[analysis] Upload received — file=%s, user=%s, keywords=%s, filters=%s",
        file.filename, current_user.id, user_keywords, search_filters,
    )

    cv_id       = uuid_lib.uuid4()
    storage_key = await save_cv(content, str(current_user.id), str(cv_id), file.filename)

    cv       = await cv_svc.create_cv(db, cv_id=cv_id, user_id=current_user.id, pdf_path=storage_key, pdf_hash=pdf_hash)
    analysis = await analysis_svc.create_analysis(db, user_id=current_user.id, cv_id=cv.id)
    await analysis_svc.update_analysis(db, analysis.id, status="processing", search_filters=search_filters)

    # Enqueue the pipeline in Celery — runs in a separate worker process
    from app.worker.tasks import run_pipeline
    run_pipeline.delay(
        analysis_id=str(analysis.id),
        pdf_path=storage_key,
        cv_id=str(cv.id),
        user_keywords=user_keywords,
        user_locations=user_locations,
        contract_type=contract_type,
        remote=remote,
        date_posted=date_posted,
        experience_level=experience_level,
    )

    await db.refresh(analysis)
    return analysis


@router.get("/latest", response_model=AnalysisResponse)
async def get_latest_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent analysis for the current user."""
    analysis = await analysis_svc.get_latest_analysis_for_user(db, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found")
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await analysis_svc.get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/{analysis_id}/stream")
async def stream_analysis(
    analysis_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint — streams pipeline node progress to the browser in real time."""
    analysis = await analysis_svc.get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    aid = str(analysis_id)

    async def generate():
        async for event in prog.subscribe(aid):
            yield f"data: {json.dumps(event)}\n\n"
        # If pipeline was already cleared (very old analysis), send done immediately
        if not await prog.has_history(aid):
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )


# ── Admin endpoints ────────────────────────────────────────────────────────────

class AdminForceRequest(BaseModel):
    user_id: UUID
    keywords: list[str] = []
    locations: list[str] = []
    contract_type: str = ""
    remote: bool = False
    date_posted: str = ""
    experience_level: str = ""


@router.post("/admin/force", response_model=AnalysisResponse, status_code=202)
async def admin_force_pipeline(
    body: AdminForceRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin only — force a fresh pipeline for any user.
    Bypasses rate limit, dedup, and the 24h cooldown.
    Uses the user's latest CV already stored in the system.
    """
    cv = await cv_svc.get_latest_cv_for_user(db, body.user_id)
    if not cv or not cv.pdf_path:
        raise HTTPException(status_code=404, detail="No CV found for this user. They must upload one first.")

    user_keywords  = body.keywords[:10]
    user_locations = body.locations[:5]

    search_filters = {
        "locations":        user_locations,
        "contract_type":    body.contract_type,
        "remote":           body.remote,
        "date_posted":      body.date_posted,
        "experience_level": body.experience_level,
    }

    analysis = await analysis_svc.create_analysis(db, user_id=body.user_id, cv_id=cv.id)
    await analysis_svc.update_analysis(db, analysis.id, status="processing", search_filters=search_filters)

    from app.worker.tasks import run_pipeline
    run_pipeline.delay(
        analysis_id=str(analysis.id),
        pdf_path=cv.pdf_path,
        cv_id=str(cv.id),
        user_keywords=user_keywords,
        user_locations=user_locations,
        contract_type=body.contract_type,
        remote=body.remote,
        date_posted=body.date_posted,
        experience_level=body.experience_level,
    )

    logger.info(
        "[admin] Pipeline forced for user=%s analysis=%s by admin=%s",
        body.user_id, analysis.id, admin.id,
    )
    await db.refresh(analysis)
    return analysis
