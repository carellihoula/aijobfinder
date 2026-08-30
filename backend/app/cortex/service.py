import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cortex.models import CortexJob
from app.cv.vectorize import VECTOR_WEIGHTS
from app.logger import get_logger

logger = get_logger(__name__)


def make_job_hash(title: str, company: str, location: str) -> str:
    key = f"{(title or '').lower().strip()}|{(company or '').lower().strip()}|{(location or '').lower().strip()}"
    return hashlib.sha256(key.encode()).hexdigest()


async def get_existing_hashes(db: AsyncSession, hashes: list[str]) -> set[str]:
    result = await db.execute(
        select(CortexJob.job_hash).where(CortexJob.job_hash.in_(hashes))
    )
    return set(result.scalars().all())


async def upsert_job(db: AsyncSession, job_data: dict) -> None:
    result = await db.execute(
        select(CortexJob).where(CortexJob.job_hash == job_data["job_hash"])
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.last_seen = datetime.now(timezone.utc)
        existing.is_active = True
    else:
        db.add(CortexJob(**job_data))
    await db.commit()


async def refresh_seen(db: AsyncSession, hashes: list[str]) -> None:
    if not hashes:
        return
    await db.execute(
        update(CortexJob)
        .where(CortexJob.job_hash.in_(hashes))
        .values(last_seen=datetime.now(timezone.utc), is_active=True)
    )
    await db.commit()


# VECTOR_WEIGHTS lives in app.cv.vectorize - shared with embeddings_filter.py
# so both fusion implementations (SQL here, sklearn there) never drift apart.

# How many rows the cheap ANN pre-filter (indexed, single vector) pulls in before
# the exact multi-vector fused score is computed on that smaller set. Must stay
# well above the final `limit` so the fused ranking has real candidates to work with.
ANN_PREFILTER_LIMIT = 300


async def search_jobs(
    db: AsyncSession,
    query_vectors: dict,
    limit: int = 100,
    contract_type: str = "",
    remote: bool = False,
    locations: list[str] | None = None,
) -> list[dict]:
    """
    Fused multi-vector similarity search.

    `query_vectors` holds the CV split into separate embeddings:
    - "skills" (required, used as the ANN pre-filter anchor), "summary",
      "education": one embedding vector each (list[float])
    - "experiences": a list of embedding vectors (list[list[float]]), one per
      recent job with a real description - pooled by taking the single closest
      match (MIN distance) rather than averaging, so one strong past experience
      is enough even if the others are unrelated.

    Each job has two vectors of its own (`embedding_skills`: title + LLM-
    extracted skills; `embedding_context`: raw description). Every CV facet is
    compared against BOTH and the closer one wins (LEAST over both), rather
    than hard-mapping a facet to a single "correct" job vector.

    Any CV key can be missing (e.g. no summary on the CV) - its weight is
    simply redistributed across whichever vectors are present.

    Hard filters on explicit user preferences:
    - contract_type: user explicitly chose a contract type
    - remote: user explicitly wants remote
    - locations: ILIKE filter - None means no filter (all France)
    """
    if "skills" not in query_vectors:
        raise ValueError("query_vectors must at least contain 'skills'")

    present_weights = {k: VECTOR_WEIGHTS[k] for k in query_vectors if k in VECTOR_WEIGHTS}
    total_weight = sum(present_weights.values())

    conditions = [
        "is_active = true",
        "embedding_skills IS NOT NULL",
        "embedding_context IS NOT NULL",
    ]
    params: dict = {
        "emb_skills": json.dumps(query_vectors["skills"]),
        "prefilter_limit": max(ANN_PREFILTER_LIMIT, limit),
        "limit": limit,
    }

    if contract_type:
        conditions.append("contract_type = :contract_type")
        params["contract_type"] = contract_type

    if remote:
        conditions.append("remote = true")

    if locations:
        loc_parts = " OR ".join(f"location ILIKE :loc_{i}" for i in range(len(locations)))
        conditions.append(f"({loc_parts})")
        for i, loc in enumerate(locations):
            params[f"loc_{i}"] = f"%{loc}%"

    where_clause = " AND ".join(conditions)

    # Build the fused score expression: a weighted sum of cosine distances
    # (pgvector's `<=>`, lower = closer). Each CV facet is compared against
    # BOTH job vectors (embedding_skills, embedding_context) via LEAST() -
    # "experiences" additionally pools its own multiple vectors the same way,
    # so a facet with k sub-vectors contributes LEAST() over 2*k terms.
    score_terms = []
    for name, weight in present_weights.items():
        normalized_weight = weight / total_weight
        vectors = query_vectors["experiences"] if name == "experiences" else [query_vectors[name]]
        least_parts = []
        for i, vec in enumerate(vectors):
            key = f"emb_{name}_{i}"
            params[key] = json.dumps(vec)
            least_parts.append(f"embedding_skills <=> CAST(:{key} AS vector)")
            least_parts.append(f"embedding_context <=> CAST(:{key} AS vector)")
        score_terms.append(f"{normalized_weight} * LEAST({', '.join(least_parts)})")
    score_expr = " + ".join(score_terms)

    # Stage 1 (candidates): ANN index search on "skills" alone - the only way
    # pgvector's index can be used, since it only accelerates ORDER BY on a
    # single vector. Stage 2: exact fused score, cheap because it only runs on
    # the pre-filtered `prefilter_limit` rows instead of the whole table.
    stmt = text(f"""
        WITH candidates AS (
            SELECT id, title, company, location, description, url,
                   contract_type, remote, seniority, skills, created_at,
                   embedding_skills, embedding_context
            FROM cortex_jobs
            WHERE {where_clause}
            ORDER BY embedding_skills <=> CAST(:emb_skills AS vector)
            LIMIT :prefilter_limit
        )
        SELECT id, title, company, location, description, url,
               contract_type, remote, seniority, skills, created_at,
               ({score_expr}) AS match_distance
        FROM candidates
        ORDER BY match_distance ASC
        LIMIT :limit
    """)

    result = await db.execute(stmt, params)
    return [dict(row) for row in result.mappings()]


async def deactivate_old_jobs(db: AsyncSession, days: int = 30) -> int:
    """Soft-delete: mark jobs not seen in `days` as inactive."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        update(CortexJob)
        .where(CortexJob.last_seen < cutoff)
        .where(CortexJob.is_active == True)
        .values(is_active=False)
    )
    await db.commit()
    return result.rowcount


async def purge_inactive_jobs(db: AsyncSession, days: int = 90) -> int:
    """Hard-delete rows that have been inactive for `days` - frees disk space."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        delete(CortexJob)
        .where(CortexJob.is_active == False)
        .where(CortexJob.last_seen < cutoff)
    )
    await db.commit()
    return result.rowcount


async def get_stats(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count()).select_from(CortexJob))).scalar_one()
    active = (await db.execute(
        select(func.count()).select_from(CortexJob).where(CortexJob.is_active == True)
    )).scalar_one()
    inactive = total - active
    return {"total_jobs": total, "active_jobs": active, "inactive_jobs": inactive}