from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "ailfj",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # acknowledge only after task completes (safer)
    worker_prefetch_multiplier=1,  # one task at a time per worker (ingestion is heavy)
)

# ── Scheduled tasks (Celery Beat) ─────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Nightly cron — re-fetches Adzuna for all keywords accumulated from user pipelines.
    # Uses date_posted=3 (last 3 days) to stay efficient. Skips if registry is empty.
    "cortex-full-ingestion-nightly": {
        "task": "app.worker.tasks.full_ingestion",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"locations": None},
    },
    # Per-user nightly refresh — runs after ingestion (2h), checks each stale analysis.
    # Calls LLM only when the Cortex has new jobs not yet seen by this user.
    "refresh-user-analyses-nightly": {
        "task": "app.worker.tasks.refresh_user_analyses",
        "schedule": crontab(hour=3, minute=0),
    },
    # Cleanup old jobs every Sunday at 4am — deactivate jobs not seen in 30 days
    "cortex-cleanup-weekly": {
        "task": "app.worker.tasks.cleanup_old_jobs",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
        "kwargs": {"days": 30},
    },
}