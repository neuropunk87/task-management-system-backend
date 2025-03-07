from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import httpx
from tasks.models import Task
from notifications.models import Notification
import logging


logger = logging.getLogger(__name__)


@shared_task
def send_email_notification(user_email, subject, message):
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
        )
        return "Email sent successfully"
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")
        return f"Error sending email notification: {e}"


def send_message_sync(telegram_id, message):
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": telegram_id, "text": message, "disable_web_page_preview": True}
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(url, json=data)
            logger.info(f"Telegram API response: {response.status_code} - {response.text}")
            response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Telegram API error: {e.response.status_code} - {e.response.text}")
        return f"Error sending Telegram notification: {e.response.text}"
    except httpx.RequestError as e:
        logger.error(f"Request error while sending Telegram notification: {type(e).__name__}: {str(e)}")
        return f"Error sending Telegram notification: {type(e).__name__}: {str(e)}"


@shared_task
def send_telegram_notification(telegram_id, message):
    return send_message_sync(telegram_id, message)


@shared_task
def notify_deadlines():
    now = timezone.now()
    deadline_threshold = now + timedelta(days=1)

    tasks = Task.objects.filter(
        deadline__range=[now, deadline_threshold],
        status__in=["Pending", "In Progress"]
    ).prefetch_related("assigned_to")

    for task in tasks:
        subject = f"Task Deadline Reminder: '{task.title}'"
        message = f"\nReminder:\nDeadline for task '{task.title}' is {task.deadline}."

        for user in task.assigned_to.all():
            Notification.objects.create(user=user, task=task, message=message)
            if user.email:
                send_email_notification.delay(user.email, subject, message)
            if user.telegram_notifications_enabled and user.telegram_id:
                send_telegram_notification.delay(user.telegram_id, message)


@shared_task
def delete_old_notifications(days=30):
    cutoff_date = timezone.now() - timedelta(days=days)
    deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff_date).delete()
    return f"Deleted {deleted_count} old notifications."
