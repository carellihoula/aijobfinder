import base64
import io
import json
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.service import get_analysis
from app.auth.dependencies import get_current_user
from app.cover_letter import service as cover_letter_svc
from app.cover_letter.generator import CoverLetterContent, generate_cover_letter, render_pdf
from app.cv.service import get_cv
from app.db.session import get_db
from app.logger import get_logger
from app.storage import read_file
from app.users.models import User

logger = get_logger(__name__)

router = APIRouter(prefix="/analysis", tags=["Cover Letter"])


class CoverLetterRequest(BaseModel):
    suggestion: str = ""
    previous_content: dict | None = None


@router.get(
    "/{analysis_id}/cv",
    summary="Download the original CV PDF",
    response_class=StreamingResponse,
)
async def download_cv(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not analysis.cv_id:
        raise HTTPException(status_code=404, detail="No CV linked to this analysis")

    cv = await get_cv(db, analysis.cv_id)
    if not cv or not cv.pdf_path:
        raise HTTPException(status_code=404, detail="CV file not found")

    filename = f"cv_{(cv.data or {}).get('full_name', 'candidate').replace(' ', '_').lower()}.pdf"

    # Always stream through our server - S3 presigned redirects break fetch() in the
    # browser because S3 CORS must be configured per-origin, which fails in dev.
    try:
        pdf_bytes = await read_file(cv.pdf_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="CV file no longer available on storage")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=300",
        },
    )


def _content_headers(content: CoverLetterContent) -> dict:
    company_slug = (content.recipient.company_name or "company").replace(" ", "_").lower()
    # base64-encode to avoid header encoding issues with French characters.
    content_b64 = base64.b64encode(json.dumps(content.model_dump()).encode()).decode()
    return {
        "Content-Disposition": f'inline; filename="cover_letter_{company_slug}.pdf"',
        "X-Cover-Letter-Content": content_b64,
        "Access-Control-Expose-Headers": "X-Cover-Letter-Content",
    }


@router.get(
    "/{analysis_id}/cover-letter",
    summary="Fetch a previously generated cover letter without regenerating it",
    response_class=StreamingResponse,
)
async def get_cover_letter(
    analysis_id: UUID,
    job_index: int = Query(0, ge=0, description="Index of the job in the matches list"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    stored = await cover_letter_svc.get_cover_letter(db, analysis_id, job_index)
    if not stored:
        raise HTTPException(status_code=404, detail="No cover letter generated yet for this offer")

    content = CoverLetterContent(**stored.content)
    pdf_bytes = render_pdf(content)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=_content_headers(content),
    )


@router.post(
    "/{analysis_id}/cover-letter",
    summary="Generate or refine a PDF cover letter for a matched job",
    response_class=StreamingResponse,
)
async def create_cover_letter(
    analysis_id: UUID,
    job_index: int = Query(0, ge=0, description="Index of the job in the matches list"),
    body: CoverLetterRequest = Body(default_factory=CoverLetterRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis, job, cv_data = await _get_analysis_job_cv(
        db, analysis_id, current_user.id, job_index
    )

    # Fall back to the DB-persisted content for refinement continuity when the
    # frontend doesn't have it locally (new device, cleared cache, ...).
    previous_content = body.previous_content
    if previous_content is None:
        stored = await cover_letter_svc.get_cover_letter(db, analysis_id, job_index)
        if stored:
            previous_content = stored.content

    gender = (current_user.preferences or {}).get("gender", "") if current_user.preferences else ""
    content: CoverLetterContent = await generate_cover_letter(
        cv_data, job,
        suggestion=body.suggestion,
        previous_content=previous_content,
        gender=gender,
    )
    pdf_bytes = render_pdf(content)

    await cover_letter_svc.upsert_cover_letter(db, analysis_id, job_index, content.model_dump())

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=_content_headers(content),
    )


@router.post(
    "/{analysis_id}/apply",
    summary="Apply to a job - returns CV + cover letter as separate documents",
)
async def apply_to_job(
    analysis_id: UUID,
    job_index: int = Query(0, ge=0, description="Index of the job in the matches list (0 = best match)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Prepares the application documents for a matched job.
    Returns metadata with the URLs to download each document separately:
      - GET /analysis/{id}/cv              → original CV PDF
      - POST /analysis/{id}/cover-letter   → generated cover letter PDF
    The user downloads both and applies directly on the company website.
    """
    analysis, job, cv_data = await _get_analysis_job_cv(
        db, analysis_id, current_user.id, job_index
    )

    cv = await get_cv(db, analysis.cv_id) if analysis.cv_id else None
    has_cv_file = bool(cv and cv.pdf_path)

    gender = (current_user.preferences or {}).get("gender", "") if current_user.preferences else ""
    content: CoverLetterContent = await generate_cover_letter(cv_data, job, gender=gender)

    logger.info(
        "[apply] user=%s analysis=%s job_index=%d job=%r tone=%s",
        current_user.id, analysis_id, job_index, job.get("title"), content.tone,
    )

    return {
        "job": {
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "url": job.get("url"),
        },
        "cover_letter": {
            "subject": content.subject,
            "tone": content.tone,
            "highlighted_skills": content.highlighted_skills,
            "key_selling_point": content.key_selling_point,
            "paragraphs": [
                {"purpose": p.purpose, "text": p.text}
                for p in content.paragraphs
            ],
        },
        "documents": {
            "cv": {
                "available": has_cv_file,
                "download_url": f"/analysis/{analysis_id}/cv" if has_cv_file else None,
            },
            "cover_letter": {
                "available": True,
                "download_url": f"/analysis/{analysis_id}/cover-letter?job_index={job_index}",
            },
        },
    }


# ── Shared helper ──────────────────────────────────────────────────────────────

async def _get_analysis_job_cv(
    db: AsyncSession,
    analysis_id: UUID,
    user_id: UUID,
    job_index: int,
) -> tuple:
    analysis = await get_analysis(db, analysis_id, user_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Analysis is not completed yet (status: {analysis.status})",
        )

    matches: list[dict] = analysis.matches or []
    if not matches:
        raise HTTPException(status_code=400, detail="This analysis has no job matches")
    if job_index >= len(matches):
        raise HTTPException(
            status_code=400,
            detail=f"job_index {job_index} is out of range (0–{len(matches) - 1})",
        )

    match = matches[job_index]
    job = match.get("job") or match

    cv_data: dict = {}
    if analysis.cv_id:
        cv = await get_cv(db, analysis.cv_id)
        if cv and cv.data:
            cv_data = cv.data

    return analysis, job, cv_data
