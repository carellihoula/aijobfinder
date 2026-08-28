import base64
import io
import json
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.applications import service as applications_svc
from app.applications.models import Application
from app.applications.scraper import JobOfferNotFound, clean_pasted_text, extract_job, fetch_job_text
from app.applications.schemas import (
    ApplicationResponse,
    CreateApplicationRequest,
    PreviewRequest,
    PreviewResponse,
    RefineCoverLetterRequest,
    UpdateApplicationRequest,
)
from app.auth.dependencies import get_current_user
from app.cover_letter.generator import CoverLetterContent, letter_html, render_pdf
from app.db.session import get_db
from app.logger import get_logger
from app.users.models import User
from app.worker.tasks import generate_application_cover_letter


class ExportBodyRequest(BaseModel):
    text: str


class UpdateBodyRequest(BaseModel):
    text: str

logger = get_logger(__name__)

router = APIRouter(prefix="/applications", tags=["Applications"])


def _job_dict(application: Application) -> dict:
    return {"title": application.title, "company": application.company, "desc": application.description, "url": application.url}


@router.post("/preview", response_model=PreviewResponse, summary="Scrape or parse a job posting without persisting anything")
async def preview_job(payload: PreviewRequest):
    if not payload.url and not payload.text:
        raise HTTPException(status_code=422, detail="Provide either 'url' or 'text'")

    if payload.url:
        try:
            text = await fetch_job_text(payload.url)
        except JobOfferNotFound as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    else:
        text = clean_pasted_text(payload.text)
        if len(text) < 50:
            raise HTTPException(status_code=422, detail="Pasted text is too short to be a job posting")

    extracted = await extract_job(text)
    return PreviewResponse(
        title=extracted.title, company=extracted.company, location=extracted.location,
        description=text, url=payload.url,
    )


@router.post("", response_model=ApplicationResponse, status_code=202, summary="Save a job and enqueue cover letter generation")
async def create_application(
    payload: CreateApplicationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.create_application(
        db, current_user.id,
        title=payload.title, company=payload.company, description=payload.description,
        url=payload.url, summary=payload.description[:280],
    )
    logger.info("[applications] Created - id=%s title=%r company=%r", application.id, payload.title, payload.company)

    generate_application_cover_letter.delay(
        str(application.id), _job_dict(application), str(current_user.id), payload.suggestion,
    )
    return application


@router.post("/{application_id}/cover-letter/refine", response_model=ApplicationResponse, status_code=202)
async def refine_cover_letter(
    application_id: UUID,
    payload: RefineCoverLetterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.get_application(db, application_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    previous_content = application.cover_letter_content
    await applications_svc.set_cover_letter_result(db, application_id, status="processing", content=previous_content)

    generate_application_cover_letter.delay(
        str(application.id), _job_dict(application), str(current_user.id), payload.suggestion, previous_content,
    )
    return await applications_svc.get_application(db, application_id, current_user.id)


@router.get("/{application_id}/cover-letter", summary="Download the generated cover letter PDF")
async def download_cover_letter(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.get_application(db, application_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.cover_letter_status != "completed" or not application.cover_letter_content:
        raise HTTPException(status_code=409, detail=f"Cover letter not ready (status: {application.cover_letter_status})")

    content = CoverLetterContent(**application.cover_letter_content)
    pdf_bytes = render_pdf(content)
    content_b64 = base64.b64encode(json.dumps(application.cover_letter_content).encode()).decode()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="cover_letter.pdf"',
            "X-Cover-Letter-Content": content_b64,
            "Access-Control-Expose-Headers": "X-Cover-Letter-Content",
        },
    )


@router.get(
    "/{application_id}/cover-letter/body",
    summary="Fetch the stored letter as JSON (content + editable body) - no PDF rendering",
)
async def get_cover_letter_body(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.get_application(db, application_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if not application.cover_letter_content:
        raise HTTPException(status_code=404, detail="No cover letter generated yet for this application")

    content = CoverLetterContent(**application.cover_letter_content)
    return {
        "content": application.cover_letter_content,
        "body": application.edited_body or letter_html(content),
    }


@router.patch(
    "/{application_id}/cover-letter/body",
    summary="Save a manual edit of the letter body (overrides the AI-generated text on export)",
)
async def update_cover_letter_body(
    application_id: UUID,
    body: UpdateBodyRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.get_application(db, application_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    updated = await applications_svc.update_edited_body(db, application_id, body.text)
    if not updated:
        raise HTTPException(status_code=404, detail="No cover letter generated yet for this application")
    return {"ok": True}


@router.post(
    "/{application_id}/cover-letter/export",
    summary="Save the current editor text and render it to PDF via reportlab",
    response_class=StreamingResponse,
)
async def export_cover_letter_pdf(
    application_id: UUID,
    body: ExportBodyRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.get_application(db, application_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    updated = await applications_svc.update_edited_body(db, application_id, body.text)
    if not updated or not updated.cover_letter_content:
        raise HTTPException(status_code=404, detail="No cover letter generated yet for this application")

    content = CoverLetterContent(**updated.cover_letter_content)
    pdf_bytes = render_pdf(content, body_text=body.text)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="cover_letter.pdf"'},
    )


@router.get("", response_model=list[ApplicationResponse], summary="List my applications")
async def list_applications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await applications_svc.list_applications_for_user(db, current_user.id)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.get_application(db, application_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: UUID,
    payload: UpdateApplicationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    application = await applications_svc.update_application(
        db, application_id, current_user.id, title=payload.title, company=payload.company, status=payload.status,
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.delete("/{application_id}", status_code=204)
async def delete_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await applications_svc.delete_application(db, application_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found")
