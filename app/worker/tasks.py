import asyncio

from app.logger import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.worker.tasks.full_ingestion",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # retry after 5 min
)
def full_ingestion(self, locations: list[str] | None = None, domain: str | None = None) -> dict:
    """
    Celery task — Broad Cortex ingestion using seed keywords.
    Scheduled nightly by Celery Beat.
    Can also be triggered manually via POST /cortex/ingest/full.
    """
    from app.cortex.ingestion import run_full_ingestion

    logger.info("[worker] full_ingestion started — domain=%s, locations=%s", domain, locations)
    try:
        result = asyncio.run(run_full_ingestion(locations=locations, domain=domain))
        logger.info("[worker] full_ingestion done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] full_ingestion failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.feed_cortex_from_fallback",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def feed_cortex_from_fallback(self, jobs: list[dict]) -> dict:
    """
    Celery task — Store jobs found via API fallback into the Cortex.
    Triggered automatically by cortex_feed_node after each successful API fallback.
    This is how the Cortex self-enriches from real user searches.
    """
    from app.cortex.ingestion import store_jobs_from_fallback

    logger.info("[worker] feed_cortex_from_fallback — %d jobs", len(jobs))
    try:
        result = asyncio.run(store_jobs_from_fallback(jobs))
        logger.info("[worker] feed done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] feed failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.cleanup_old_jobs",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def cleanup_old_jobs(self, days: int = 30) -> dict:
    """
    Celery task — Deactivate jobs not seen in the last N days.
    Scheduled weekly by Celery Beat.
    """
    from app.cortex import service as cortex_svc
    from app.cortex.db import CortexSessionLocal

    logger.info("[worker] cleanup_old_jobs started — days=%d", days)
    try:
        async def _run():
            if CortexSessionLocal is None:
                return {"deactivated": 0, "purged": 0}
            async with CortexSessionLocal() as db:
                deactivated = await cortex_svc.deactivate_old_jobs(db, days)
            async with CortexSessionLocal() as db:
                purged = await cortex_svc.purge_inactive_jobs(db, days=days * 3)
            return {"deactivated": deactivated, "purged": purged}

        result = asyncio.run(_run())
        logger.info("[worker] cleanup done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] cleanup failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
