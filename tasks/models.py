from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from dirtyfields import DirtyFieldsMixin
from users.models import CustomUser
from projects.models import Project


class Task(DirtyFieldsMixin, models.Model):
    class Priority(models.TextChoices):
        LOW = 'Low', "Low"
        MEDIUM = 'Medium', "Medium"
        HIGH = 'High', "High"

    class Status(models.TextChoices):
        PENDING = 'Pending', "Pending"
        IN_PROGRESS = 'In Progress', "In Progress"
        COMPLETED = 'Completed', "Completed"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    deadline = models.DateTimeField()
    assigned_to = models.ManyToManyField(
        CustomUser,
        blank=True,
        related_name='tasks',
        help_text="Users assigned to this task"
    )
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    modified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-deadline']
        constraints = [models.UniqueConstraint(fields=["project", "title"], name="task_title_per_project")]
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse('task-detail', args=[str(self.id)])

    @transaction.atomic
    def save(self, *args, **kwargs):
        creating = self._state.adding
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "status" in update_fields:
            if self.status == self.Status.COMPLETED and self.completed_at is None:
                self.completed_at = timezone.now()
            elif self.status != self.Status.COMPLETED:
                self.completed_at = None
        if update_fields:
            update_fields = set(update_fields)
            update_fields.add("modified_at")
            if "status" in update_fields:
                update_fields.add("completed_at")
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)
        if creating and self.status == self.Status.COMPLETED:
            # auto_now_add is evaluated after the initial completion timestamp.
            self.completed_at = self.created_at
            type(self).objects.filter(pk=self.pk).update(completed_at=self.completed_at)


class TaskHistory(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='history')
    modified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    modified_at = models.DateTimeField(auto_now_add=True)
    field_changed = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-modified_at']

    def __str__(self):
        return (f"Task {self.task.id} "
                f"changed by {self.modified_by.username if self.modified_by else 'Unknown'} "
                f"at {self.modified_at}")


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.author.username if self.author else 'Unknown'} on {self.task.title}"
