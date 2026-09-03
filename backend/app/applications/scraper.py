import html
import re

import httpx
import trafilatura
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.logger import get_logger
from app.observability.langfuse_client import get_langfuse_callbacks

logger = get_logger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACES_RE = re.compile(r"[ \t ]+")       # runs of spaces/tabs/non-breaking space (not newlines)
_BLANK_LINES_RE = re.compile(r"\n[ \t]*(\n[ \t]*)+")  # 2+ consecutive line breaks


def clean_pasted_text(text: str) -> str:
    """Clean text pasted from a rich editor or web page: strip any HTML markup, decode
    entities, and normalize whitespace while keeping paragraph breaks readable."""
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_FETCH_TIMEOUT = 15.0
_MAX_TEXT_CHARS = 8000  # cap before sending to the LLM


class JobOfferNotFound(Exception):
    """Raised when a URL could not be fetched or no readable content could be extracted."""


async def fetch_job_text(url: str) -> str:
    """Download a job posting page and extract its main readable text (boilerplate stripped)."""
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT}, timeout=_FETCH_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("[applications] Failed to fetch %s: %s", url, exc)
        raise JobOfferNotFound(f"Could not fetch URL: {exc}") from exc

    text = trafilatura.extract(response.text, include_comments=False, include_tables=False)
    if not text or len(text.strip()) < 50:
        raise JobOfferNotFound("Could not extract readable content from this page")

    return text[:_MAX_TEXT_CHARS]


class _JobExtract(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str = Field(default="", description="Job location, empty if not found")
    short_summary: str = Field(
        description="2-3 sentence summary of the role, used for display when no source link is available"
    )


_SYSTEM_PROMPT = """\
You are an expert at reading job postings.
Extract the job title, company name, location, and a short 2-3 sentence summary from the text below.
If a field cannot be found, use an empty string.\
"""


async def extract_job(text: str) -> _JobExtract:
    """Extract title/company/location/summary from raw job posting text via structured LLM output."""
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_LIGHT,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        callbacks=get_langfuse_callbacks(),
    )
    structured_llm = llm.with_structured_output(_JobExtract)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Job posting text:\n\n{text}"),
    ]

    logger.info("[applications] Extracting job info from text (%d chars) ...", len(text))
    result: _JobExtract = await structured_llm.ainvoke(messages)
    return result
