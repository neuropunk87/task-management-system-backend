from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Task


User = get_user_model()


@receiver(m2m_changed, sender=Task.assigned_to.through)
def add_assigned_users_to_project_participants(sender, instance, action, pk_set, **kwargs):
    if action != "post_add" or not pk_set:
        return

    project = getattr(instance, "project", None)
    if not project:
        return

    users = User.objects.filter(pk__in=pk_set)
    if users.exists():
        project.participants.add(*users)
