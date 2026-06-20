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
    # Full ingestion every night at 2am — all domains, all seed keywords
    "cortex-full-ingestion-nightly": {
        "task": "app.worker.tasks.full_ingestion",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"locations": None, "domain": None},
    },
    # Cleanup old jobs every Sunday at 3am — deactivate jobs not seen in 30 days
    "cortex-cleanup-weekly": {
        "task": "app.worker.tasks.cleanup_old_jobs",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
        "kwargs": {"days": 30},
    },
}