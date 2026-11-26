from django.db import models
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q

from projects.models import Project
from tasks.models import Task


class ProjectAnalytics(models.Model):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="analytics",
    )
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
        completion_duration = ExpressionWrapper(
            F("completed_at") - F("created_at"),
            output_field=DurationField(),
        )
        summary = self.project.tasks.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status=Task.Status.COMPLETED)),
            in_progress=Count("id", filter=Q(status=Task.Status.IN_PROGRESS)),
            pending=Count("id", filter=Q(status=Task.Status.PENDING)),
            average=Avg(
                completion_duration,
                filter=Q(
                    status=Task.Status.COMPLETED,
                    completed_at__isnull=False,
                ),
            ),
        )
        self.total_tasks = summary["total"]
        self.completed_tasks = summary["completed"]
        self.in_progress_tasks = summary["in_progress"]
        self.pending_tasks = summary["pending"]
        self.average_completion_time = summary["average"]
        self.save(
            update_fields=[
                "total_tasks",
                "completed_tasks",
                "in_progress_tasks",
                "pending_tasks",
                "average_completion_time",
            ]
        )
