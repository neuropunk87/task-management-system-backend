from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver
from users.models import CustomUser
from tasks.models import Task, TaskHistory
from notifications.models import Notification
from notifications.utils import send_email_notification, send_telegram_notification


@receiver(post_save, sender=CustomUser)
def send_telegram_bot_link(sender, instance, created, **kwargs):
    if created:
        subject = "Welcome to our project!"
        message = f"""\nHello, {instance.username.capitalize()}!\n
Thank you for registering in our project. To receive Telegram notifications, please follow the instructions:
1. Fill in your Telegram ID in your profile on the site.
2. Click on the following link and start chatting with our bot:\n
👉 https://t.me/task_reminder_helper_bot\n
After that, your Telegram will be linked to your account.\n
If you have any questions, please email us!\n
Regards,\nProject Team."""
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [instance.email]
        send_mail(subject, message, from_email, recipient_list)


@receiver(m2m_changed, sender=Task.assigned_to.through)
def task_created_notification(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action == "post_add":
        new_users = model.objects.filter(pk__in=pk_set)
        for user in new_users:
            subject = f"New Task assigned: {instance.title}"
            message = f"""\nHello, {user.username.capitalize()}!\n
You have been assigned a new task:\n
Title: {instance.title}
Description: {instance.description}
Project: {instance.project}
Status: {instance.status}
Priority: {instance.priority}
Deadline: {instance.deadline}\n
Please check your dashboard for more details.\n
Regards,\nProject Team."""
            Notification.objects.create(user=user, task=instance, message=message)
            TaskHistory.objects.create(
                task=instance,
                modified_by=instance.modified_by,
                field_changed="assigned_to",
                old_value="",
                new_value=user.username,
            )
            if user.email:
                send_email_notification.delay(user.email, subject, message)
            if user.telegram_notifications_enabled and user.telegram_id:
                send_telegram_notification.delay(user.telegram_id, message)

    elif action == "post_remove":
        removed_users = model.objects.filter(pk__in=pk_set)
        for user in removed_users:
            subject = f"Task unassigned: {instance.title}"
            message = f"""\nHello, {user.username.capitalize()}!\n
You have been removed from the task:\n
Title: {instance.title}\n
If this was a mistake, please contact the project manager.\n
Regards,\nProject Team."""
            Notification.objects.create(user=user, task=instance, message=message)
            TaskHistory.objects.create(
                task=instance,
                modified_by=instance.modified_by,
                field_changed="assigned_to",
                old_value=user.username,
                new_value="",
            )
            if user.email:
                send_email_notification.delay(user.email, subject, message)
            if user.telegram_notifications_enabled and user.telegram_id:
                send_telegram_notification.delay(user.telegram_id, message)


@receiver(pre_save, sender=Task)
def task_updated_notification(sender, instance, **kwargs):
    if not instance.pk:
        return

    old_instance = Task.objects.get(pk=instance.pk)
    changed_fields = {}

    for field in ['status', 'priority', 'deadline']:
        old_value, new_value = getattr(old_instance, field), getattr(instance, field)
        if old_value != new_value:
            changed_fields[field] = (old_value, new_value)
            TaskHistory.objects.create(
                task=instance,
                modified_by=instance.modified_by,
                field_changed=field,
                old_value=old_value,
                new_value=new_value,
            )
    if changed_fields and instance.assigned_to.exists():
        for user in instance.assigned_to.all():
            subject = f"Task '{instance.title}' updated"
            messages = [f"\nTask '{instance.title}' {field} changed from '{old}' to '{new}'."
                        for field, (old, new) in changed_fields.items()]
            message = f"\nHello, {user.username.capitalize()}!\n" + "\n".join(messages)
            Notification.objects.create(user=user, task=instance, message=message)
            if user.email:
                send_email_notification.delay(user.email, subject, message)
            if user.telegram_notifications_enabled and user.telegram_id:
                send_telegram_notification.delay(user.telegram_id, message)
