from app.logger import get_logger
from app.pipeline.state import PipelineState

logger = get_logger(__name__)


async def cortex_feed_node(state: PipelineState) -> dict:
    """
    Node - After a successful API fallback, enqueue found jobs into the Cortex.
    Fire-and-forget via Celery: does NOT block the main pipeline.
    This is how the Cortex self-enriches from real user searches.
    """
    from app.cortex.db import CortexSessionLocal

    if CortexSessionLocal is None:
        return {}

    jobs: list[dict] = state.get("jobs") or []
    if not jobs:
        return {}

    from app.worker.tasks import feed_cortex_from_fallback
    feed_cortex_from_fallback.delay(jobs=jobs)

    logger.info("[cortex_feed] Enqueued %d jobs for Cortex enrichment", len(jobs))
    return {}