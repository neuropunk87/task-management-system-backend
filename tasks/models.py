from django.db import models
from django.urls import reverse
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
    title = models.CharField(max_length=255, unique=True)
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

    class Meta:
        ordering = ['-deadline']
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse('task_detail', args=[str(self.id)])


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
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.author.username if self.author else 'Unknown'} on {self.task.title}"
