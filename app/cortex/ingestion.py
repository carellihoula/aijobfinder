import asyncio

import httpx
from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.cortex.enricher import enrich_seniority
from app.logger import get_logger
from app.pipeline.nodes.job_search import _search_adzuna

logger = get_logger(__name__)


async def run_ingestion_from_registry(locations: list[str] | None = None) -> dict:
    """
    Nightly cron ingestion — uses keywords accumulated from real user pipelines.
    Fetches only offers from the last 3 days (date_posted="3") to stay efficient.
    Returns early if the registry is empty (no users have run the pipeline yet).

    Called by: Celery Beat nightly cron, POST /cortex/ingest/full admin endpoint.
    """
    from app.cortex.registry import get_all_keywords

    keywords = await get_all_keywords()
    if not keywords:
        logger.info("[ingestion] Registry empty — no user keywords yet, skipping")
        return {"fetched": 0, "new": 0, "stored": 0}

    logger.info("[ingestion] Registry ingestion — %d keywords", len(keywords))
    return await run_ingestion(keywords, locations, date_posted="3")


async def run_seed_ingestion(keywords: list[str], locations: list[str] | None = None) -> dict:
    """Manual admin bootstrap with explicit keywords (no date filter)."""
    logger.info("[ingestion] Seed ingestion — %d keywords", len(keywords))
    return await run_ingestion(keywords, locations, date_posted="")


async def run_ingestion(keywords: list[str], locations: list[str] | None = None, date_posted: str = "") -> dict:
    """
    Ingestion pipeline:
      1. Fetch raw jobs from Adzuna
      2. Deduplicate in memory (hash: title+company+location)
      3. Identify jobs already in Cortex → refresh last_seen only
      4. Detect seniority via LLM batch (30 jobs/call, gpt-4o-mini)
      5. Embed new jobs
      6. Store in Cortex

    date_posted: Adzuna filter — "" = all time, "1" = last 24h, "3" = last 3 days.
    """
    if CortexSessionLocal is None:
        logger.error("[ingestion] CORTEX_DATABASE_URL not configured")
        return {"fetched": 0, "new": 0, "stored": 0}

    if locations is None:
        locations = [""]

    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        logger.warning("[ingestion] Adzuna not configured")
        return {"fetched": 0, "new": 0, "stored": 0}

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    logger.info(
        "[ingestion] Fetching via Adzuna — keywords=%d, locations=%s",
        len(keywords), locations,
    )
    combos = [(kw, loc) for kw in keywords for loc in locations]
    raw_results = []
    async with httpx.AsyncClient(timeout=30) as client:
        for i, (kw, loc) in enumerate(combos):
            try:
                result = await _search_adzuna(client, kw, loc, "", False, date_posted, "")
                raw_results.append(result)
            except Exception as exc:
                raw_results.append(exc)
            if i < len(combos) - 1:
                await asyncio.sleep(1.2)

    # ── 2. Deduplicate in memory ──────────────────────────────────────────────
    seen: set[str] = set()
    raw_jobs: list[dict] = []
    for batch in raw_results:
        if isinstance(batch, Exception):
            logger.warning("[ingestion] Provider call failed: %s", batch)
            continue
        for job in batch:
            h = cortex_svc.make_job_hash(
                job.get("title", ""), job.get("company", ""), job.get("location", "")
            )
            if h not in seen:
                seen.add(h)
                job["job_hash"] = h
                raw_jobs.append(job)

    logger.info("[ingestion] %d unique raw jobs fetched", len(raw_jobs))
    if not raw_jobs:
        return {"fetched": 0, "new": 0, "stored": 0}

    # ── 3. Check DB ───────────────────────────────────────────────────────────
    all_hashes = [j["job_hash"] for j in raw_jobs]
    async with CortexSessionLocal() as db:
        existing = await cortex_svc.get_existing_hashes(db, all_hashes)
        await cortex_svc.refresh_seen(db, list(existing))

    new_jobs = [j for j in raw_jobs if j["job_hash"] not in existing]
    logger.info(
        "[ingestion] %d new jobs to process (%d already in Cortex)",
        len(new_jobs), len(existing),
    )
    if not new_jobs:
        return {"fetched": len(raw_jobs), "new": 0, "stored": 0}

    # ── 4. Enrich seniority via LLM ───────────────────────────────────────────
    enriched = await enrich_seniority(new_jobs)

    # ── 5. Embed ──────────────────────────────────────────────────────────────
    logger.info("[ingestion] Embedding %d jobs ...", len(enriched))
    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    texts = [
        f"{j.get('title', '')} {j.get('desc', '')}".strip()
        for j in enriched
    ]
    embeddings = await embedder.aembed_documents(texts)

    # ── 6. Store ──────────────────────────────────────────────────────────────
    stored = 0
    async with CortexSessionLocal() as db:
        for job, emb in zip(enriched, embeddings):
            try:
                await cortex_svc.upsert_job(db, {
                    "job_hash":      job["job_hash"],
                    "title":         job.get("title", ""),
                    "company":       job.get("company", ""),
                    "location":      job.get("location", ""),
                    "description":   job.get("desc", ""),
                    "url":           job.get("url", ""),
                    "source":        job.get("source", ""),
                    "contract_type": job.get("contract_type", ""),
                    "remote":        job.get("remote", False),
                    "seniority":     job.get("seniority", ""),
                    "embedding":     emb,
                })
                stored += 1
            except Exception as exc:
                logger.warning("[ingestion] Failed to store '%s': %s", job.get("title"), exc)

    logger.info(
        "[ingestion] Done — fetched=%d, new=%d, stored=%d",
        len(raw_jobs), len(new_jobs), stored,
    )
    return {"fetched": len(raw_jobs), "new": len(new_jobs), "stored": stored}


async def store_jobs_from_fallback(jobs: list[dict]) -> dict:
    """
    Store jobs found by the API fallback directly into the Cortex.
    Skips the fetch step — jobs are already in memory from job_search_node.
    Pipeline: dedup → enrich seniority → embed → store.
    """
    if CortexSessionLocal is None or not jobs:
        return {"new": 0, "stored": 0}

    # ── 1. Add job_hash ───────────────────────────────────────────────────────
    seen: set[str] = set()
    hashed_jobs: list[dict] = []
    for job in jobs:
        h = cortex_svc.make_job_hash(
            job.get("title", ""), job.get("company", ""), job.get("location", "")
        )
        if h not in seen:
            seen.add(h)
            job["job_hash"] = h
            hashed_jobs.append(job)

    # ── 2. Filter out already known jobs ─────────────────────────────────────
    all_hashes = [j["job_hash"] for j in hashed_jobs]
    async with CortexSessionLocal() as db:
        existing = await cortex_svc.get_existing_hashes(db, all_hashes)
        await cortex_svc.refresh_seen(db, list(existing))

    new_jobs = [j for j in hashed_jobs if j["job_hash"] not in existing]
    logger.info(
        "[cortex_feed] %d jobs from fallback — %d new, %d already in Cortex",
        len(jobs), len(new_jobs), len(existing),
    )
    if not new_jobs:
        return {"new": 0, "stored": 0}

    # ── 3. Enrich seniority ───────────────────────────────────────────────────
    enriched = await enrich_seniority(new_jobs)

    # ── 4. Embed ──────────────────────────────────────────────────────────────
    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    texts = [f"{j.get('title', '')} {j.get('desc', '')}".strip() for j in enriched]
    embeddings = await embedder.aembed_documents(texts)

    # ── 5. Store ──────────────────────────────────────────────────────────────
    stored = 0
    async with CortexSessionLocal() as db:
        for job, emb in zip(enriched, embeddings):
            try:
                await cortex_svc.upsert_job(db, {
                    "job_hash":      job["job_hash"],
                    "title":         job.get("title", ""),
                    "company":       job.get("company", ""),
                    "location":      job.get("location", ""),
                    "description":   job.get("desc", ""),
                    "url":           job.get("url", ""),
                    "source":        job.get("source", ""),
                    "contract_type": job.get("contract_type", ""),
                    "remote":        job.get("remote", False),
                    "seniority":     job.get("seniority", ""),
                    "embedding":     emb,
                })
                stored += 1
            except Exception as exc:
                logger.warning("[cortex_feed] Failed to store '%s': %s", job.get("title"), exc)

    logger.info("[cortex_feed] Stored %d new jobs from fallback into Cortex", stored)
    return {"new": len(new_jobs), "stored": stored}