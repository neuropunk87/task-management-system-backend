from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from projects.models import Project
from tasks.models import Task


class ProjectAnalytics(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='analytics')
    total_tasks = models.PositiveIntegerField(default=0)
    completed_tasks = models.PositiveIntegerField(default=0)
    in_progress_tasks = models.PositiveIntegerField(default=0)
    pending_tasks = models.PositiveIntegerField(default=0)
    average_completion_time = models.DurationField(null=True, blank=True)

    class Meta:
        verbose_name = "Project Analytics"
        verbose_name_plural = "Projects Analytics"

    def __str__(self):
        return f"Analytics for {self.project.name}"

    def update_analytics(self):
        tasks = self.project.tasks.all()
        self.total_tasks = tasks.count()
        self.completed_tasks = tasks.filter(status="Completed").count()
        self.in_progress_tasks = tasks.filter(status="In Progress").count()
        self.pending_tasks = tasks.filter(status="Pending").count()
        completed_tasks = tasks.filter(status="Completed", modified_at__isnull=False, created_at__isnull=False)

        if completed_tasks.exists():
            total_time_seconds = sum(
                (task.modified_at - task.created_at).total_seconds()
                for task in completed_tasks
                if task.modified_by and task.created_at
            )
            avg_time_seconds = total_time_seconds / completed_tasks.count()
            self.average_completion_time = timedelta(hours=round(avg_time_seconds / 3600, 2))
        else:
            self.average_completion_time = None

        self.save(update_fields=["total_tasks", "completed_tasks", "in_progress_tasks", "pending_tasks", "average_completion_time"])


@receiver(post_save, sender=Task)
def update_project_analytics_on_task_save(sender, instance, **kwargs):
    if instance.project and hasattr(instance.project, 'analytics'):
        instance.project.analytics.update_analytics()
