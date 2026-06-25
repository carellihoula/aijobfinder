from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

TOP_K = 100


def _build_cv_query(cv: dict, experience_level: str, user_keywords: list[str]) -> str:
    """
    Build the vector search query for the Cortex.
    - CV profile (roles, skills, level) = base semantic signal
    - experience_level = seniority bias
    - user_keywords = additional semantic bias (NOT API queries — they orient the vector
      toward what the user explicitly wants, e.g. 'machine learning', 'healthcare')
    """
    parts = []
    if cv.get("roles"):
        parts.append("Roles: " + ", ".join(cv["roles"]))
    if cv.get("skills"):
        parts.append("Skills: " + ", ".join(cv["skills"][:20]))
    if cv.get("summary"):
        parts.append(cv["summary"])
    if cv.get("level"):
        parts.append("Level: " + cv["level"])
    if experience_level:
        parts.append(f"Target seniority: {experience_level}")
    if user_keywords:
        parts.append("Focus: " + ", ".join(user_keywords))
    return " | ".join(parts)


async def cortex_search_node(state: PipelineState) -> dict:
    """
    Node 3 — Vector search in the Cortex.
    Returns filtered_jobs if results found, empty list if Cortex has no matches
    (triggers fallback to direct API search in the graph).
    """
    if CortexSessionLocal is None:
        logger.warning("[cortex_search] CORTEX_DATABASE_URL not configured — triggering fallback")
        return {"filtered_jobs": []}

    cv = state.get("cv_json") or {}
    user_locations: list[str] = state.get("user_locations") or []
    contract_type: str = state.get("contract_type") or ""
    remote: bool = state.get("remote") or False
    experience_level: str = state.get("experience_level") or ""
    user_keywords: list[str] = state.get("user_keywords") or []

    cv_query = _build_cv_query(cv, experience_level, user_keywords)
    if not cv_query.strip():
        logger.warning("[cortex_search] Empty CV profile — triggering fallback")
        return {"filtered_jobs": []}

    # Same priority as job_search: profile config > CV location > no filter
    if user_locations:
        effective_locations = user_locations
    else:
        from app.pipeline.nodes.job_search import _clean_location
        raw_cv_loc: str = cv.get("location", "") or ""
        cleaned_cv_loc = _clean_location(raw_cv_loc)
        effective_locations = [cleaned_cv_loc] if cleaned_cv_loc else None

    logger.info(
        "[cortex_search] Embedding CV query (%d chars) — contract=%s, remote=%s, seniority=%s, locations=%s",
        len(cv_query), contract_type or "all", remote, experience_level or "all", effective_locations,
    )

    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    cv_embedding = await embedder.aembed_query(cv_query)

    async with CortexSessionLocal() as db:
        jobs = await cortex_svc.search_jobs(
            db,
            query_embedding=cv_embedding,
            limit=TOP_K,
            contract_type=contract_type,
            remote=remote,
            seniority=experience_level,
            locations=effective_locations,
        )

    logger.info("[cortex_search] %d jobs retrieved from Cortex", len(jobs))

    if not jobs:
        logger.warning("[cortex_search] No results — graph will fallback to direct API search")
        return {"filtered_jobs": []}

    filtered_jobs = [
        {
            "title":         j["title"],
            "company":       j["company"],
            "location":      j["location"],
            "desc":          j["description"],
            "url":           j["url"],
            "contract_type": j["contract_type"],
            "remote":        j["remote"],
            "date":          j["created_at"].isoformat() if j.get("created_at") else "",
        }
        for j in jobs
    ]

    return {"filtered_jobs": filtered_jobs}