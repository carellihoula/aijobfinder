import asyncio

from langchain_openai import OpenAIEmbeddings

from app.config import settings
from app.cortex import service as cortex_svc
from app.cortex.db import CortexSessionLocal
from app.cortex.enricher import enrich_seniority
from app.cortex.providers.base import JobProvider, RawJob
from app.logger import get_logger

logger = get_logger(__name__)


def _make_hash(job: RawJob) -> str:
    return cortex_svc.make_job_hash(job.title, job.company, job.location)


async def run_provider_ingestion(provider: JobProvider) -> dict:
    """
    Full ingestion pipeline for a single provider:
      1. Fetch raw jobs
      2. Deduplicate in memory (external_id + title/company/location hash)
      3. Skip jobs already in Cortex (refresh last_seen only)
      4. Enrich seniority via LLM
      5. Embed
      6. Store in Cortex

    Called by individual Celery tasks (ingest_france_travail, ingest_greenhouse, ingest_lever).
    """
    if CortexSessionLocal is None:
        logger.error("[ingestion] CORTEX_DATABASE_URL not configured")
        return {"fetched": 0, "new": 0, "stored": 0}

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    logger.info("[ingestion:%s] Fetching jobs ...", provider.name)
    raw_jobs: list[RawJob] = await provider.fetch_jobs()
    logger.info("[ingestion:%s] Fetched %d raw jobs", provider.name, len(raw_jobs))

    if not raw_jobs:
        return {"fetched": 0, "new": 0, "stored": 0}

    # ── 2. Deduplicate in memory ──────────────────────────────────────────────
    seen_ids:    set[str] = set()
    seen_hashes: set[str] = set()
    unique: list[tuple[RawJob, str]] = []  # (job, hash)

    for job in raw_jobs:
        h = _make_hash(job)
        ext_key = f"{provider.name}:{job.external_id}" if job.external_id else None

        if (ext_key and ext_key in seen_ids) or h in seen_hashes:
            continue

        if ext_key:
            seen_ids.add(ext_key)
        seen_hashes.add(h)
        unique.append((job, h))

    logger.info("[ingestion:%s] %d unique jobs after in-memory dedup", provider.name, len(unique))

    # ── 3. Check DB ───────────────────────────────────────────────────────────
    all_hashes = [h for _, h in unique]
    async with CortexSessionLocal() as db:
        existing = await cortex_svc.get_existing_hashes(db, all_hashes)
        await cortex_svc.refresh_seen(db, list(existing))

    new_pairs = [(job, h) for job, h in unique if h not in existing]
    logger.info(
        "[ingestion:%s] %d new jobs (%d already in Cortex)",
        provider.name, len(new_pairs), len(existing),
    )
    if not new_pairs:
        return {"fetched": len(raw_jobs), "new": 0, "stored": 0}

    # ── 4. Enrich seniority ───────────────────────────────────────────────────
    jobs_dict = [
        {
            "title":         job.title,
            "company":       job.company,
            "location":      job.location,
            "desc":          job.description,
            "url":           job.url,
            "contract_type": job.contract_type,
            "remote":        job.remote,
            "source":        job.source,
            "job_hash":      h,
        }
        for job, h in new_pairs
    ]
    enriched = await enrich_seniority(jobs_dict)

    # ── 5. Embed ──────────────────────────────────────────────────────────────
    logger.info("[ingestion:%s] Embedding %d jobs ...", provider.name, len(enriched))
    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    texts = [f"{j['title']} {j['desc']}".strip() for j in enriched]
    embeddings = await embedder.aembed_documents(texts)

    # ── 6. Store ──────────────────────────────────────────────────────────────
    stored = 0
    async with CortexSessionLocal() as db:
        for job_d, emb in zip(enriched, embeddings):
            try:
                await cortex_svc.upsert_job(db, {
                    "job_hash":      job_d["job_hash"],
                    "title":         job_d["title"],
                    "company":       job_d["company"],
                    "location":      job_d["location"],
                    "description":   job_d["desc"],
                    "url":           job_d["url"],
                    "source":        job_d["source"],
                    "contract_type": job_d["contract_type"],
                    "remote":        job_d["remote"],
                    "seniority":     job_d.get("seniority", ""),
                    "embedding":     emb,
                })
                stored += 1
            except Exception as exc:
                logger.warning("[ingestion:%s] Failed to store '%s': %s", provider.name, job_d["title"], exc)

    logger.info(
        "[ingestion:%s] Done - fetched=%d, unique=%d, new=%d, stored=%d",
        provider.name, len(raw_jobs), len(unique), len(new_pairs), stored,
    )
    if stored > 0:
        from app.cortex.registry import set_cortex_updated_at
        await set_cortex_updated_at()

    return {"fetched": len(raw_jobs), "new": len(new_pairs), "stored": stored}


async def run_all_providers() -> dict:
    """Run all providers sequentially. Called by the nightly full_ingestion task."""
    from app.cortex.providers.france_travail import FranceTravailProvider
    from app.cortex.providers.greenhouse import GreenhouseProvider
    from app.cortex.providers.lever import LeverProvider

    providers: list[JobProvider] = [
        FranceTravailProvider(),
        GreenhouseProvider(),
        LeverProvider(),
    ]

    totals: dict = {"fetched": 0, "new": 0, "stored": 0}
    for provider in providers:
        try:
            result = await run_provider_ingestion(provider)
            for k in totals:
                totals[k] += result.get(k, 0)
        except Exception as exc:
            logger.error("[ingestion] Provider %s crashed: %s", provider.name, exc, exc_info=True)

    logger.info("[ingestion] All providers done - %s", totals)
    return totals
