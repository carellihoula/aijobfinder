from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)


# ── Structured JSON schema ────────────────────────────────────────────────────

class _Sender(BaseModel):
    full_name: str = Field(description="Candidate's full name")
    email: str = Field(description="Candidate's email address")
    phone: str = Field(description="Candidate's phone number")
    location: str = Field(description="Candidate's city / location")


class _Recipient(BaseModel):
    company_name: str = Field(description="Name of the company being applied to")
    contact: str = Field(
        description="Contact designation, e.g. 'Le/La Responsable des Ressources Humaines'"
    )
    job_title: str = Field(description="Exact title of the position being applied for")


class _Paragraph(BaseModel):
    purpose: Literal["hook", "experience", "skills", "cultural_fit", "call_to_action"] = Field(
        description="Semantic role of this paragraph in the letter"
    )
    text: str = Field(description="Paragraph text: 4–5 sentences, 80–110 words. Dense, specific, no filler. Every sentence must add concrete value.")


class CoverLetterContent(BaseModel):
    """
    Complete, self-contained cover letter data.
    Produced by the LLM — PDF backends only consume this object.
    """
    # ── Header ────────────────────────────────────────────────────────────────
    sender: _Sender
    recipient: _Recipient
    city_date: str = Field(
        description="Formatted date string, e.g. 'Paris, 15 juin 2026'"
    )

    # ── Letter structure ──────────────────────────────────────────────────────
    subject: str = Field(
        description="Object line, e.g. 'Candidature au poste de Développeur Backend chez Acme'"
    )
    salutation: str = Field(
        default="Madame, Monsieur,",
        description="Opening salutation"
    )
    paragraphs: list[_Paragraph] = Field(
        description="3 to 5 body paragraphs as needed: hook → experience → skills (optional) → cultural_fit (optional) → call_to_action. Each paragraph: 4–5 sentences, 80–110 words, concrete and specific."
    )
    closing: str = Field(
        description="Single closing sentence before sign-off"
    )
    sign_off: str = Field(
        default="Cordialement,",
        description="Sign-off formula"
    )

    # ── Enrichment metadata ───────────────────────────────────────────────────
    highlighted_skills: list[str] = Field(
        description="Top 3–5 skills emphasized in the letter"
    )
    tone: Literal["formal", "dynamic", "creative"] = Field(
        description="Overall tone adapted to the company and role"
    )
    key_selling_point: str = Field(
        description="One sentence: the strongest reason why this candidate fits this role"
    )


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert career coach and professional writer specializing in French cover letters.

Given a candidate profile and a job offer, generate a complete, personalized cover letter \
as a structured JSON object.

Rules:
- ALL text fields (subject, paragraphs, closing, city_date, etc.) must be written in French
- Tone must be adapted: formal for traditional sectors (finance, legal, healthcare), \
dynamic for tech/startups, creative for design/media
- Write as many paragraphs as needed (3 to 5) to make the letter compelling and complete:
  • hook          — genuine motivation for THIS company and THIS role specifically, not generic
  • experience    — most relevant past experience with concrete achievements and measurable results
  • skills        — (optional) 3–4 specific technical or soft skills matching the job, with examples
  • cultural_fit  — (optional) alignment with company values, mission or culture if clearly known
  • call_to_action — strong closing: reinforce fit, request interview, show availability
- Each paragraph: 4–5 sentences, 80–110 words. Be specific, avoid clichés, no filler.
- closing: 1 short impactful sentence (e.g. "Je serais ravi(e) de vous présenter ma candidature lors d'un entretien.")
- city_date format: "Ville, J mois YYYY" (e.g. "Paris, 15 juin 2026")
- If candidate location has multiple parts, use the first city only
- Extract sender info from the candidate profile (use empty string if missing)
- highlighted_skills: pick the 3–5 skills most relevant to THIS specific job
- key_selling_point: one punchy sentence that captures the candidate's unique value for this role
"""


async def generate_cover_letter(cv: dict, job: dict) -> CoverLetterContent:
    """
    Agent: takes raw CV dict + job dict, returns a fully structured CoverLetterContent.
    The output JSON is self-contained — PDF backends only need this object.
    """
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.4,
        api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(CoverLetterContent)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=(
            f"## Candidate profile\n{_format_cv(cv)}\n\n"
            f"## Job offer\n{_format_job(job)}"
        )),
    ]

    content: CoverLetterContent = await llm.ainvoke(messages)

    logger.info(
        "[cover_letter_agent] done — tone=%s paragraphs=%d skills=%s",
        content.tone,
        len(content.paragraphs),
        content.highlighted_skills,
    )
    return content


def render_pdf(content: CoverLetterContent) -> bytes:
    """Dispatch to the configured PDF backend."""
    backend = settings.COVER_LETTER_BACKEND.lower()

    if backend == "weasyprint":
        from app.cover_letter.backends.weasyprint_backend import render
    else:
        from app.cover_letter.backends.reportlab_backend import render

    return render(content)


# ── Input formatters (for the LLM prompt only) ────────────────────────────────

def _format_cv(cv: dict) -> str:
    lines = [
        f"Name: {cv.get('full_name', '')}",
        f"Email: {cv.get('email', '')}",
        f"Phone: {cv.get('phone', '')}",
        f"Location: {cv.get('location', '')}",
        f"Level: {cv.get('level', 'unknown')} | Experience: {cv.get('experience_years', 0)} years",
    ]
    if cv.get("roles"):
        lines.append(f"Target roles: {', '.join(cv['roles'])}")
    if cv.get("skills"):
        lines.append(f"Skills: {', '.join(cv['skills'][:20])}")
    if cv.get("summary"):
        lines.append(f"Summary: {cv['summary'][:300]}")
    if cv.get("experiences"):
        lines.append("Experience:")
        for exp in cv["experiences"][:4]:
            lines.append(
                f"  • {exp.get('title', '')} @ {exp.get('company', '')} "
                f"({exp.get('start_date', '')}–{exp.get('end_date', 'present')})"
            )
            if exp.get("description"):
                lines.append(f"    {exp['description'][:200]}")
    if cv.get("education"):
        lines.append("Education:")
        for edu in cv["education"][:2]:
            lines.append(f"  • {edu.get('degree', '')} — {edu.get('school', '')}")
    return "\n".join(lines)


def _format_job(job: dict) -> str:
    lines = [
        f"Title: {job.get('title', 'N/A')}",
        f"Company: {job.get('company', 'N/A')}",
        f"Location: {job.get('location', 'N/A')}",
    ]
    if job.get("desc"):
        lines.append(f"Description:\n{job['desc'][:600]}")
    return "\n".join(lines)