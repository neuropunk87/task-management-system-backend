from django.db import models
from django.urls import reverse
from users.models import CustomUser


class Project(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Project name")
    description = models.TextField(blank=True, help_text="Detailed description of the project")
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_projects',
        help_text="The user who owns the project"
    )
    participants = models.ManyToManyField(
        CustomUser,
        related_name='projects',
        help_text="Users who are participants in the project"
    )

    class Status(models.TextChoices):
        ACTIVE = 'active', "Active"
        ARCHIVED = 'archived', "Archived"

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Project status"
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="The date and time when the project was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="The date and time when the project was last updated")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse('project_detail', args=[str(self.id)])

    def is_owner(self, user: CustomUser) -> bool:
        return self.owner == user

    def is_participant(self, user: CustomUser) -> bool:
        return self.participants.filter(id=user.id).exists()
        # return user in self.participants.all()
