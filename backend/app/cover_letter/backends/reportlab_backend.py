"""ReportLab PDF backend - pure Python, no system dependencies."""
import io

from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from app.cover_letter.generator import CoverLetterContent

_NAVY = HexColor("#1B3A5C")
_GRAY = HexColor("#6B7280")

_LEFT   = 2.2 * cm
_RIGHT  = 2.2 * cm
_TOP    = 1.8 * cm
_BOTTOM = 1.8 * cm


def render(content: CoverLetterContent, body_text: str | None = None) -> bytes:
    W, H = A4
    available_w = W - _LEFT - _RIGHT
    available_h = H - _TOP - _BOTTOM

    # Pass 1 - measure at scale 1.0
    s = _styles(scale=1.0)
    story = _build_story(content, s, scale=1.0, body_text=body_text)
    content_h = _measure_height(story, available_w)

    # Compute scale so content fits exactly, capped at 1.0 (never enlarge)
    scale = min(1.0, available_h / content_h) if content_h > 0 else 1.0

    # Pass 2 - render with scaled fonts and spacers
    s = _styles(scale=scale)
    story = _build_story(content, s, scale=scale, body_text=body_text)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=_LEFT,
        rightMargin=_RIGHT,
        topMargin=_TOP,
        bottomMargin=_BOTTOM,
    )
    doc.build(story)
    return buffer.getvalue()


def _measure_height(story: list, available_w: float) -> float:
    total = 0.0
    for elem in story:
        if isinstance(elem, Spacer):
            total += elem.height
        elif isinstance(elem, HRFlowable):
            total += 1
        elif isinstance(elem, Paragraph):
            _, h = elem.wrap(available_w, 10_000)
            total += h
    return total


def _sp(v: float, scale: float) -> Spacer:
    return Spacer(1, v * scale)


def _build_story(content: CoverLetterContent, s: dict, scale: float, body_text: str | None = None) -> list:
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(content.sender.full_name.upper(), s["name"]))
    story.append(_sp(0.08 * cm, scale))

    contact_parts = [p for p in [content.sender.email, content.sender.phone, content.sender.location] if p]
    if contact_parts:
        story.append(Paragraph("  ·  ".join(contact_parts), s["contact"]))

    story.append(_sp(0.2 * cm, scale))
    story.append(HRFlowable(width="100%", thickness=1, color=_NAVY, spaceAfter=0))
    story.append(_sp(0.4 * cm, scale))

    # ── Date ──────────────────────────────────────────────────────────────────
    story.append(Paragraph(content.city_date, s["date"]))
    story.append(_sp(0.35 * cm, scale))

    # ── Recipient ─────────────────────────────────────────────────────────────
    story.append(Paragraph(content.recipient.company_name, s["recipient_name"]))
    story.append(Paragraph(content.recipient.contact, s["recipient_sub"]))
    story.append(_sp(0.35 * cm, scale))

    # ── Subject ───────────────────────────────────────────────────────────────
    story.append(Paragraph(f"<b>Objet :</b> {content.subject}", s["subject"]))
    story.append(_sp(0.4 * cm, scale))

    # ── Body ──────────────────────────────────────────────────────────────────
    if body_text is not None:
        # User-edited body - each blank-line-separated block becomes its own
        # paragraph, all in the same style (no way to know which block was the
        # salutation/closing/etc. once freely edited).
        blocks = [b.strip() for b in body_text.split("\n\n") if b.strip()]
        for block in blocks:
            story.append(Paragraph(block.replace("\n", "<br/>"), s["body"]))
            story.append(_sp(0.3 * cm, scale))
    else:
        story.append(Paragraph(content.salutation, s["body"]))
        story.append(_sp(0.3 * cm, scale))

        for paragraph in content.paragraphs:
            story.append(Paragraph(paragraph.text, s["body"]))
            story.append(_sp(0.3 * cm, scale))

        story.append(Paragraph(content.closing, s["body"]))
        story.append(_sp(0.45 * cm, scale))
        story.append(Paragraph(content.sign_off, s["body"]))

    story.append(_sp(0.8 * cm, scale))
    story.append(Paragraph(content.sender.full_name, s["signature"]))

    return story


def _styles(scale: float = 1.0) -> dict[str, ParagraphStyle]:
    def fs(size: float) -> float:
        return max(6.0, size * scale)  # never go below 6pt

    return {
        "name": ParagraphStyle(
            "name", fontName="Helvetica-Bold", fontSize=fs(13),
            textColor=_NAVY, leading=fs(16),
        ),
        "contact": ParagraphStyle(
            "contact", fontName="Helvetica", fontSize=fs(8),
            textColor=_GRAY, leading=fs(11),
        ),
        "date": ParagraphStyle(
            "date", fontName="Helvetica", fontSize=fs(9),
            textColor=_GRAY, alignment=TA_RIGHT, leading=fs(11),
        ),
        "recipient_name": ParagraphStyle(
            "recipient_name", fontName="Helvetica-Bold", fontSize=fs(9.5),
            textColor=black, leading=fs(13),
        ),
        "recipient_sub": ParagraphStyle(
            "recipient_sub", fontName="Helvetica", fontSize=fs(9),
            textColor=_GRAY, leading=fs(12),
        ),
        "subject": ParagraphStyle(
            "subject", fontName="Helvetica", fontSize=fs(9.5),
            textColor=black, leading=fs(13),
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=fs(9.5),
            textColor=black, leading=fs(14), alignment=TA_JUSTIFY,
        ),
        "signature": ParagraphStyle(
            "signature", fontName="Helvetica-Bold", fontSize=fs(9.5),
            textColor=_NAVY, leading=fs(13),
        ),
    }
