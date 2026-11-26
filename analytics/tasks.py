from celery import shared_task
from django.db import IntegrityError, OperationalError

from analytics.models import ProjectAnalytics
from projects.models import Project


@shared_task(
    bind=True,
    autoretry_for=(IntegrityError, OperationalError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def refresh_project_analytics(self, project_id):
    if not Project.objects.filter(pk=project_id).exists():
        return False
    analytics, _ = ProjectAnalytics.objects.get_or_create(project_id=project_id)
    analytics.update_analytics()
    return True
