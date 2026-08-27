from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "buvoli",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.pregnancy"],
)

celery_app.conf.beat_schedule = {
    "release-recovered-cows": {
        "task": "app.tasks.pregnancy.release_recovered_cows",
        "schedule": crontab(hour=6, minute=0),
    },
}
celery_app.conf.timezone = "Europe/Prague"
