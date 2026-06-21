import json
import uuid as uuid_lib
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import progress as prog
from app.analysis import service as analysis_svc
from app.analysis.schemas import AnalysisResponse
from app.auth.dependencies import get_current_user
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

    user_keywords = [kw.strip() for kw in keywords.split(",") if kw.strip()][:10]
    user_locations = [loc.strip() for loc in locations.split(",") if loc.strip()][:5]

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

    cv       = await cv_svc.create_cv(db, cv_id=cv_id, user_id=current_user.id, pdf_path=storage_key)
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
