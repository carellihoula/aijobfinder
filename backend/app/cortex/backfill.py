"""
One-off backfill: re-enrich (skills) and re-embed (embedding_skills,
embedding_context) every active Cortex job that predates the two-vector
schema.

Needed because init_cortex()'s idempotent ADD COLUMN (see cortex/db.py) only
adds the new columns - it doesn't populate them - and the normal ingestion
pipeline only touches genuinely NEW jobs (an already-seen job just gets its
last_seen refreshed, see ingestion.py). Without this, existing rows stay NULL
and are silently excluded from search (WHERE embedding_skills IS NOT NULL)
until they naturally cycle out after 30 days of inactivity.

CLI usage (run once after deploying the two-vector schema):
    python -m app.cortex.backfill
"""
from __future__ import annotations

import asyncio

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import select, update

from app.config import settings
from app.cortex.db import CortexSessionLocal
from app.cortex.enricher import enrich_jobs
from app.cortex.models import CortexJob
from app.logger import get_logger

logger = get_logger(__name__)

BATCH_SIZE = 30


async def run_backfill() -> dict:
    if CortexSessionLocal is None:
        logger.error("[backfill] CORTEX_DATABASE_URL not configured")
        return {"total": 0, "done": 0}

    async with CortexSessionLocal() as db:
        result = await db.execute(
            select(CortexJob).where(
                CortexJob.is_active == True,
                CortexJob.embedding_skills.is_(None),
            )
        )
        stale_jobs = list(result.scalars().all())

    total = len(stale_jobs)
    logger.info("[backfill] %d active jobs need re-embedding", total)
    if not total:
        return {"total": 0, "done": 0}

    embedder = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    done = 0
    for i in range(0, total, BATCH_SIZE):
        batch = stale_jobs[i:i + BATCH_SIZE]
        jobs_dict = [
            {"title": j.title, "company": j.company, "desc": j.description or ""}
            for j in batch
        ]
        enriched = await enrich_jobs(jobs_dict)

        skills_texts = [
            f"{j['title']} " + ", ".join(j.get("skills") or [])
            for j in enriched
        ]
        context_texts = [j["desc"] for j in enriched]
        all_embeddings = await embedder.aembed_documents(skills_texts + context_texts)
        n = len(enriched)
        skills_embeddings = all_embeddings[:n]
        context_embeddings = all_embeddings[n:]

        async with CortexSessionLocal() as db:
            for job, job_d, skills_emb, context_emb in zip(batch, enriched, skills_embeddings, context_embeddings):
                await db.execute(
                    update(CortexJob)
                    .where(CortexJob.id == job.id)
                    .values(
                        seniority=job_d.get("seniority") or job.seniority or "",
                        skills=job_d.get("skills") or [],
                        embedding_skills=skills_emb,
                        embedding_context=context_emb,
                    )
                )
            await db.commit()

        done += len(batch)
        logger.info("[backfill] %d/%d done", done, total)

    return {"total": total, "done": done}


if __name__ == "__main__":
    result = asyncio.run(run_backfill())
    print(f"Backfill done: {result['done']}/{result['total']} jobs re-embedded")