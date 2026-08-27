from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from app.config import settings

celery_app = Celery(
    "ailfj",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"],
)


@worker_process_init.connect
def _register_all_models(**kwargs) -> None:
    """
    Import every SQLAlchemy model once, up front, in every worker process.

    Models reference each other by string name in relationship() - if a task
    queries one model before all the others it relates to have been imported,
    the mapper fails to configure and *every* later query against that model
    in the same process fails too, forever (SQLAlchemy's mapper registry is
    process-global and doesn't retry). Importing everything at process start
    means task import order can never matter.
    """
    from app.applications.models import Application  # noqa: F401
    from app.analysis.models import Analysis  # noqa: F401
    from app.cv.models import CV  # noqa: F401
    from app.users.models import User  # noqa: F401


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
    # France Travail - every 3 hours (new offers posted continuously throughout the day)
    "ingest-france-travail": {
        "task": "app.worker.tasks.ingest_france_travail",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    # Greenhouse - once daily at 01:15 (ATS boards update infrequently)
    "ingest-greenhouse": {
        "task": "app.worker.tasks.ingest_greenhouse",
        "schedule": crontab(minute=15, hour=1),
    },
    # Lever - once daily at 01:30, offset to avoid overlap with Greenhouse
    "ingest-lever": {
        "task": "app.worker.tasks.ingest_lever",
        "schedule": crontab(minute=30, hour=1),
    },
    # JobSpy (Indeed/LinkedIn/Google Jobs) - once daily at 00:15. Real HTTP scraping,
    # much slower than the JSON-API providers above - can take up to ~55 minutes,
    # comfortably finished before Greenhouse/Lever start at 01:15/01:30.
    "ingest-jobspy": {
        "task": "app.worker.tasks.ingest_jobspy",
        "schedule": crontab(minute=15, hour=0),
    },
    # Per-user nightly refresh - at 03:45, after the 03:00 France Travail ingestion finishes
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
    # Reconcile analyses orphaned in "processing" by a killed worker - every 15 min
    "fail-stale-analyses": {
        "task": "app.worker.tasks.fail_stale_analyses",
        "schedule": crontab(minute="*/15"),
        "kwargs": {"older_than_minutes": 30},
    },
    # Reconcile cover letters orphaned in "processing"/"pending" by a killed worker
    "fail-stale-cover-letters": {
        "task": "app.worker.tasks.fail_stale_cover_letters",
        "schedule": crontab(minute="*/15"),
        "kwargs": {"older_than_minutes": 15},
    },
}