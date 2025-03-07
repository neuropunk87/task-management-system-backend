from django.db.models.signals import post_save
from django.dispatch import receiver
from tasks.models import Task
from analytics.models import ProjectAnalytics


@receiver(post_save, sender=Task)
def update_project_analytics(sender, instance, **kwargs):
    if instance.project:
        analytics, created = ProjectAnalytics.objects.get_or_create(project=instance.project)
        analytics.update_analytics()
