import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cortex.models import CortexJob
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


async def search_jobs(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int = 100,
    contract_type: str = "",
    remote: bool = False,
    seniority: str = "",
    locations: list[str] | None = None,
) -> list[dict]:
    """
    Vector similarity search with hard filters on explicit user preferences.
    - contract_type: hard filter (user explicitly chose a contract type)
    - remote: hard filter (user explicitly wants remote)
    - seniority: hard filter (user explicitly chose a level - LLM-tagged at ingestion)
    - locations: ILIKE filter - None means no filter (all France)
    """
    embedding_str = json.dumps(query_embedding)

    conditions = ["is_active = true", "embedding IS NOT NULL"]
    params: dict = {"embedding": embedding_str, "limit": limit}

    if contract_type:
        conditions.append("contract_type = :contract_type")
        params["contract_type"] = contract_type

    if remote:
        conditions.append("remote = true")

    if seniority:
        conditions.append("(seniority = :seniority OR seniority = '')")
        params["seniority"] = seniority

    if locations:
        loc_parts = " OR ".join(f"location ILIKE :loc_{i}" for i in range(len(locations)))
        conditions.append(f"({loc_parts})")
        for i, loc in enumerate(locations):
            params[f"loc_{i}"] = f"%{loc}%"

    where_clause = " AND ".join(conditions)
    stmt = text(f"""
        SELECT id, title, company, location, description, url,
               contract_type, remote, seniority, skills, created_at
        FROM cortex_jobs
        WHERE {where_clause}
        ORDER BY embedding <=> CAST(:embedding AS vector)
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