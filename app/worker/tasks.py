import asyncio
from uuid import UUID

from app.logger import get_logger
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


def _dispose_engines() -> None:
    """Reset async engine pools before each asyncio.run() call.

    asyncpg connections are bound to the event loop that created them.
    When Celery runs a second task in the same worker process, asyncio.run()
    creates a new loop — old pool connections raise "Future attached to a
    different loop". dispose() clears the pool so fresh connections are made
    on the current loop.
    """
    from app.db.session import engine
    engine.sync_engine.dispose()
    try:
        from app.cortex.db import cortex_engine
        if cortex_engine is not None:
            cortex_engine.sync_engine.dispose()
    except Exception:
        pass


@celery_app.task(
    name="app.worker.tasks.run_pipeline",
    bind=True,
    max_retries=0,   # pipeline failures are logged + stored, not blindly retried
    time_limit=600,  # 10 min hard limit
    soft_time_limit=540,
)
def run_pipeline(
    self,
    analysis_id: str,
    pdf_path: str,
    cv_id: str,
    user_keywords: list[str],
    user_locations: list[str],
    contract_type: str,
    remote: bool,
    date_posted: str,
    experience_level: str,
) -> dict:
    """
    Celery task — Run the full LangGraph pipeline for one CV analysis.
    Progress events are published to Redis Pub/Sub so the FastAPI SSE
    endpoint can stream them to the browser in real time.
    """
    # All models must be imported before any service — SQLAlchemy mapper resolves
    # relationship("User") lazily but needs User in registry before first query.
    import app.users.models    # noqa: F401
    import app.cv.models       # noqa: F401
    import app.analysis.models  # noqa: F401

    from app.analysis import progress as prog
    from app.analysis import service as analysis_svc
    from app.cv import service as cv_svc
    from app.db.session import AsyncSessionLocal
    from app.pipeline.graph import pipeline

    logger.info("[pipeline] task started — analysis_id=%s", analysis_id)

    async def _run() -> None:
        initial_state = {
            "pdf_path":         pdf_path,
            "cv_text":          "",
            "cv_json":          None,
            "user_keywords":    user_keywords,
            "keywords":         [],
            "user_locations":   user_locations,
            "contract_type":    contract_type,
            "remote":           remote,
            "date_posted":      date_posted,
            "experience_level": experience_level,
            "failed_keywords":  [],
            "search_attempts":  0,
            "jobs":             [],
            "filtered_jobs":    [],
            "matches":          [],
            "final_report":     "",
            "messages":         [],
        }

        try:
            accumulated: dict = dict(initial_state)
            async for chunk in pipeline.astream(initial_state, stream_mode="updates"):
                node_name = next(iter(chunk))
                node_output = chunk[node_name]
                # LangGraph emits None for internal nodes (__start__ etc.) — skip them
                if node_output is not None:
                    await prog.publish(analysis_id, node_name)
                    accumulated.update(node_output)
                    logger.debug("[pipeline] node=%s done", node_name)

            await prog.publish_done(analysis_id)
            result = accumulated

            # Register keywords in the cortex registry so the nightly cron
            # can refresh Adzuna for queries that real users actually searched.
            keywords_used: list[str] = result.get("keywords") or []
            if keywords_used:
                from app.cortex.registry import register_keywords
                await register_keywords(keywords_used)

            async with AsyncSessionLocal() as db:
                await cv_svc.update_cv(
                    db, UUID(cv_id),
                    raw_text=result.get("cv_text", ""),
                    data=result.get("cv_json"),
                )
                await analysis_svc.update_analysis(
                    db, UUID(analysis_id),
                    status="completed",
                    keywords=result.get("keywords", []),
                    matches=result.get("matches", []),
                    final_report=result.get("final_report", ""),
                )

            logger.info(
                "[pipeline] completed — analysis_id=%s matches=%d",
                analysis_id, len(result.get("matches", [])),
            )
            await prog.clear(analysis_id)

        except Exception as exc:
            await prog.publish_done(analysis_id)
            logger.error(
                "[pipeline] failed — analysis_id=%s | %s", analysis_id, exc, exc_info=True
            )
            async with AsyncSessionLocal() as db:
                await analysis_svc.update_analysis(
                    db, UUID(analysis_id), status="failed", error=str(exc)
                )

    _dispose_engines()
    asyncio.run(_run())
    return {"analysis_id": analysis_id}


@celery_app.task(
    name="app.worker.tasks.full_ingestion",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # retry after 5 min
)
def full_ingestion(self, locations: list[str] | None = None) -> dict:
    """
    Celery task — Refresh the Cortex using keywords from real user pipelines.
    Only fetches Adzuna offers from the last 3 days — skips if registry is empty.
    Scheduled nightly by Celery Beat.
    Can also be triggered manually via POST /cortex/ingest/full.
    """
    from app.cortex.ingestion import run_ingestion_from_registry

    logger.info("[worker] full_ingestion started — locations=%s", locations)
    try:
        _dispose_engines()
        result = asyncio.run(run_ingestion_from_registry(locations=locations))
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
        _dispose_engines()
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

        _dispose_engines()
        result = asyncio.run(_run())
        logger.info("[worker] cleanup done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] cleanup failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
