"""Transactional outbox helpers; publication is only an optimization, not storage."""

import logging

from django.db import transaction
from kombu.exceptions import OperationalError

from notifications.models import NotificationDelivery


logger = logging.getLogger(__name__)


def publish_delivery(delivery_id):
    from notifications.tasks import deliver_notification

    try:
        deliver_notification.delay(delivery_id)
        return True
    except (OperationalError, OSError, TimeoutError):
        logger.warning("Notification publication deferred; the persisted outbox will retry.")
        return False


def queue_delivery(user, subject, message, *, notification=None, dedupe_key=None):
    if not user.is_active:
        return
    key = dedupe_key or f"notification:{notification.pk}"
    recipients = []
    if user.email:
        recipients.append((NotificationDelivery.Channel.EMAIL, user.email))
    if user.telegram_notifications_enabled and user.telegram_id and user.telegram_verified_at:
        recipients.append((NotificationDelivery.Channel.TELEGRAM, user.telegram_id))
    for channel, destination in recipients:
        delivery, created = NotificationDelivery.objects.get_or_create(
            dedupe_key=f"{key}:{channel}",
            defaults={
                "user": user,
                "notification": notification,
                "channel": channel,
                "destination": destination,
                "subject": subject.replace("\r", " ").replace("\n", " ")[:300],
                "message": message,
            },
        )
        if created:
            transaction.on_commit(lambda pk=delivery.pk: publish_delivery(pk), robust=True)


def queue_welcome_email(user):
    from django.conf import settings

    message = (
        f"Hello, {user.username}!\n\nThank you for registering. "
        "To receive Telegram notifications, open your profile, generate a "
        "one-time Telegram link and follow it.\n\n"
        f"Bot: {settings.TELEGRAM_BOT_USERNAME or 'the configured Telegram bot'}\n"
        "Regards,\nProject Team"
    )
    queue_delivery(user, "Welcome to our project!", message, dedupe_key=f"welcome:{user.pk}")
