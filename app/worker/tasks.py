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
# Runs pdf_parser + cv_structurer only. Called on CV upload (one-time onboarding).
# No job search — just populates cv.data from the PDF.

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
            "user_keywords": [], "keywords": [], "user_locations": [],
            "contract_type": "", "remote": False, "date_posted": "",
            "experience_level": "", "failed_keywords": [], "search_attempts": 0,
            "jobs": [], "filtered_jobs": [], "matches": [], "final_report": "",
            "messages": [],
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

            # Preserve user edits from previous CV
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
            logger.info("[init_profile] completed — cv_id=%s name=%s", cv_id, cv_json.get("full_name"))

        except Exception as exc:
            await prog.publish_done(cv_id)
            logger.error("[init_profile] failed — cv_id=%s | %s", cv_id, exc, exc_info=True)

    _dispose_engines()
    asyncio.run(_run())
    return {"cv_id": cv_id}


# ─── Task: run_search ─────────────────────────────────────────────────────────
# Runs the full job-search pipeline using profile data (cv.data + user.preferences).
# No PDF needed. Called on demand from the profile page.

@celery_app.task(
    name="app.worker.tasks.run_search",
    bind=True,
    max_retries=0,
    time_limit=600,
    soft_time_limit=540,
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
        # Load profile data from DB
        async with AsyncSessionLocal() as db:
            cv   = await cv_svc.get_cv(db, UUID(cv_id))
            user = await user_svc.get_user_by_id(db, UUID(user_id))

        cv_json = (cv.data or {}) if cv else {}
        prefs   = (user.preferences or {}) if user else {}

        contracts  = prefs.get("contract_types") or []
        work_modes = prefs.get("work_modes") or []

        state = {
            "cv_json":          cv_json,
            "user_keywords":    [],
            "keywords":         [],
            "user_locations":   prefs.get("locations") or [],
            "contract_type":    contracts[0] if contracts else "",
            "remote":           "remote" in work_modes,
            "date_posted":      "",
            "experience_level": "",
            "failed_keywords":  [],
            "search_attempts":  0,
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

            keywords_used: list[str] = accumulated.get("keywords") or []
            if keywords_used:
                from app.cortex.registry import register_keywords
                await register_keywords(keywords_used)

            async with AsyncSessionLocal() as db:
                await analysis_svc.update_analysis(
                    db, UUID(analysis_id),
                    status="completed",
                    keywords=accumulated.get("keywords", []),
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


# ─── Task: run_pipeline (deprecated — kept for backwards compat) ──────────────

@celery_app.task(
    name="app.worker.tasks.run_pipeline",
    bind=True,
    max_retries=0,
    time_limit=600,
    soft_time_limit=540,
)
def run_pipeline(
    self,
    analysis_id: str,
    pdf_path: str,
    cv_id: str,
    user_id: str,
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

            # Merge user-curated profile fields from the previous CV so edits
            # made in the profile page survive a new PDF upload.
            # Rules:
            #   - roles      → preserve previous (user-curated job titles)
            #   - skills     → union of previous + new AI-extracted skills
            #   - hobbies    → preserve previous if new PDF didn't extract any
            #   - everything else (experiences, education, contact info, level)
            #     → take fresh from new AI extraction (correct for a new PDF)
            cv_json: dict = result.get("cv_json") or {}
            async with AsyncSessionLocal() as db:
                prev_cv = await cv_svc.get_previous_cv_for_user(
                    db, UUID(user_id), UUID(cv_id)
                )
            if prev_cv and prev_cv.data:
                prev = prev_cv.data
                if prev.get("roles"):
                    cv_json["roles"] = prev["roles"]
                prev_skills = set(prev.get("skills") or [])
                new_skills  = set(cv_json.get("skills") or [])
                cv_json["skills"] = list(new_skills | prev_skills)
                if prev.get("hobbies") and not cv_json.get("hobbies"):
                    cv_json["hobbies"] = prev["hobbies"]

            async with AsyncSessionLocal() as db:
                await cv_svc.update_cv(
                    db, UUID(cv_id),
                    raw_text=result.get("cv_text", ""),
                    data=cv_json,
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
    name="app.worker.tasks.refresh_user_analyses",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def refresh_user_analyses(self) -> dict:
    """
    Celery task — Nightly per-user analysis refresh.
    For each completed analysis whose cortex_snapshot_at is older than cortex_updated_at:
      1. Re-run cortex_search (embedding only, no Adzuna)
      2. Compare returned job hashes with stored matches
      3. If new jobs found → run embeddings_filter + llm_reranker + report_generator
      4. If unchanged → just update cortex_snapshot_at (free)
    Scheduled at 3h — after the 2h ingestion cron.
    """
    logger.info("[worker] refresh_user_analyses started")

    async def _run() -> dict:
        from datetime import timezone

        from app.analysis import service as analysis_svc
        from app.cortex import service as cortex_svc
        from app.cortex.registry import get_cortex_updated_at
        from app.cv import service as cv_svc
        from app.db.session import AsyncSessionLocal
        from app.pipeline.nodes.cortex_search import cortex_search_node
        from app.pipeline.nodes.embeddings_filter import embeddings_filter_node
        from app.pipeline.nodes.llm_reranker import llm_reranker_node
        from app.pipeline.nodes.report_generator import report_generator_node

        import app.users.models    # noqa: F401
        import app.cv.models       # noqa: F401
        import app.analysis.models # noqa: F401

        cortex_updated_at = await get_cortex_updated_at()
        if cortex_updated_at is None:
            logger.info("[refresh] cortex_updated_at not set — Cortex never received new jobs")
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

                # Load user preferences — used instead of stored search_filters when set
                from app.users import service as user_svc
                async with AsyncSessionLocal() as db:
                    user = await user_svc.get_user_by_id(db, analysis.user_id)

                user_prefs     = (user.preferences or {}) if user else {}
                search_filters = analysis.search_filters or {}

                pref_locations    = user_prefs.get("locations", [])
                pref_contracts    = user_prefs.get("contract_types", [])
                pref_work_modes   = user_prefs.get("work_modes", [])

                # Profile preferences override stored search_filters when set
                resolved_locations    = pref_locations  if pref_locations  else search_filters.get("locations", [])
                resolved_contract     = pref_contracts[0] if pref_contracts else search_filters.get("contract_type", "")
                resolved_remote       = ("remote" in pref_work_modes) if pref_work_modes else search_filters.get("remote", False)
                resolved_exp_level    = search_filters.get("experience_level", "")

                cv_json = cv.data

                state = {
                    "cv_json":          cv_json,
                    "user_keywords":    search_filters.get("user_keywords", []),
                    "user_locations":   resolved_locations,
                    "contract_type":    resolved_contract,
                    "remote":           resolved_remote,
                    "experience_level": resolved_exp_level,
                    "keywords":         analysis.keywords or [],
                    "jobs":             [],
                    "filtered_jobs":    [],
                    "matches":          [],
                    "final_report":     "",
                    "failed_keywords":  [],
                    "search_attempts":  0,
                    "pdf_path":         "",
                    "cv_text":          "",
                    "date_posted":      "",
                    "messages":         [],
                }

                # 1. Cortex search (no Adzuna in refresh context)
                cortex_result = await cortex_search_node(state)
                state.update(cortex_result)

                new_pool = state.get("filtered_jobs") or []

                # Always update snapshot so we don't re-check until next ingestion
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
                    logger.debug("[refresh] analysis %s — no new jobs, snapshot updated", analysis.id)
                    continue

                # 3. New jobs — run embeddings_filter → llm_reranker → report_generator
                state["jobs"]         = new_pool
                state["filtered_jobs"] = []

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
                logger.info("[refresh] analysis %s refreshed with new matches", analysis.id)

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
