from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)

TOP_K = 100


def _clean_location(location: str) -> str:
    """Extract usable city/region from raw location strings.
    e.g. 'France - Mobilité nationale' → 'France'
         'Paris, Île-de-France'        → 'Paris'
    """
    if not location:
        return ""
    for sep in (" - ", ",", "/"):
        if sep in location:
            location = location.split(sep)[0]
    return location.strip()


def _build_cv_query(cv: dict, experience_level: str) -> str:
    """Build the vector search query from the CV profile."""
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
    return " | ".join(parts)


async def cortex_search_node(state: PipelineState) -> dict:
    """
    Node 3 - Vector search in the Cortex.
    Returns jobs list (empty if Cortex has no matches).
    The Cortex is the sole source of jobs - no API fallback.
    """
    if CortexSessionLocal is None:
        logger.warning("[cortex_search] CORTEX_DATABASE_URL not configured")
        return {"jobs": []}

    cv = state.get("cv_json") or {}
    user_locations: list[str] = state.get("user_locations") or []
    contract_type:  str       = state.get("contract_type") or ""
    remote:         bool      = state.get("remote") or False
    experience_level: str     = state.get("experience_level") or ""

    cv_query = _build_cv_query(cv, experience_level)
    if not cv_query.strip():
        logger.warning("[cortex_search] Empty CV profile - no jobs returned")
        return {"jobs": []}

    if user_locations:
        effective_locations = user_locations
    else:
        raw_cv_loc = cv.get("location", "") or ""
        cleaned = _clean_location(raw_cv_loc)
        effective_locations = [cleaned] if cleaned else None

    logger.info(
        "[cortex_search] Querying Cortex - contract=%s, remote=%s, seniority=%s, locations=%s",
        contract_type or "all", remote, experience_level or "all", effective_locations,
    )

    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    cv_embedding = await embedder.aembed_query(cv_query)

    async with CortexSessionLocal() as db:
        rows = await cortex_svc.search_jobs(
            db,
            query_embedding=cv_embedding,
            limit=TOP_K,
            contract_type=contract_type,
            remote=remote,
            seniority=experience_level,
            locations=effective_locations,
        )

    logger.info("[cortex_search] %d jobs retrieved from Cortex", len(rows))

    jobs = [
        {
            "title":         r["title"],
            "company":       r["company"],
            "location":      r["location"],
            "desc":          r["description"],
            "url":           r["url"],
            "contract_type": r["contract_type"],
            "remote":        r["remote"],
            "date":          r["created_at"].isoformat() if r.get("created_at") else "",
        }
        for r in rows
    ]

    return {"jobs": jobs}
