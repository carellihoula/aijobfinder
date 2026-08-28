from datetime import datetime
from html import escape
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.logger import get_logger

_FRENCH_MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _today_fr() -> str:
    now = datetime.now()
    return f"{now.day} {_FRENCH_MONTHS[now.month - 1]} {now.year}"

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
    Produced by the LLM - PDF backends only consume this object.
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


# ── System prompts ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert career coach and professional writer specializing in French cover letters.

Given a candidate profile and a job offer, generate a complete, personalized cover letter \
as a structured JSON object.

Rules:
- ALL text fields (subject, paragraphs, closing, city_date, etc.) must be written in French
- Tone must be adapted: formal for traditional sectors (finance, legal, healthcare), \
dynamic for tech/startups, creative for design/media
- Write as many paragraphs as needed (3 to 5) to make the letter compelling and complete:
  • hook          - genuine motivation for THIS company and THIS role specifically, not generic
  • experience    - most relevant past experience with concrete achievements and measurable results
  • skills        - (optional) 3–4 specific technical or soft skills matching the job, with examples
  • cultural_fit  - (optional) alignment with company values, mission or culture if clearly known
  • call_to_action - strong closing: reinforce fit, request interview, show availability
- Each paragraph: 4–5 sentences, 80–110 words. Be specific, avoid clichés, no filler.
- closing: 1 short impactful sentence. Use "{ravi_form}" (the candidate's gender-appropriate form). Never write "ravi(e)". Example: "Je serais {ravi_form} de vous présenter ma candidature lors d'un entretien."
- city_date format: "Ville, J mois YYYY" - use EXACTLY today's date: {today}
- If candidate location has multiple parts, use the first city only
- Extract sender info from the candidate profile (use empty string if missing)
- highlighted_skills: pick the 3–5 skills most relevant to THIS specific job
- key_selling_point: one punchy sentence that captures the candidate's unique value for this role
"""

_REFINE_SYSTEM_PROMPT = """\
You are an expert career coach and professional writer specializing in French cover letters.

You are given a cover letter that was already generated and the user wants to refine it. \
Your job is to apply the user's refinement instructions while preserving everything that works well.

Rules:
- Keep every part the user did NOT ask to change - do not rewrite for the sake of it
- Apply the refinement instructions precisely and only where requested
- If no explicit instruction targets a specific paragraph, keep it as-is (same wording)
- ALL text fields must be written in French
- closing: use "{ravi_form}" (never "ravi(e)")
- city_date format: "Ville, J mois YYYY" - use EXACTLY today's date: {today}
- highlighted_skills, tone and key_selling_point should only change if the instructions imply it
"""


async def generate_cover_letter(
    cv: dict,
    job: dict,
    suggestion: str = "",
    previous_content: dict | None = None,
    gender: str = "",
) -> CoverLetterContent:
    """
    Generates or refines a cover letter.
    When previous_content is provided the LLM refines the existing letter instead of
    generating from scratch - only the parts targeted by suggestion are changed.
    """
    ravi_form = "ravie" if gender == "female" else "ravi"

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.4,
        api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(CoverLetterContent)

    if previous_content:
        system = _REFINE_SYSTEM_PROMPT.format(today=_today_fr(), ravi_form=ravi_form)
        human = (
            f"## Candidate profile\n{_format_cv(cv)}\n\n"
            f"## Job offer\n{_format_job(job)}\n\n"
            f"## Current cover letter (to refine)\n{_format_previous_content(previous_content)}\n\n"
            f"## Refinement instructions\n{suggestion.strip() or 'Améliore globalement la lettre sans changer sa structure.'}"
        )
    else:
        system = _SYSTEM_PROMPT.format(today=_today_fr(), ravi_form=ravi_form)
        human = f"## Candidate profile\n{_format_cv(cv)}\n\n## Job offer\n{_format_job(job)}"
        if suggestion.strip():
            human += f"\n\n## Modification request\n{suggestion.strip()}"

    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    content: CoverLetterContent = await llm.ainvoke(messages)

    logger.info(
        "[cover_letter_agent] %s - tone=%s paragraphs=%d",
        "refined" if previous_content else "generated",
        content.tone,
        len(content.paragraphs),
    )
    return content


def render_pdf(content: CoverLetterContent, body_text: str | None = None) -> bytes:
    """If body_text is given, it replaces the salutation/paragraphs/closing/sign-off
    block (the user's manually edited version) - the header (sender, recipient,
    date, subject) still comes from content, unchanged."""
    from app.cover_letter.backends.reportlab_backend import render

    return render(content, body_text=body_text)


def letter_body_text(content: CoverLetterContent) -> str:
    """The editable "body" of the letter: salutation through sign-off, as a single
    blank-line-separated text block - used only by the legacy PDF-returning endpoints."""
    parts = [content.salutation]
    parts += [p.text for p in content.paragraphs]
    parts.append(content.closing)
    parts.append(content.sign_off)
    return "\n\n".join(parts)


def letter_html(content: CoverLetterContent) -> str:
    """Full letter (header + body) as semantic HTML, deterministically templated from
    the structured content - not written by the LLM. Fed straight into SimpleEditor,
    which parses it into real formatting (bold name, right-aligned date, etc.), not
    literal tags, so the letter looks correct from the first AI generation onward."""
    def esc(text: str) -> str:
        return escape(text or "")

    contact_parts = [p for p in [content.sender.email, content.sender.phone, content.sender.location] if p]
    contact_line = "  ·  ".join(esc(p) for p in contact_parts)

    parts = [
        f"<p><strong>{esc(content.sender.full_name.upper())}</strong>"
        + (f"<br>{contact_line}</p>" if contact_line else "</p>"),
        "<hr>",
        f'<p style="text-align: right">{esc(content.city_date)}</p>',
        f"<p>{esc(content.recipient.company_name)}<br>{esc(content.recipient.contact)}</p>",
        f"<p><strong>Objet :</strong> {esc(content.subject)}</p>",
        f'<p style="text-align: justify">{esc(content.salutation)}</p>',
    ]
    parts += [f'<p style="text-align: justify">{esc(p.text)}</p>' for p in content.paragraphs]
    parts.append(f'<p style="text-align: justify">{esc(content.closing)}</p>')
    parts.append(f'<p style="text-align: justify">{esc(content.sign_off)}</p>')

    return "".join(parts)


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
            lines.append(f"  • {edu.get('degree', '')} - {edu.get('school', '')}")
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


def _format_previous_content(content: dict) -> str:
    """Serialize a CoverLetterContent dict into a readable format for the refinement prompt."""
    lines = [
        f"Subject: {content.get('subject', '')}",
        f"Tone: {content.get('tone', '')}",
        f"Key selling point: {content.get('key_selling_point', '')}",
        "",
    ]
    for i, para in enumerate(content.get("paragraphs", []), 1):
        purpose = para.get("purpose", f"paragraph_{i}")
        text = para.get("text", "")
        lines.append(f"[{purpose}]\n{text}")
        lines.append("")
    lines.append(f"Closing: {content.get('closing', '')}")
    return "\n".join(lines)