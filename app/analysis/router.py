import json
import uuid as uuid_lib
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import service as analysis_svc
from app.analysis import progress as prog
from app.analysis.schemas import AnalysisResponse
from app.auth.dependencies import get_current_user
from app.config import settings
from app.cv import service as cv_svc
from app.db.session import AsyncSessionLocal, get_db
from app.logger import get_logger
from app.pipeline.graph import pipeline
from app.storage import save_cv
from app.users.models import User

router = APIRouter(prefix="/analysis", tags=["Analysis"])
logger = get_logger(__name__)


async def _run_pipeline(
    analysis_id: UUID,
    pdf_path: str,
    cv_id: UUID,
    user_keywords: list[str],
    user_locations: list[str],
    contract_type: str,
    remote: bool,
    date_posted: str,
    experience_level: str,
):
    """Background task: invoke the shared pipeline and persist results."""
    initial_state = {
        "pdf_path": pdf_path,
        "cv_text": "",
        "cv_json": None,
        "user_keywords": user_keywords,
        "keywords": [],
        "user_locations": user_locations,
        "contract_type": contract_type,
        "remote": remote,
        "date_posted": date_posted,
        "experience_level": experience_level,
        "failed_keywords": [],
        "search_attempts": 0,
        "jobs": [],
        "filtered_jobs": [],
        "matches": [],
        "final_report": "",
        "messages": [],
    }

    logger.info("[analysis] Pipeline started — analysis_id=%s", analysis_id)
    aid = str(analysis_id)
    try:
        # stream_mode="updates" → each chunk is {node_name: partial_state_diff}
        # Accumulate diffs manually to reconstruct the final state
        accumulated: dict = dict(initial_state)
        async for chunk in pipeline.astream(initial_state, stream_mode="updates"):
            node_name = next(iter(chunk))
            prog.publish(aid, node_name)
            accumulated.update(chunk[node_name])
            logger.debug("[analysis] node=%s done", node_name)

        prog.publish_done(aid)
        result = accumulated

        async with AsyncSessionLocal() as db:

            await cv_svc.update_cv(db, cv_id, raw_text=result.get("cv_text", ""), data=result.get("cv_json"))
            await analysis_svc.update_analysis(
                db,
                analysis_id,
                status="completed",
                keywords=result.get("keywords", []),
                matches=result.get("matches", []),
                final_report=result.get("final_report", ""),
            )
        logger.info("[analysis] Pipeline completed — analysis_id=%s, matches=%d", analysis_id, len(result.get("matches", [])))
        prog.clear(aid)
    except Exception as exc:
        prog.publish_done(aid)
        logger.error("[analysis] Pipeline failed — analysis_id=%s | %s", analysis_id, exc, exc_info=True)
        async with AsyncSessionLocal() as db:
            await analysis_svc.update_analysis(db, analysis_id, status="failed", error=str(exc))


_VALID_CONTRACT_TYPES = {"cdi", "cdd", "stage", "alternance", "freelance", "temps_partiel", ""}
_VALID_DATE_POSTED = {"today", "3days", "week", "month", ""}
_VALID_EXPERIENCE = {"junior", "mid", "senior", ""}


@router.post("/upload", response_model=AnalysisResponse, status_code=202)
async def upload_cv(
    background_tasks: BackgroundTasks,
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
        "locations": user_locations,
        "contract_type": contract_type,
        "remote": remote,
        "date_posted": date_posted,
        "experience_level": experience_level,
    }

    logger.info(
        "[analysis] Upload received — file=%s, user=%s, keywords=%s, filters=%s",
        file.filename, current_user.id, user_keywords, search_filters,
    )

    # Pre-generate cv_id so the storage key embeds it
    cv_id = uuid_lib.uuid4()
    storage_key = await save_cv(content, str(current_user.id), str(cv_id), file.filename)

    cv = await cv_svc.create_cv(db, cv_id=cv_id, user_id=current_user.id, pdf_path=storage_key)
    analysis = await analysis_svc.create_analysis(db, user_id=current_user.id, cv_id=cv.id)
    await analysis_svc.update_analysis(db, analysis.id, status="processing", search_filters=search_filters)

    background_tasks.add_task(
        _run_pipeline,
        analysis.id, storage_key, cv.id,
        user_keywords, user_locations,
        contract_type, remote, date_posted, experience_level,
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
    """SSE endpoint — streams pipeline node progress in real time."""
    analysis = await analysis_svc.get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    aid = str(analysis_id)

    async def generate():
        # subscribe() replays history — works whether pipeline is running or already done
        async for event in prog.subscribe(aid):
            yield f"data: {json.dumps(event)}\n\n"
        # If no history (very old or already-cleared analysis), send done immediately
        if not prog.has_history(aid):
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
