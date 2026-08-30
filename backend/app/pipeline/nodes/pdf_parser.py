import io

import pdfplumber
import pytesseract
from starlette.concurrency import run_in_threadpool

from app.logger import get_logger
from app.pipeline.state import PipelineState
from app.storage import read_file

logger = get_logger(__name__)

# Below this, treat the real text layer as effectively empty and fall back to
# OCR - a scanned PDF sometimes still carries a stray line or two of embedded
# text (e.g. a filename watermark), not literally zero characters, so an
# exact `not cv_text` check alone would miss it and fail outright.
MIN_TEXT_LENGTH = 50
OCR_RESOLUTION = 200  # DPI - enough for Tesseract without being needlessly slow


def _ocr_pdf_sync(pdf: pdfplumber.PDF) -> str:
    """Fallback for scanned/image-only PDFs (e.g. a photo of a paper CV saved
    as PDF): rasterize each page and run Tesseract on it. Slower and less
    accurate than reading the real text layer, only used when that layer is
    missing entirely. Synchronous/CPU-bound on purpose - the caller offloads
    it to a thread so it doesn't block the event loop."""
    text_parts: list[str] = []
    for page in pdf.pages:
        image = page.to_image(resolution=OCR_RESOLUTION).original
        page_text = pytesseract.image_to_string(image, lang="fra+eng")
        if page_text.strip():
            text_parts.append(page_text)
    return "\n\n".join(text_parts).strip()


async def pdf_parser_node(state: PipelineState) -> dict:
    """Node 1 - Extract raw text from a PDF (storage-agnostic via storage.read_file).
    Tries the PDF's real text layer first (fast, accurate); falls back to OCR
    only when that layer is empty or near-empty - a scanned CV, where pages
    are really just an image with no embedded text at all."""
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

        if len(cv_text) < MIN_TEXT_LENGTH:
            logger.info(
                "[pdf_parser] Text layer too thin (%d chars) - falling back to OCR: %s",
                len(cv_text), key,
            )
            cv_text = await run_in_threadpool(_ocr_pdf_sync, pdf)

    if not cv_text:
        logger.error("[pdf_parser] No text extracted (including OCR) from %s", key)
        raise ValueError(f"No text could be extracted from: {key}")

    logger.info("[pdf_parser] Extracted %d chars from %d pages", len(cv_text), len(text_parts))
    return {"cv_text": cv_text}