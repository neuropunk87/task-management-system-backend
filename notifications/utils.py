"""Backward-compatible notification task imports.

Celery tasks live in ``notifications.tasks`` so Django autodiscovery can load them.
The two scheduled task names intentionally retain their historical identifiers.
"""

from notifications.tasks import (
    delete_old_notifications,
    notify_deadlines,
    send_email_notification,
    send_message_sync,
    send_telegram_notification,
)


__all__ = [
    "delete_old_notifications",
    "notify_deadlines",
    "send_email_notification",
    "send_message_sync",
    "send_telegram_notification",
]
