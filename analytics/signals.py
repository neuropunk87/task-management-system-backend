from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from analytics.tasks import refresh_project_analytics
from tasks.models import Task


@receiver(pre_save, sender=Task)
def capture_previous_project(sender, instance, **kwargs):
    instance._analytics_previous_project_id = None
    if instance.pk:
        instance._analytics_previous_project_id = (
            Task.objects.filter(pk=instance.pk)
            .values_list("project_id", flat=True)
            .first()
        )


def _schedule_refresh(project_ids):
    for project_id in {value for value in project_ids if value}:
        transaction.on_commit(
            lambda project_id=project_id: refresh_project_analytics.delay(project_id),
            robust=True,
        )


@receiver(post_save, sender=Task)
def update_project_analytics(sender, instance, **kwargs):
    _schedule_refresh(
        (instance.project_id, getattr(instance, "_analytics_previous_project_id", None))
    )


@receiver(post_delete, sender=Task)
def update_project_analytics_after_delete(sender, instance, **kwargs):
    _schedule_refresh((instance.project_id,))
