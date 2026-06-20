import io

import pdfplumber

from app.logger import get_logger
from app.pipeline.state import PipelineState
from app.storage import read_file

logger = get_logger(__name__)


async def pdf_parser_node(state: PipelineState) -> dict:
    """Node 1 — Extract raw text from a PDF (storage-agnostic via storage.read_file)."""
    key = state["pdf_path"]
    logger.info("[pdf_parser] Reading %s", key)

    pdf_bytes = await read_file(key)
    text_parts: list[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    cv_text = "\n\n".join(text_parts).strip()

    if not cv_text:
        logger.error("[pdf_parser] No text extracted from %s", key)
        raise ValueError(f"No text could be extracted from: {key}")

    logger.info("[pdf_parser] Extracted %d chars from %d pages", len(cv_text), len(text_parts))
    return {"cv_text": cv_text}
