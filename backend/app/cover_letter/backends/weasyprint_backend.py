"""WeasyPrint PDF backend - renders the letter's real HTML (the same markup
SimpleEditor shows and edits), so bold, italic, underline, links, highlight
color, lists and alignment all come through via actual CSS, no hand-rolled
tag-by-tag translation needed."""
from weasyprint import CSS, HTML

_PAGE_CSS = CSS(string="""
    @page {
        size: A4;
        margin: 1.8cm 2.2cm;
    }
    body {
        font-family: Helvetica, Arial, sans-serif;
        font-size: 9.5pt;
        line-height: 1.4;
        color: #111827;
        margin: 0;
    }
    p { margin: 0 0 0.3cm 0; }
    hr { border: none; border-top: 1px solid #1B3A5C; margin: 0.2cm 0 0.4cm 0; }
    a { color: #1B3A5C; }
    ul, ol { margin: 0 0 0.3cm 0; padding-left: 1.2cm; }
    mark { padding: 0 0.05cm; }
    h1, h2, h3, h4 { margin: 0 0 0.3cm 0; line-height: 1.3; }
""")


def render(html: str) -> bytes:
    """`html` is a full letter body (header through sign-off) as produced by
    `letter_html()`, optionally edited by the user in SimpleEditor."""
    document = f"<!doctype html><html><body>{html}</body></html>"
    return HTML(string=document).write_pdf(stylesheets=[_PAGE_CSS])
