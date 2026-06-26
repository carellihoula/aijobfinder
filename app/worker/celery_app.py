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
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ── Scheduled tasks (Celery Beat) ─────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # France Travail — every 3 hours (new offers posted continuously throughout the day)
    "ingest-france-travail": {
        "task": "app.worker.tasks.ingest_france_travail",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    # Greenhouse — once daily at 01:15 (ATS boards update infrequently)
    "ingest-greenhouse": {
        "task": "app.worker.tasks.ingest_greenhouse",
        "schedule": crontab(minute=15, hour=1),
    },
    # Lever — once daily at 01:30, offset to avoid overlap with Greenhouse
    "ingest-lever": {
        "task": "app.worker.tasks.ingest_lever",
        "schedule": crontab(minute=30, hour=1),
    },
    # Per-user nightly refresh — at 03:45, after the 03:00 France Travail ingestion finishes
    "refresh-user-analyses-nightly": {
        "task": "app.worker.tasks.refresh_user_analyses",
        "schedule": crontab(hour=3, minute=45),
    },
    # Cleanup old jobs every Sunday at 04:00
    "cortex-cleanup-weekly": {
        "task": "app.worker.tasks.cleanup_old_jobs",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
        "kwargs": {"days": 30},
    },
}