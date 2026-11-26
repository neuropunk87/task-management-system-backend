from datetime import timedelta
from unittest.mock import patch
from smtplib import SMTPException

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.models import Notification, NotificationDelivery
from notifications.delivery import queue_delivery
from notifications.tasks import deliver_notification, notify_deadlines, retry_pending_deliveries, TransientNotificationError
from notifications.tasks import send_message_sync, send_email_notification, send_telegram_notification, delete_old_notifications
from kombu.exceptions import OperationalError
import httpx
from django.test import override_settings
from projects.models import Project
from tasks.models import Task


User = get_user_model()


class NotificationSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("notify", "notify@example.com", "password")
        self.other = User.objects.create_user("other-n", "other-n@example.com", "password")
        self.project = Project.objects.create(name="Notify project", owner=self.user)
        self.task = Task.objects.create(
            project=self.project,
            title="Deadline task",
            deadline=timezone.now() + timedelta(hours=6),
            created_by=self.user,
        )
        self.task.assigned_to.add(self.user)
        self.notification = Notification.objects.create(
            user=self.user,
            task=self.task,
            message="Private notification",
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_notification_collection_is_read_only(self):
        response = self.client_for(self.user).post(
            "/api/notifications/",
            {"message": "forged"},
            format="json",
        )
        self.assertEqual(response.status_code, 405)

    def test_user_cannot_mark_another_users_notification(self):
        response = self.client_for(self.other).post(
            f"/api/notifications/{self.notification.pk}/read/"
        )
        self.assertEqual(response.status_code, 404)

    @patch("notifications.delivery.publish_delivery")
    def test_deadline_reminders_are_idempotent(self, mocked_publish):
        with self.captureOnCommitCallbacks(execute=True):
            notify_deadlines()
            notify_deadlines()
        reminders = Notification.objects.filter(dedupe_key__startswith="deadline:")
        self.assertEqual(reminders.count(), 1)
        self.assertEqual(NotificationDelivery.objects.filter(notification__in=reminders).count(), 1)

    def make_delivery(self, *, telegram=False):
        if telegram:
            self.user.telegram_id = "333"
            self.user.telegram_notifications_enabled = True
            self.user.telegram_verified_at = timezone.now()
            self.user.save()
        queue_delivery(self.user, "Safe subject", "Sensitive message", notification=self.notification)
        channel = NotificationDelivery.Channel.TELEGRAM if telegram else NotificationDelivery.Channel.EMAIL
        return NotificationDelivery.objects.get(notification=self.notification, channel=channel)

    def test_delivery_is_idempotent_when_a_queue_message_is_replayed(self):
        delivery = self.make_delivery()
        self.assertTrue(deliver_notification(delivery.pk))
        self.assertFalse(deliver_notification(delivery.pk))
        self.assertEqual(len(mail.outbox), 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.SENT)

    def test_transaction_rollback_does_not_leave_an_outbox_message(self):
        try:
            with transaction.atomic():
                self.make_delivery()
                raise ValueError("rollback")
        except ValueError:
            pass
        self.assertFalse(NotificationDelivery.objects.filter(notification=self.notification).exists())

    @patch("notifications.tasks.deliver_notification.delay", side_effect=OperationalError("broker offline"))
    def test_broker_failure_preserves_committed_delivery(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            delivery = self.make_delivery()
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.PENDING)
        self.assertGreaterEqual(delay.call_count, 1)
        with patch("notifications.tasks.deliver_notification.delay") as working_broker:
            self.assertGreaterEqual(retry_pending_deliveries(), 1)
            self.assertIn(delivery.pk, [call.args[0] for call in working_broker.call_args_list])

    @patch("notifications.tasks.send_mail", side_effect=SMTPException("delivery failed"))
    def test_failed_email_has_bounded_persistent_retry(self, mocked_send):
        delivery = self.make_delivery()
        self.assertFalse(deliver_notification(delivery.pk))
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.status, NotificationDelivery.Status.PENDING)
        self.assertGreater(delivery.available_at, timezone.now())
        delivery.attempts = 7
        delivery.available_at = timezone.now() - timedelta(seconds=1)
        delivery.save()
        self.assertFalse(deliver_notification(delivery.pk))
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)

    @patch("notifications.tasks.send_message_sync")
    def test_unlink_prevents_queued_telegram_delivery(self, mocked_send):
        delivery = self.make_delivery(telegram=True)
        from users.telegram import unlink_telegram
        unlink_telegram(self.user)
        self.assertFalse(deliver_notification(delivery.pk))
        mocked_send.assert_not_called()
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.CANCELLED)

    def test_deactivation_or_membership_removal_prevents_queued_delivery(self):
        delivery = self.make_delivery()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertFalse(deliver_notification(delivery.pk))
        self.assertEqual(len(mail.outbox), 0)

    def test_historical_unverified_telegram_id_is_never_queued(self):
        self.user.telegram_id = "444"
        self.user.telegram_notifications_enabled = True
        self.user.save()
        self.make_delivery()
        self.assertFalse(NotificationDelivery.objects.filter(user=self.user, channel="telegram").exists())

    def test_reverse_assignment_add_and_clear_are_supported(self):
        self.other.tasks.add(self.task)
        self.assertTrue(Notification.objects.filter(user=self.other, task=self.task).exists())
        self.other.tasks.clear()
        self.assertFalse(self.task.assigned_to.filter(pk=self.other.pk).exists())

    def test_nonpersisted_status_change_does_not_create_history_or_messages(self):
        initial_count = Notification.objects.count()
        self.task.status = Task.Status.COMPLETED
        self.task.description = "Only this field is persisted"
        self.task.save(update_fields=["description"])
        self.assertEqual(Notification.objects.count(), initial_count)

    @override_settings(TELEGRAM_BOT_TOKEN="test-only-token")
    @patch("notifications.tasks.httpx.Client")
    def test_telegram_transport_has_timeouts_and_no_html_mode(self, client_class):
        response = client_class.return_value.__enter__.return_value.post.return_value
        response.status_code = 200
        response.is_error = False
        self.assertTrue(send_message_sync(333, "<b>untrusted text</b>"))
        self.assertEqual(client_class.call_args.kwargs["timeout"], 15)
        payload = client_class.return_value.__enter__.return_value.post.call_args.kwargs["json"]
        self.assertNotIn("parse_mode", payload)
        self.assertTrue(payload["disable_web_page_preview"])

    @override_settings(TELEGRAM_BOT_TOKEN="test-only-token")
    @patch("notifications.tasks.httpx.Client")
    def test_telegram_transient_errors_retry_but_blocked_chats_do_not(self, client_class):
        response = client_class.return_value.__enter__.return_value.post.return_value
        for code in (429, 503):
            response.status_code = code
            with self.assertRaises(TransientNotificationError):
                send_message_sync(333, "message")
        response.status_code = 403
        response.is_error = True
        self.assertFalse(send_message_sync(333, "message"))
        client_class.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError("connection failed")
        with self.assertRaises(TransientNotificationError):
            send_message_sync(333, "message")

    @patch("notifications.tasks.send_message_sync")
    def test_legacy_task_cannot_send_to_an_unverified_chat(self, send):
        self.user.telegram_id = "333"
        self.user.telegram_notifications_enabled = True
        self.user.save()
        self.assertFalse(send_telegram_notification("333", "message"))
        send.assert_not_called()

    @patch("notifications.tasks.send_mail")
    def test_legacy_email_without_notification_context_is_cancelled(self, send):
        self.assertFalse(send_email_notification(self.user.email, "Private subject", "Unknown context"))
        send.assert_not_called()

    def test_legacy_deliveries_are_deduplicated_and_requeued_with_context(self):
        self.user.telegram_id = "333"
        self.user.telegram_verified_at = timezone.now()
        self.user.telegram_notifications_enabled = True
        self.user.save()
        self.assertTrue(send_email_notification(self.user.email, "Untrusted old subject", self.notification.message))
        self.assertTrue(send_telegram_notification("333", self.notification.message))
        deliveries = NotificationDelivery.objects.filter(notification=self.notification)
        self.assertEqual(deliveries.count(), 2)
        self.assertTrue(all(item.subject == "Task notification" for item in deliveries))
        self.assertTrue(all(item.message == self.notification.message for item in deliveries))
        self.assertEqual(len(mail.outbox), 0)

    def test_legacy_deliveries_cannot_bypass_task_access(self):
        self.user.telegram_id = "333"
        self.user.telegram_verified_at = timezone.now()
        self.user.telegram_notifications_enabled = True
        self.user.save()
        self.task.assigned_to.clear()
        self.project.owner = self.other
        self.project.save(update_fields=["owner"])
        self.assertFalse(send_email_notification(self.user.email, "Private subject", self.notification.message))
        self.assertFalse(send_telegram_notification("333", self.notification.message))
        self.assertFalse(NotificationDelivery.objects.filter(notification=self.notification).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_active_delivery_lease_prevents_parallel_duplicate(self):
        delivery = self.make_delivery()
        delivery.status = NotificationDelivery.Status.SENDING
        delivery.lease_until = timezone.now() + timedelta(minutes=5)
        delivery.save()
        self.assertFalse(deliver_notification(delivery.pk))
        self.assertEqual(len(mail.outbox), 0)
        delivery.lease_until = timezone.now() - timedelta(seconds=1)
        delivery.save()
        self.assertTrue(deliver_notification(delivery.pk))
        self.assertEqual(len(mail.outbox), 1)

    def test_notification_mark_read_does_not_change_creation_timestamp(self):
        timestamp = self.notification.created_at
        response = self.client_for(self.user).post(f"/api/notifications/{self.notification.pk}/read/")
        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertEqual(self.notification.created_at, timestamp)

    def test_old_notifications_cleanup_preserves_recent_records(self):
        Notification.objects.filter(pk=self.notification.pk).update(created_at=timezone.now() - timedelta(days=40))
        delete_old_notifications()
        self.assertFalse(Notification.objects.filter(pk=self.notification.pk).exists())
        self.assertTrue(Notification.objects.filter(task=self.task).exists())

    def test_cleanup_prunes_terminal_welcome_deliveries_but_keeps_pending(self):
        deliveries = []
        for status in (
            NotificationDelivery.Status.SENT,
            NotificationDelivery.Status.CANCELLED,
            NotificationDelivery.Status.FAILED,
            NotificationDelivery.Status.PENDING,
        ):
            delivery = NotificationDelivery.objects.create(
                user=self.user, dedupe_key=f"old-welcome:{status}", channel="email",
                destination=self.user.email, subject="Welcome", message="Private",
                status=status,
            )
            deliveries.append(delivery)
        NotificationDelivery.objects.filter(pk__in=[item.pk for item in deliveries]).update(
            created_at=timezone.now() - timedelta(days=40),
        )
        recent = NotificationDelivery.objects.create(
            user=self.user, dedupe_key="recent-welcome", channel="email",
            destination=self.user.email, subject="Welcome", message="Private", status="sent",
        )
        delete_old_notifications()
        self.assertFalse(NotificationDelivery.objects.filter(pk__in=[item.pk for item in deliveries[:3]]).exists())
        self.assertTrue(NotificationDelivery.objects.filter(pk=deliveries[3].pk).exists())
        self.assertTrue(NotificationDelivery.objects.filter(pk=recent.pk).exists())

    def test_repeated_crashes_cannot_exceed_delivery_attempt_limit(self):
        delivery = self.make_delivery()
        delivery.status = NotificationDelivery.Status.SENDING
        delivery.attempts = 8
        delivery.lease_until = timezone.now() - timedelta(seconds=1)
        delivery.save()
        self.assertFalse(deliver_notification(delivery.pk))
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.Status.FAILED)
        self.assertEqual(delivery.attempts, 8)
        self.assertEqual(len(mail.outbox), 0)
