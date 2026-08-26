from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)


class _KeywordsOutput(BaseModel):
    keywords: list[str] = Field(
        description="3 to 6 job search queries, ordered by relevance, each 2-5 words"
    )


MAX_KEYWORDS = 10

_SYSTEM_PROMPT = """\
You are a job search expert.
Given a candidate profile, generate exactly {n} short job search queries optimized for job boards.
Each query must combine the main role + key skills or seniority when relevant.
Keep each query between 2 and 5 words, concrete, and directly usable as a job board search term.
Examples: "Senior Python Developer", "ML Engineer PyTorch", "Data Scientist NLP".
Do NOT include location in the queries.
"""

_RETRY_SYSTEM_PROMPT = """\
You are a job search expert.
The following queries returned ZERO results on job boards: {failed_keywords}

Generate exactly {n} DIFFERENT search queries for the same candidate.
Rules:
- Do NOT reuse or paraphrase the failed queries
- Be broader and more generic (e.g. "Developer" instead of "Python FastAPI Developer")
- Try different angles: adjacent roles, different skill combinations, more common job titles
- Each query must be 2-5 words
"""


async def keyword_extractor_node(state: PipelineState) -> dict:
    """
    Node — Generate job search queries from the CV profile.
    On retry (failed_keywords not empty), generates different and broader queries.
    """
    cv = state.get("cv_json") or {}
    user_keywords: list[str] = state.get("user_keywords") or []
    failed_keywords: list[str] = state.get("failed_keywords") or []
    is_retry = bool(failed_keywords)

    logger.info(
        "[keyword_extractor] %s | user_keywords=%s | failed=%s",
        "RETRY" if is_retry else "first run",
        user_keywords,
        failed_keywords,
    )

    slots_left = MAX_KEYWORDS - len(user_keywords)
    if slots_left <= 0:
        logger.info("[keyword_extractor] Slots full — skipping AI generation")
        return {"keywords": user_keywords}

    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.4 if is_retry else 0.2,  # more creative on retry
        api_key=settings.OPENAI_API_KEY,
    ).with_structured_output(_KeywordsOutput)

    cv_summary = (
        f"Roles: {', '.join(cv.get('roles', []) or [])}\n"
        f"Skills: {', '.join((cv.get('skills') or [])[:15])}\n"
        f"Level: {cv.get('level', 'mid')}\n"
        f"Years of experience: {cv.get('experience_years', 0)}"
    )

    if is_retry:
        system_content = _RETRY_SYSTEM_PROMPT.format(
            failed_keywords=failed_keywords,
            n=slots_left,
        )
    else:
        system_content = _SYSTEM_PROMPT.format(n=slots_left)

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=f"Generate {slots_left} search queries for this candidate:\n{cv_summary}"),
    ]

    result: _KeywordsOutput = await llm.ainvoke(messages)
    logger.info("[keyword_extractor] Generated keywords: %s", result.keywords)

    # Merge: user keywords first, then AI-generated (deduplicated, exclude failed)
    failed_set = {kw.strip().lower() for kw in failed_keywords}
    seen: set[str] = {kw.strip().lower() for kw in user_keywords}
    merged: list[str] = list(user_keywords)

    for kw in result.keywords:
        normalized = kw.strip().lower()
        if normalized and normalized not in seen and normalized not in failed_set:
            seen.add(normalized)
            merged.append(kw.strip())
            if len(merged) >= MAX_KEYWORDS:
                break

    logger.info("[keyword_extractor] Final keywords (%d): %s", len(merged), merged)
    return {"keywords": merged}