from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from notifications.models import Notification
from notifications.delivery import queue_delivery
from tasks.models import Task, TaskHistory


TRACKED_TASK_FIELDS = ("status", "priority", "deadline")


def _record_assignment(task, user, added):
    action = "assigned to" if added else "removed from"
    subject = f"Task assignment changed: {task.title}"
    message = f"You were {action} the task '{task.title}'."
    notification = Notification.objects.create(user=user, task=task, message=message)
    TaskHistory.objects.create(
        task=task,
        modified_by=task.modified_by,
        field_changed="assigned_to",
        old_value="" if added else user.username,
        new_value=user.username if added else "",
    )
    queue_delivery(user, subject, message, notification=notification)


@receiver(m2m_changed, sender=Task.assigned_to.through)
def task_assignment_notification(sender, instance, action, model, pk_set, reverse, **kwargs):
    if action == "pre_clear":
        instance._removed_assignee_ids = list(
            (instance.tasks if reverse else instance.assigned_to).values_list("pk", flat=True)
        )
        return
    if action not in {"post_add", "post_remove", "post_clear"}:
        return

    related_ids = pk_set or getattr(instance, "_removed_assignee_ids", [])
    added = action == "post_add"
    for related in model.objects.filter(pk__in=related_ids):
        task, user = (related, instance) if reverse else (instance, related)
        _record_assignment(task, user, added)
    if hasattr(instance, "_removed_assignee_ids"):
        del instance._removed_assignee_ids


@receiver(pre_save, sender=Task)
def capture_task_changes(sender, instance, **kwargs):
    if kwargs.get("raw") or not instance.pk:
        instance._notification_changes = {}
        return
    old = Task.objects.filter(pk=instance.pk).first()
    if not old:
        instance._notification_changes = {}
        return
    instance._notification_changes = {
        field: (getattr(old, field), getattr(instance, field))
        for field in TRACKED_TASK_FIELDS
        if kwargs.get("update_fields") is None or field in kwargs["update_fields"]
        if getattr(old, field) != getattr(instance, field)
    }


@receiver(post_save, sender=Task)
def task_updated_notification(sender, instance, created, **kwargs):
    changes = getattr(instance, "_notification_changes", {})
    if kwargs.get("raw") or created or not changes:
        return

    for field, (old_value, new_value) in changes.items():
        TaskHistory.objects.create(
            task=instance,
            modified_by=instance.modified_by,
            field_changed=field,
            old_value=str(old_value),
            new_value=str(new_value),
        )

    summary = "; ".join(
        f"{field}: '{old}' -> '{new}'"
        for field, (old, new) in changes.items()
    )
    subject = f"Task updated: {instance.title}"
    message = f"Task '{instance.title}' was updated. {summary}."
    for user in instance.assigned_to.filter(is_active=True):
        notification = Notification.objects.create(user=user, task=instance, message=message)
        queue_delivery(user, subject, message, notification=notification)
