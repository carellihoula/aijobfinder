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
    different loop". dispose(close=False) drops pool references without
    trying to close asyncpg connections (which would fail outside a greenlet).
    New connections are created fresh on the current loop.
    """
    from app.db.session import engine
    engine.sync_engine.dispose(close=False)
    try:
        from app.cortex.db import cortex_engine
        if cortex_engine is not None:
            cortex_engine.sync_engine.dispose(close=False)
    except Exception:
        pass


def _merge_prev_profile(cv_json: dict, prev_data: dict) -> dict:
    """Preserve user-curated profile fields when a new CV replaces the old one."""
    if prev_data.get("roles"):
        cv_json["roles"] = prev_data["roles"]
    prev_skills = set(prev_data.get("skills") or [])
    new_skills  = set(cv_json.get("skills") or [])
    cv_json["skills"] = list(new_skills | prev_skills)
    if prev_data.get("hobbies") and not cv_json.get("hobbies"):
        cv_json["hobbies"] = prev_data["hobbies"]
    return cv_json


# ─── Task: init_profile ───────────────────────────────────────────────────────

@celery_app.task(
    name="app.worker.tasks.init_profile",
    bind=True,
    max_retries=0,
    time_limit=120,
    soft_time_limit=100,
)
def init_profile(self, cv_id: str, user_id: str, pdf_path: str) -> dict:
    """Extract and structure CV data from a PDF. Progress events keyed on cv_id."""
    import app.users.models    # noqa: F401
    import app.cv.models       # noqa: F401
    import app.analysis.models # noqa: F401

    from app.analysis import progress as prog
    from app.cv import service as cv_svc
    from app.db.session import AsyncSessionLocal
    from app.pipeline.graph import profile_init_pipeline

    logger.info("[init_profile] started — cv_id=%s", cv_id)

    async def _run() -> None:
        state = {
            "pdf_path": pdf_path, "cv_text": "", "cv_json": None,
            "user_locations": [], "contract_type": "", "remote": False,
            "experience_level": "", "jobs": [], "filtered_jobs": [],
            "matches": [], "final_report": "", "messages": [],
        }
        try:
            accumulated: dict = dict(state)
            async for chunk in profile_init_pipeline.astream(state, stream_mode="updates"):
                node_name = next(iter(chunk))
                node_output = chunk[node_name]
                if node_output is not None:
                    await prog.publish(cv_id, node_name)
                    accumulated.update(node_output)

            await prog.publish_done(cv_id)
            cv_json: dict = accumulated.get("cv_json") or {}

            async with AsyncSessionLocal() as db:
                prev_cv = await cv_svc.get_previous_cv_for_user(db, UUID(user_id), UUID(cv_id))
            if prev_cv and prev_cv.data:
                cv_json = _merge_prev_profile(cv_json, prev_cv.data)

            async with AsyncSessionLocal() as db:
                await cv_svc.update_cv(
                    db, UUID(cv_id),
                    raw_text=accumulated.get("cv_text", ""),
                    data=cv_json,
                )
            logger.info("[init_profile] completed — cv_id=%s", cv_id)

        except Exception as exc:
            await prog.publish_done(cv_id)
            logger.error("[init_profile] failed — cv_id=%s | %s", cv_id, exc, exc_info=True)

    _dispose_engines()
    asyncio.run(_run())
    return {"cv_id": cv_id}


# ─── Task: run_search ─────────────────────────────────────────────────────────

@celery_app.task(
    name="app.worker.tasks.run_search",
    bind=True,
    max_retries=0,
    time_limit=300,
    soft_time_limit=270,
)
def run_search(self, analysis_id: str, cv_id: str, user_id: str) -> dict:
    """Run job search pipeline from profile data. Progress events keyed on analysis_id."""
    import app.users.models    # noqa: F401
    import app.cv.models       # noqa: F401
    import app.analysis.models # noqa: F401

    from app.analysis import progress as prog
    from app.analysis import service as analysis_svc
    from app.cv import service as cv_svc
    from app.db.session import AsyncSessionLocal
    from app.pipeline.graph import search_pipeline
    from app.users import service as user_svc

    logger.info("[run_search] started — analysis_id=%s", analysis_id)

    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            cv   = await cv_svc.get_cv(db, UUID(cv_id))
            user = await user_svc.get_user_by_id(db, UUID(user_id))

        cv_json = (cv.data or {}) if cv else {}
        prefs   = (user.preferences or {}) if user else {}

        contracts  = prefs.get("contract_types") or []
        work_modes = prefs.get("work_modes") or []

        state = {
            "cv_json":          cv_json,
            "user_locations":   prefs.get("locations") or [],
            "contract_type":    contracts[0] if contracts else "",
            "remote":           "remote" in work_modes,
            "experience_level": "",
            "jobs":             [],
            "filtered_jobs":    [],
            "matches":          [],
            "final_report":     "",
            "messages":         [],
            "pdf_path":         "",
            "cv_text":          "",
        }

        try:
            accumulated: dict = dict(state)
            async for chunk in search_pipeline.astream(state, stream_mode="updates"):
                node_name = next(iter(chunk))
                node_output = chunk[node_name]
                if node_output is not None:
                    await prog.publish(analysis_id, node_name)
                    accumulated.update(node_output)

            await prog.publish_done(analysis_id)

            async with AsyncSessionLocal() as db:
                await analysis_svc.update_analysis(
                    db, UUID(analysis_id),
                    status="completed",
                    keywords=[],
                    matches=accumulated.get("matches", []),
                    final_report=accumulated.get("final_report", ""),
                )

            logger.info(
                "[run_search] completed — analysis_id=%s matches=%d",
                analysis_id, len(accumulated.get("matches", [])),
            )
            await prog.clear(analysis_id)

        except Exception as exc:
            await prog.publish_done(analysis_id)
            logger.error("[run_search] failed — analysis_id=%s | %s", analysis_id, exc, exc_info=True)
            async with AsyncSessionLocal() as db:
                await analysis_svc.update_analysis(db, UUID(analysis_id), status="failed", error=str(exc))

    _dispose_engines()
    asyncio.run(_run())
    return {"analysis_id": analysis_id}


# ─── Tasks: provider ingestion ────────────────────────────────────────────────

@celery_app.task(
    name="app.worker.tasks.ingest_france_travail",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def ingest_france_travail(self) -> dict:
    """Fetch jobs from France Travail API and store in Cortex."""
    from app.cortex.ingestion import run_provider_ingestion
    from app.cortex.providers.france_travail import FranceTravailProvider

    logger.info("[worker] ingest_france_travail started")
    try:
        _dispose_engines()
        result = asyncio.run(run_provider_ingestion(FranceTravailProvider()))
        logger.info("[worker] ingest_france_travail done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] ingest_france_travail failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.ingest_greenhouse",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def ingest_greenhouse(self) -> dict:
    """Fetch jobs from Greenhouse (French companies) and store in Cortex."""
    from app.cortex.ingestion import run_provider_ingestion
    from app.cortex.providers.greenhouse import GreenhouseProvider

    logger.info("[worker] ingest_greenhouse started")
    try:
        _dispose_engines()
        result = asyncio.run(run_provider_ingestion(GreenhouseProvider()))
        logger.info("[worker] ingest_greenhouse done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] ingest_greenhouse failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.ingest_lever",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def ingest_lever(self) -> dict:
    """Fetch jobs from Lever (French companies) and store in Cortex."""
    from app.cortex.ingestion import run_provider_ingestion
    from app.cortex.providers.lever import LeverProvider

    logger.info("[worker] ingest_lever started")
    try:
        _dispose_engines()
        result = asyncio.run(run_provider_ingestion(LeverProvider()))
        logger.info("[worker] ingest_lever done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] ingest_lever failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.worker.tasks.full_ingestion",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def full_ingestion(self) -> dict:
    """Run all providers sequentially. Scheduled nightly by Celery Beat."""
    from app.cortex.ingestion import run_all_providers

    logger.info("[worker] full_ingestion started")
    try:
        _dispose_engines()
        result = asyncio.run(run_all_providers())
        logger.info("[worker] full_ingestion done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] full_ingestion failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


# ─── Task: refresh_user_analyses ─────────────────────────────────────────────

@celery_app.task(
    name="app.worker.tasks.refresh_user_analyses",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def refresh_user_analyses(self) -> dict:
    """
    Nightly per-user refresh.
    For each completed analysis whose cortex_snapshot_at < cortex_updated_at:
      1. Re-run cortex_search
      2. If new jobs found → run embeddings_filter + llm_reranker + report_generator
      3. If unchanged → just update cortex_snapshot_at (free)
    Scheduled at 3h — after the 2h ingestion cron.
    """
    logger.info("[worker] refresh_user_analyses started")

    async def _run() -> dict:
        import app.users.models    # noqa: F401
        import app.cv.models       # noqa: F401
        import app.analysis.models # noqa: F401

        from app.analysis import service as analysis_svc
        from app.cortex import service as cortex_svc
        from app.cortex.registry import get_cortex_updated_at
        from app.cv import service as cv_svc
        from app.db.session import AsyncSessionLocal
        from app.pipeline.nodes.cortex_search import cortex_search_node
        from app.pipeline.nodes.embeddings_filter import embeddings_filter_node
        from app.pipeline.nodes.llm_reranker import llm_reranker_node
        from app.pipeline.nodes.report_generator import report_generator_node

        cortex_updated_at = await get_cortex_updated_at()
        if cortex_updated_at is None:
            logger.info("[refresh] cortex_updated_at not set — skipping")
            return {"checked": 0, "refreshed": 0, "skipped": 0}

        async with AsyncSessionLocal() as db:
            analyses = await analysis_svc.get_stale_analyses(db, cortex_updated_at)

        logger.info("[refresh] %d stale analyses to check", len(analyses))
        refreshed = skipped = 0

        for analysis in analyses:
            try:
                async with AsyncSessionLocal() as db:
                    cv = await cv_svc.get_cv(db, analysis.cv_id)
                if not cv or not cv.data:
                    continue

                from app.users import service as user_svc
                async with AsyncSessionLocal() as db:
                    user = await user_svc.get_user_by_id(db, analysis.user_id)

                user_prefs     = (user.preferences or {}) if user else {}
                search_filters = analysis.search_filters or {}

                pref_locations  = user_prefs.get("locations", [])
                pref_contracts  = user_prefs.get("contract_types", [])
                pref_work_modes = user_prefs.get("work_modes", [])

                state = {
                    "cv_json":          cv.data,
                    "user_locations":   pref_locations or search_filters.get("locations", []),
                    "contract_type":    pref_contracts[0] if pref_contracts else search_filters.get("contract_type", ""),
                    "remote":           ("remote" in pref_work_modes) if pref_work_modes else search_filters.get("remote", False),
                    "experience_level": search_filters.get("experience_level", ""),
                    "jobs":             [],
                    "filtered_jobs":    [],
                    "matches":          [],
                    "final_report":     "",
                    "messages":         [],
                    "pdf_path":         "",
                    "cv_text":          "",
                }

                # 1. Cortex search
                cortex_result = await cortex_search_node(state)
                state.update(cortex_result)

                new_pool = state.get("jobs") or []

                # Always update snapshot timestamp
                async with AsyncSessionLocal() as db:
                    await analysis_svc.update_analysis(
                        db, analysis.id, cortex_snapshot_at=cortex_updated_at
                    )

                if not new_pool:
                    skipped += 1
                    continue

                # 2. Compare job hashes with stored matches
                existing_hashes = {
                    cortex_svc.make_job_hash(
                        m["job"].get("title", ""),
                        m["job"].get("company", ""),
                        m["job"].get("location", ""),
                    )
                    for m in (analysis.matches or [])
                }
                new_hashes = {
                    cortex_svc.make_job_hash(j.get("title", ""), j.get("company", ""), j.get("location", ""))
                    for j in new_pool
                }

                if not (new_hashes - existing_hashes):
                    skipped += 1
                    continue

                # 3. New jobs found — run embeddings_filter → llm_reranker → report_generator
                emb_result = await embeddings_filter_node(state)
                state.update(emb_result)

                rerank_result = await llm_reranker_node(state)
                state.update(rerank_result)

                report_result = await report_generator_node(state)
                state.update(report_result)

                async with AsyncSessionLocal() as db:
                    await analysis_svc.update_analysis(
                        db, analysis.id,
                        matches=state.get("matches", []),
                        final_report=state.get("final_report", ""),
                        cortex_snapshot_at=cortex_updated_at,
                    )

                refreshed += 1
                logger.info("[refresh] analysis %s refreshed", analysis.id)

            except Exception as exc:
                logger.error("[refresh] analysis %s failed: %s", analysis.id, exc, exc_info=True)

        logger.info("[refresh] done — checked=%d, refreshed=%d, skipped=%d", len(analyses), refreshed, skipped)
        return {"checked": len(analyses), "refreshed": refreshed, "skipped": skipped}

    try:
        _dispose_engines()
        result = asyncio.run(_run())
        logger.info("[worker] refresh_user_analyses done — %s", result)
        return result
    except Exception as exc:
        logger.error("[worker] refresh_user_analyses failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


# ─── Task: cleanup_old_jobs ───────────────────────────────────────────────────

@celery_app.task(
    name="app.worker.tasks.cleanup_old_jobs",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def cleanup_old_jobs(self, days: int = 30) -> dict:
    """Deactivate jobs not seen in the last N days. Scheduled weekly."""
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


# ─── Task: generate_application_cover_letter ──────────────────────────────────

@celery_app.task(
    name="app.worker.tasks.generate_application_cover_letter",
    bind=True,
    max_retries=0,
    time_limit=120,
    soft_time_limit=100,
)
def generate_application_cover_letter(
    self,
    application_id: str,
    job: dict,
    user_id: str,
    suggestion: str = "",
    previous_content: dict | None = None,
) -> dict:
    """Generate (or refine) a cover letter for a manually-added application. Runs off the
    request/response cycle since the LLM structured-output call can take ~30-60s."""
    import app.users.models        # noqa: F401
    import app.cv.models           # noqa: F401
    import app.analysis.models     # noqa: F401
    import app.applications.models # noqa: F401

    from app.applications import service as applications_svc
    from app.cover_letter.generator import generate_cover_letter
    from app.cv import service as cv_svc
    from app.db.session import AsyncSessionLocal
    from app.users import service as user_svc

    logger.info("[generate_application_cover_letter] started — application_id=%s", application_id)

    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            cv = await cv_svc.get_latest_cv_for_user(db, UUID(user_id))
            user = await user_svc.get_user_by_id(db, UUID(user_id))
        cv_data = (cv.data or {}) if cv else {}
        gender = (user.preferences or {}).get("gender", "") if user and user.preferences else ""

        try:
            content = await generate_cover_letter(
                cv_data, job, suggestion=suggestion, previous_content=previous_content, gender=gender,
            )
            async with AsyncSessionLocal() as db:
                await applications_svc.set_cover_letter_result(
                    db, UUID(application_id), status="completed", content=content.model_dump(),
                )
            logger.info("[generate_application_cover_letter] completed — application_id=%s", application_id)
        except Exception as exc:
            logger.error(
                "[generate_application_cover_letter] failed — application_id=%s | %s",
                application_id, exc, exc_info=True,
            )
            async with AsyncSessionLocal() as db:
                await applications_svc.set_cover_letter_result(
                    db, UUID(application_id), status="failed", content=None,
                )

    _dispose_engines()
    asyncio.run(_run())
    return {"application_id": application_id}
