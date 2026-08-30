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
from app.cover_letter.generator import (
    CoverLetterContent,
    generate_cover_letter,
    letter_body_text,
    letter_html,
    render_pdf,
)
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


class UpdateBodyRequest(BaseModel):
    text: str


class ExportBodyRequest(BaseModel):
    text: str


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


def _content_headers(content: CoverLetterContent, body_text: str) -> dict:
    company_slug = (content.recipient.company_name or "company").replace(" ", "_").lower()
    # base64-encode to avoid header encoding issues with French characters.
    content_b64 = base64.b64encode(json.dumps(content.model_dump()).encode()).decode()
    body_b64 = base64.b64encode(body_text.encode()).decode()
    return {
        "Content-Disposition": f'inline; filename="cover_letter_{company_slug}.pdf"',
        "X-Cover-Letter-Content": content_b64,
        "X-Cover-Letter-Body": body_b64,
        "Access-Control-Expose-Headers": "X-Cover-Letter-Content, X-Cover-Letter-Body",
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
    pdf_bytes = await render_pdf(content, body_text=stored.edited_body)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=_content_headers(content, stored.edited_body or letter_body_text(content)),
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
    pdf_bytes = await render_pdf(content)

    await cover_letter_svc.upsert_cover_letter(db, analysis_id, job_index, content.model_dump())

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=_content_headers(content, letter_body_text(content)),
    )


@router.patch(
    "/{analysis_id}/cover-letter/body",
    summary="Save a manual edit of the letter body (overrides the AI-generated text on download)",
)
async def update_cover_letter_body(
    analysis_id: UUID,
    job_index: int = Query(0, ge=0, description="Index of the job in the matches list"),
    body: UpdateBodyRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    updated = await cover_letter_svc.update_edited_body(db, analysis_id, job_index, body.text)
    if not updated:
        raise HTTPException(status_code=404, detail="No cover letter generated yet for this offer")
    return {"ok": True}


@router.get(
    "/{analysis_id}/cover-letter/body",
    summary="Fetch the stored letter as JSON (content + editable body) - no PDF rendering",
)
async def get_cover_letter_body(
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
    return {
        "content": stored.content,
        "body": stored.edited_body or letter_html(content),
    }


@router.get(
    "/{analysis_id}/cover-letters",
    summary="List every offer in this analysis that already has a generated cover letter",
)
async def list_cover_letters(
    analysis_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    matches: list[dict] = analysis.matches or []
    letters = await cover_letter_svc.list_cover_letters(db, analysis_id)

    items = []
    for letter in letters:
        if letter.job_index >= len(matches):
            continue
        match = matches[letter.job_index]
        job = match.get("job") or match
        items.append({
            "job_index": letter.job_index,
            "company": job.get("company", ""),
            "title": job.get("title", ""),
        })
    return items


@router.delete(
    "/{analysis_id}/cover-letter",
    summary="Delete a generated cover letter for this offer",
    status_code=204,
)
async def delete_cover_letter(
    analysis_id: UUID,
    job_index: int = Query(0, ge=0, description="Index of the job in the matches list"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    ok = await cover_letter_svc.delete_cover_letter(db, analysis_id, job_index)
    if not ok:
        raise HTTPException(status_code=404, detail="No cover letter found for this offer")


@router.post(
    "/{analysis_id}/cover-letter/generate",
    summary="Generate or refine the letter via AI - returns JSON (content + body), no PDF rendering",
)
async def generate_cover_letter_json(
    analysis_id: UUID,
    job_index: int = Query(0, ge=0, description="Index of the job in the matches list"),
    body: CoverLetterRequest = Body(default_factory=CoverLetterRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis, job, cv_data = await _get_analysis_job_cv(
        db, analysis_id, current_user.id, job_index
    )

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

    await cover_letter_svc.upsert_cover_letter(db, analysis_id, job_index, content.model_dump())

    return {
        "content": content.model_dump(),
        "body": letter_html(content),
    }


@router.post(
    "/{analysis_id}/cover-letter/export",
    summary="Save the current editor text and render it to PDF via WeasyPrint",
    response_class=StreamingResponse,
)
async def export_cover_letter_pdf(
    analysis_id: UUID,
    job_index: int = Query(0, ge=0, description="Index of the job in the matches list"),
    body: ExportBodyRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await get_analysis(db, analysis_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    updated = await cover_letter_svc.update_edited_body(db, analysis_id, job_index, body.text)
    if not updated:
        raise HTTPException(status_code=404, detail="No cover letter generated yet for this offer")

    content = CoverLetterContent(**updated.content)
    pdf_bytes = await render_pdf(content, body_text=body.text)
    company_slug = (content.recipient.company_name or "company").replace(" ", "_").lower()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cover_letter_{company_slug}.pdf"'},
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
