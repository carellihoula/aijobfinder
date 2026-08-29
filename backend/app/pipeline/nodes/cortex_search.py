from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.cv.vectorize import build_cv_vector_texts, flatten_vector_texts, regroup_vectors
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


async def _embed_cv_vectors(cv: dict) -> dict:
    """Embed every CV facet text from `build_cv_vector_texts` in a single
    batched API call, then regroup the results back into the {name: vector}
    shape `cortex_svc.search_jobs` expects."""
    vector_texts = build_cv_vector_texts(cv)
    if not vector_texts:
        return {}

    flat_texts, flat_keys = flatten_vector_texts(vector_texts)

    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    raw_vectors = await embedder.aembed_documents(flat_texts)

    return regroup_vectors(flat_keys, raw_vectors)


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

    query_vectors = await _embed_cv_vectors(cv)
    if "competences" not in query_vectors:
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

    async with CortexSessionLocal() as db:
        rows = await cortex_svc.search_jobs(
            db,
            query_vectors=query_vectors,
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
