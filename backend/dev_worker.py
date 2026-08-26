"""
Dev-only script — run Cortex tasks directly without Celery or Redis.

Usage:
    python dev_worker.py feed       # ingest jobs from fallback already in state
    python dev_worker.py ingest     # full ingestion from seed keywords
    python dev_worker.py cleanup    # deactivate jobs older than 30 days
    python dev_worker.py stats      # print Cortex job count

Not wired into the app. Kill with Ctrl-C.
"""
import asyncio
import sys

from app.cortex.ingestion import run_full_ingestion


async def cmd_ingest():
    # from app.cortex.service import run_full_ingestion
    print("Running full Cortex ingestion (all seed keywords)...")
    await run_full_ingestion()
    print("Done.")


async def cmd_cleanup():
    from app.cortex.db import CortexSessionLocal
    from app.cortex.service import deactivate_old_jobs, purge_inactive_jobs
    async with CortexSessionLocal() as db:
        deactivated = await deactivate_old_jobs(db, days=30)
    async with CortexSessionLocal() as db:
        purged = await purge_inactive_jobs(db, days=90)
    print(f"Deactivated {deactivated} jobs (inactive 30d), purged {purged} rows (inactive 90d).")


async def cmd_stats():
    from app.cortex.db import CortexSessionLocal
    from sqlalchemy import text
    if CortexSessionLocal is None:
        print("CORTEX_DATABASE_URL not set.")
        return
    async with CortexSessionLocal() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM cortex_jobs WHERE is_active = true"))
        count = result.scalar()
    print(f"Active Cortex jobs: {count}")


async def cmd_feed():
    """Re-enqueue the last fallback jobs that are sitting in Redis (manual trigger)."""
    print("Triggering feed via Celery task (Redis required)...")
    from app.worker.tasks import full_ingestion
    full_ingestion.apply()  # run synchronously in-process, no worker needed
    print("Done.")


COMMANDS = {
    "ingest":  cmd_ingest,
    "cleanup": cmd_cleanup,
    "stats":   cmd_stats,
    "feed":    cmd_feed,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    asyncio.run(COMMANDS[cmd]())