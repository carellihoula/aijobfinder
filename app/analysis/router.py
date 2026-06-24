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

_PIPELINE_COOLDOWN = 86_400  # 24 h in seconds


# ─── Upload — profile init (one-time) ────────────────────────────────────────

@router.post("/upload", status_code=202)
async def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF CV to initialise the user's profile.
    Runs only pdf_parser + cv_structurer — no job search.
    Progress is published on the cv_id key (SSE: GET /analysis/init-stream/{cv_id}).
    """
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit")

    # Dedup: same PDF already extracted → return existing cv_id, skip re-extraction
    pdf_hash = hashlib.sha256(content).hexdigest()
    existing_cv = await cv_svc.get_cv_by_hash(db, current_user.id, pdf_hash)
    if existing_cv and existing_cv.data:
        logger.info("[upload] Same CV hash — returning existing cv_id=%s", existing_cv.id)
        return {"cv_id": str(existing_cv.id), "status": "ready"}

    cv_id       = uuid_lib.uuid4()
    storage_key = await save_cv(content, str(current_user.id), str(cv_id), file.filename)
    await cv_svc.create_cv(db, cv_id=cv_id, user_id=current_user.id, pdf_path=storage_key, pdf_hash=pdf_hash)

    from app.worker.tasks import init_profile
    init_profile.delay(cv_id=str(cv_id), user_id=str(current_user.id), pdf_path=storage_key)

    logger.info("[upload] cv_id=%s user=%s — init_profile enqueued", cv_id, current_user.id)
    return {"cv_id": str(cv_id), "status": "processing"}


# ─── Init stream (SSE for profile extraction progress) ────────────────────────

@router.get("/init-stream/{cv_id}")
async def init_stream(
    cv_id: str,
    current_user: User = Depends(get_current_user),
):
    """SSE — streams pdf_parser + cv_structurer progress to the browser."""
    async def generate():
        async for event in prog.subscribe(cv_id):
            yield f"data: {json.dumps(event)}\n\n"
        if not await prog.has_history(cv_id):
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ─── Launch search — uses profile data (on-demand) ────────────────────────────

@router.post("/search", response_model=AnalysisResponse, status_code=202)
async def launch_search(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Launch a job-search run using the user's profile (cv.data + user.preferences).
    No PDF required. Rate-limited to once per 24 h.
    Progress available via SSE: GET /analysis/{id}/stream.
    """
    cv = await cv_svc.get_latest_cv_for_user(db, current_user.id)
    if not cv or not cv.data:
        raise HTTPException(
            status_code=400,
            detail="No profile found. Upload your CV first to initialise your profile.",
        )

    # Rate limit: one search per 24 h
    latest = await analysis_svc.get_latest_analysis_for_user(db, current_user.id)
    if latest:
        if latest.status == "processing":
            raise HTTPException(
                status_code=409,
                detail="A search is already running. Wait for it to complete.",
            )
        if latest.status == "completed":
            created = latest.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - created).total_seconds()
            if age < _PIPELINE_COOLDOWN:
                wait_h = round((_PIPELINE_COOLDOWN - age) / 3600, 1)
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit: next search available in {wait_h}h. "
                           "Your results are refreshed automatically every night.",
                )

    analysis = await analysis_svc.create_analysis(db, user_id=current_user.id, cv_id=cv.id)
    await analysis_svc.update_analysis(db, analysis.id, status="processing")

    from app.worker.tasks import run_search
    run_search.delay(
        analysis_id=str(analysis.id),
        cv_id=str(cv.id),
        user_id=str(current_user.id),
    )

    logger.info("[search] analysis_id=%s user=%s — run_search enqueued", analysis.id, current_user.id)
    await db.refresh(analysis)
    return analysis


# ─── Read endpoints ───────────────────────────────────────────────────────────

@router.get("/latest", response_model=AnalysisResponse)
async def get_latest_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    analysis = await analysis_svc.get_latest_analysis_for_user(db, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found")
    return analysis


@router.get("/cv-data")
async def get_cv_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cv = await cv_svc.get_latest_cv_for_user(db, current_user.id)
    if not cv or not cv.data:
        raise HTTPException(status_code=404, detail="No CV data found")
    return cv.data


@router.patch("/cv-data")
async def update_cv_data(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cv = await cv_svc.get_latest_cv_for_user(db, current_user.id)
    if not cv:
        raise HTTPException(status_code=404, detail="No CV found")
    merged = {**(cv.data or {}), **payload}
    await cv_svc.update_cv(db, cv.id, data=merged)
    return merged


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
    """SSE — streams search pipeline node progress to the browser."""
    analysis = await analysis_svc.get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    aid = str(analysis_id)

    async def generate():
        async for event in prog.subscribe(aid):
            yield f"data: {json.dumps(event)}\n\n"
        if not await prog.has_history(aid):
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ─── Admin endpoints ──────────────────────────────────────────────────────────

class AdminForceRequest(BaseModel):
    user_id: UUID


@router.post("/admin/force", response_model=AnalysisResponse, status_code=202)
async def admin_force_search(
    body: AdminForceRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin only — force a fresh search for any user using their current profile.
    Bypasses rate limit and cooldown.
    """
    cv = await cv_svc.get_latest_cv_for_user(db, body.user_id)
    if not cv or not cv.data:
        raise HTTPException(status_code=404, detail="No profile found for this user.")

    analysis = await analysis_svc.create_analysis(db, user_id=body.user_id, cv_id=cv.id)
    await analysis_svc.update_analysis(db, analysis.id, status="processing")

    from app.worker.tasks import run_search
    run_search.delay(
        analysis_id=str(analysis.id),
        cv_id=str(cv.id),
        user_id=str(body.user_id),
    )

    logger.info(
        "[admin] Search forced for user=%s analysis=%s by admin=%s",
        body.user_id, analysis.id, admin.id,
    )
    await db.refresh(analysis)
    return analysis
