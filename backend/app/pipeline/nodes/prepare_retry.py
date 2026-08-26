from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)


async def prepare_retry_node(state: PipelineState) -> dict:
    """
    Called when job_search returns 0 results.
    - Accumulates failed keywords so keyword_extractor avoids them
    - Relaxes filters progressively:
        attempt 1 → remove location constraint
        attempt 2 → remove location + contract_type
    """
    current_keywords: list[str] = state.get("keywords") or []
    failed_keywords: list[str] = list(state.get("failed_keywords") or [])
    attempts: int = state.get("search_attempts", 0)

    # Accumulate failed keywords (deduplicated)
    seen = set(failed_keywords)
    for kw in current_keywords:
        if kw not in seen:
            failed_keywords.append(kw)
            seen.add(kw)

    updates: dict = {
        "failed_keywords": failed_keywords,
        "search_attempts": attempts + 1,
        "keywords": [],      # reset so keyword_extractor generates fresh ones
        "jobs": [],
        "filtered_jobs": [], # reset to avoid stale data from previous attempt
    }

    if attempts == 0:
        updates["user_locations"] = []
        logger.info(
            "[prepare_retry] Attempt %d — failed keywords: %s | relaxing: location",
            attempts + 1, failed_keywords,
        )
    else:
        updates["user_locations"] = []
        updates["contract_type"] = ""
        logger.info(
            "[prepare_retry] Attempt %d — failed keywords: %s | relaxing: location + contract_type",
            attempts + 1, failed_keywords,
        )

    return updates