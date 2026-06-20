"""WeasyPrint PDF backend — HTML/CSS → PDF, best visual quality.

System requirements:
    apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0

Docker:
    RUN apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0
"""
from app.cover_letter.generator import CoverLetterContent

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: A4;
    margin: 2.5cm 3cm;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    color: #111;
    line-height: 1.55;
  }}

  .name {{
    font-size: 20pt;
    font-weight: bold;
    color: #1B3A5C;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 5px;
  }}

  .contact {{
    font-size: 9pt;
    color: #6B7280;
    margin-bottom: 10px;
  }}

  hr {{
    border: none;
    border-top: 1.5px solid #1B3A5C;
    margin-bottom: 22px;
  }}

  .date {{
    text-align: right;
    font-size: 10pt;
    margin-bottom: 22px;
  }}

  .recipient-name {{
    font-weight: bold;
    font-size: 11pt;
    margin-bottom: 2px;
  }}

  .recipient-sub {{
    font-size: 10pt;
    color: #6B7280;
    margin-bottom: 22px;
  }}

  .subject {{
    font-size: 10pt;
    margin-bottom: 22px;
  }}

  .salutation {{ margin-bottom: 14px; }}

  .paragraph {{
    text-align: justify;
    margin-bottom: 14px;
    hyphens: auto;
  }}

  .signoff {{ margin-bottom: 38px; }}

  .signature {{
    font-weight: bold;
    font-size: 11pt;
    color: #1B3A5C;
  }}
</style>
</head>
<body>

  <div class="name">{name}</div>
  <div class="contact">{contact}</div>
  <hr>

  <div class="date">{city_date}</div>

  <div class="recipient-name">{company}</div>
  <div class="recipient-sub">{recipient_contact}</div>

  <div class="subject"><strong>Objet&nbsp;:</strong> {subject}</div>

  <div class="salutation">{salutation}</div>

  {paragraphs_html}

  <div class="paragraph">{closing}</div>
  <div class="paragraph signoff">{sign_off}</div>

  <div class="signature">{name}</div>

</body>
</html>
"""


def render(content: CoverLetterContent) -> bytes:
    from weasyprint import HTML

    contact_parts = [
        p for p in [
            content.sender.email,
            content.sender.phone,
            content.sender.location,
        ] if p
    ]

    paragraphs_html = "\n".join(
        f'<div class="paragraph">{_esc(p.text)}</div>'
        for p in content.paragraphs
    )

    html = _HTML_TEMPLATE.format(
        name=_esc(content.sender.full_name),
        contact=_esc("  ·  ".join(contact_parts)),
        city_date=_esc(content.city_date),
        company=_esc(content.recipient.company_name),
        recipient_contact=_esc(content.recipient.contact),
        subject=_esc(content.subject),
        salutation=_esc(content.salutation),
        paragraphs_html=paragraphs_html,
        closing=_esc(content.closing),
        sign_off=_esc(content.sign_off),
    )

    return HTML(string=html).write_pdf()


def _esc(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )