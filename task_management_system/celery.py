import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "task_management_system.settings")

app = Celery("task_management_system")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "retry_notification_outbox": {
        "task": "notifications.tasks.retry_pending_deliveries",
        "schedule": 60.0,
    },
    "prune_expired_refresh_tokens": {
        "task": "users.tasks.prune_expired_tokens",
        "schedule": crontab(hour=0, minute=30),
    },
    "notify_deadlines_every_day": {
        "task": "notifications.utils.notify_deadlines",
        "schedule": crontab(hour=9, minute=0),
    },
    "delete_old_notifications_every_day": {
        "task": "notifications.utils.delete_old_notifications",
        "schedule": crontab(hour=0, minute=0),
    },
}
