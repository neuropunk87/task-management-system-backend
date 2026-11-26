"""Removing project membership must also revoke any task-assignee back door."""

from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from projects.models import Project
from tasks.models import Task


@receiver(m2m_changed, sender=Project.participants.through)
def revoke_removed_memberships(sender, instance, action, reverse, pk_set, **kwargs):
    if action == "pre_clear":
        related = instance.projects if reverse else instance.participants
        instance._cleared_membership_ids = list(related.values_list("pk", flat=True))
        return
    if action not in {"post_remove", "post_clear"}:
        return
    related_ids = pk_set or getattr(instance, "_cleared_membership_ids", [])
    projects = Project.objects.filter(pk__in=related_ids) if reverse else [instance]
    for project in projects:
        user_ids = [instance.pk] if reverse else related_ids
        user_ids = [pk for pk in user_ids if pk != project.owner_id]
        for task in Task.objects.filter(project=project, assigned_to__in=user_ids).distinct():
            task.assigned_to.remove(*user_ids)
    if hasattr(instance, "_cleared_membership_ids"):
        del instance._cleared_membership_ids
