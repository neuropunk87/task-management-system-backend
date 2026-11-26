import logging
from datetime import timedelta
from smtplib import SMTPException

import httpx
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notifications.delivery import queue_delivery, queue_welcome_email, publish_delivery
from notifications.models import Notification, NotificationDelivery
from tasks.models import Task
from users.models import CustomUser


logger = logging.getLogger(__name__)


class TransientNotificationError(Exception):
    """A delivery error that is safe to retry with backoff."""


@transaction.atomic
def requeue_legacy_notification(user, message):
    """Do not let old raw queue payloads bypass the new visibility boundary."""
    notification = Notification.objects.select_for_update().filter(
        user=user, message=message,
    ).first()
    if not notification or not notification.task_id:
        return False
    from tasks.permissions import can_view_task

    if not can_view_task(user, notification.task):
        return False
    # Reconstruct the payload from its stored context, not an arbitrary subject
    # from the old queue. Outbox rechecks visibility immediately before sending.
    queue_delivery(user, "Task notification", notification.message, notification=notification)
    return True


@shared_task(
    name="notifications.utils.send_email_notification",
    bind=True,
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_email_notification(self, user_email, subject, message):
    user = CustomUser.objects.filter(email__iexact=user_email, is_active=True).first()
    if not user:
        return False
    return requeue_legacy_notification(user, message)


def send_message_sync(telegram_id, message):
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram delivery skipped because the bot token is not configured.")
        return False

    url = (
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    )
    data = {
        "chat_id": str(telegram_id),
        "text": message[:4000],
        "disable_web_page_preview": True,
    }
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(url, json=data)
    except httpx.RequestError as exc:
        raise TransientNotificationError("Telegram request failed.") from exc

    if response.status_code == 429 or response.status_code >= 500:
        raise TransientNotificationError(
            f"Telegram returned a transient HTTP {response.status_code}."
        )
    if response.is_error:
        logger.warning("Telegram rejected a notification with HTTP %s.", response.status_code)
        return False
    return True


@shared_task(
    name="notifications.utils.send_telegram_notification",
    bind=True,
    autoretry_for=(TransientNotificationError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_telegram_notification(self, telegram_id, message):
    user = CustomUser.objects.filter(
        telegram_id=str(telegram_id), is_active=True, telegram_notifications_enabled=True,
        telegram_verified_at__isnull=False,
    ).first()
    if not user:
        return False
    return requeue_legacy_notification(user, message)


@shared_task(name="notifications.utils.send_welcome_email")
def send_welcome_email(user_id):
    user = CustomUser.objects.filter(pk=user_id, is_active=True).first()
    if not user or not user.email:
        return False
    queue_welcome_email(user)
    return True


@shared_task(name="notifications.utils.notify_deadlines")
def notify_deadlines():
    now = timezone.now()
    deadline_threshold = now + timedelta(days=1)
    tasks = Task.objects.filter(
        deadline__range=(now, deadline_threshold),
        status__in=(Task.Status.PENDING, Task.Status.IN_PROGRESS),
    ).prefetch_related("assigned_to")

    created = 0
    for task in tasks:
        subject = f"Task deadline reminder: {task.title}"
        message = f"Reminder: the deadline for '{task.title}' is {task.deadline}."
        deadline_marker = task.deadline.isoformat()
        for user in task.assigned_to.filter(is_active=True):
            with transaction.atomic():
                notification, was_created = Notification.objects.get_or_create(
                    dedupe_key=f"deadline:{task.pk}:{user.pk}:{deadline_marker}",
                    defaults={"user": user, "task": task, "message": message},
                )
                if was_created:
                    created += 1
                queue_delivery(user, subject, message, notification=notification)
    return created


@shared_task(name="notifications.utils.delete_old_notifications")
def delete_old_notifications(days=30):
    days = max(1, min(int(days), 3650))
    cutoff_date = timezone.now() - timedelta(days=days)
    deleted_count, _ = Notification.objects.filter(created_at__lt=cutoff_date).delete()
    # Welcome messages have no Notification parent, so cascading the parent
    # cleanup alone would retain recipient details and message bodies forever.
    terminal_count, _ = NotificationDelivery.objects.filter(
        notification__isnull=True,
        created_at__lt=cutoff_date,
        status__in=(
            NotificationDelivery.Status.SENT,
            NotificationDelivery.Status.CANCELLED,
            NotificationDelivery.Status.FAILED,
        ),
    ).delete()
    return deleted_count + terminal_count


@shared_task
def deliver_notification(delivery_id):
    now = timezone.now()
    with transaction.atomic():
        delivery = NotificationDelivery.objects.select_for_update().filter(pk=delivery_id).first()
        if not delivery or delivery.status in {
            NotificationDelivery.Status.SENT, NotificationDelivery.Status.CANCELLED,
            NotificationDelivery.Status.FAILED,
        }:
            return False
        if delivery.available_at > now or (
            delivery.status == NotificationDelivery.Status.SENDING
            and delivery.lease_until and delivery.lease_until > now
        ):
            return False
        if delivery.attempts >= 8:
            delivery.status = NotificationDelivery.Status.FAILED
            delivery.lease_until = None
            delivery.save(update_fields=["status", "lease_until"])
            return False
        delivery.status = NotificationDelivery.Status.SENDING
        delivery.attempts += 1
        delivery.lease_until = now + timedelta(minutes=5)
        delivery.save(update_fields=["status", "attempts", "lease_until"])

    # Never send to a stale/unlinked chat or a deactivated account.
    user = CustomUser.objects.filter(pk=delivery.user_id, is_active=True).first()
    allowed = bool(user)
    if allowed and delivery.channel == NotificationDelivery.Channel.TELEGRAM:
        allowed = bool(user.telegram_verified_at) and user.telegram_notifications_enabled and user.telegram_id == delivery.destination
    elif allowed:
        allowed = user.email == delivery.destination
    if allowed and delivery.notification_id:
        task = delivery.notification.task
        if task is None:
            allowed = False
        else:
            from tasks.permissions import can_view_task
            allowed = can_view_task(user, task)
    if not allowed:
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            status=NotificationDelivery.Status.CANCELLED, lease_until=None
        )
        return False

    try:
        if delivery.channel == NotificationDelivery.Channel.EMAIL:
            sent = send_mail(
                delivery.subject, delivery.message, settings.DEFAULT_FROM_EMAIL,
                [delivery.destination], fail_silently=False,
            )
            if not sent:
                raise TransientNotificationError("Email was not sent.")
        else:
            sent = send_message_sync(delivery.destination, delivery.message)
    except (SMTPException, OSError, TransientNotificationError):
        status = (
            NotificationDelivery.Status.FAILED if delivery.attempts >= 8
            else NotificationDelivery.Status.PENDING
        )
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            status=status, lease_until=None,
            available_at=timezone.now() + timedelta(seconds=min(60 * 2 ** delivery.attempts, 3600)),
        )
        logger.warning("Delivery %s failed; credentials and recipient details are omitted.", delivery.pk)
        return False
    NotificationDelivery.objects.filter(pk=delivery.pk).update(
        status=NotificationDelivery.Status.SENT if sent else NotificationDelivery.Status.CANCELLED,
        sent_at=timezone.now() if sent else None, lease_until=None,
    )
    return bool(sent)


@shared_task
def retry_pending_deliveries():
    now = timezone.now()
    pending = NotificationDelivery.objects.filter(
        Q(status=NotificationDelivery.Status.PENDING, available_at__lte=now)
        | Q(status=NotificationDelivery.Status.SENDING, lease_until__lte=now)
    ).order_by("available_at").values_list("pk", flat=True)[:100]
    published = 0
    for delivery_id in pending:
        if not publish_delivery(delivery_id):
            break
        published += 1
    return published
