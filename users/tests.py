from datetime import timedelta
from io import BytesIO
from unittest import skipUnless
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken
from PIL import Image

from users.models import TelegramLinkToken
from users.telegram import InvalidTelegramLink, TelegramChatAlreadyLinked, consume_telegram_link, issue_telegram_link, unlink_telegram
from notifications.models import NotificationDelivery
from django.utils import timezone


User = get_user_model()


class UserSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="A-strong-password-123!",
            telegram_id="111",
            phone_number="+380000000001",
        )
        self.other = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="A-strong-password-456!",
            telegram_id="222",
            phone_number="+380000000002",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("rest_framework_simplejwt.serializers.authenticate")
    def test_oversized_login_fields_are_rejected_before_authentication(self, authenticate):
        client = APIClient()
        for data in (
            {"username": "a" * 151, "password": "test-only-password"},
            {"username": self.user.username, "password": "a" * 129},
        ):
            with self.subTest(data_length=max(map(len, data.values()))):
                response = client.post(reverse("token-obtain-pair"), data, format="json")
                self.assertEqual(response.status_code, 400)
        authenticate.assert_not_called()

    def test_login_preserves_leading_and_trailing_password_spaces(self):
        password = "  A-long-strong-password-123!  "
        self.user.set_password(password)
        self.user.save(update_fields=["password"])
        response = APIClient().post(
            reverse("token-obtain-pair"),
            {"username": self.user.username, "password": password}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_public_user_endpoints_do_not_expose_private_fields(self):
        response = self.client.get(reverse("user-list"))
        self.assertEqual(response.status_code, 200)
        record = response.data["results"][0]
        for private_field in {
            "email",
            "telegram_id",
            "telegram_notifications_enabled",
            "phone_number",
            "date_of_birth",
        }:
            self.assertNotIn(private_field, record)

        detail = self.client.get(reverse("user-detail", args=[self.other.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn("email", detail.data)
        self.assertNotIn("telegram_id", detail.data)

    def test_profile_cannot_set_unverified_telegram_id(self):
        self.user.telegram_id = None
        self.user.telegram_notifications_enabled = False
        self.user.save()
        response = self.client.patch(
            reverse("user-profile"),
            {"telegram_id": "999", "telegram_notifications_enabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.telegram_id)

    @override_settings(TELEGRAM_BOT_TOKEN="test-only-token")
    def test_reading_telegram_status_preserves_the_code_and_write_quota(self):
        url = reverse("telegram-link")
        self.assertEqual(APIClient().get(url).status_code, 401)
        for _ in range(5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {"verified": False})
        self.assertEqual(self.client.head(url).status_code, 200)
        self.assertEqual(self.client.options(url).status_code, 200)
        self.assertFalse(TelegramLinkToken.objects.filter(user=self.user).exists())

        for _ in range(5):
            issued = self.client.post(url)
            self.assertEqual(issued.status_code, 200)
        limited = self.client.post(url)
        self.assertEqual(limited.status_code, 429)
        self.assertIn("Retry-After", limited)

        self.assertEqual(self.client.get(url).status_code, 200)
        consume_telegram_link(issued.data["start_parameter"], "333")
        self.user.refresh_from_db()
        self.assertEqual(self.client.get(url).data, {"verified": True})

    def test_one_time_telegram_link_is_hashed_and_consumed(self):
        raw_token, _ = issue_telegram_link(self.user)
        link = TelegramLinkToken.objects.get(user=self.user)
        self.assertNotEqual(link.token_digest, raw_token)

        linked = consume_telegram_link(raw_token, "333")
        self.assertEqual(linked.telegram_id, "333")
        self.assertFalse(TelegramLinkToken.objects.filter(user=self.user).exists())
        with self.assertRaises(InvalidTelegramLink):
            consume_telegram_link(raw_token, "333")

    def test_logout_rejects_another_users_refresh_token(self):
        refresh = RefreshToken.for_user(self.other)
        response = self.client.post(
            reverse("logout"),
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("traceback", str(response.data).lower())

    def test_password_change_revokes_refresh_tokens(self):
        RefreshToken.for_user(self.user)
        response = self.client.post(
            reverse("change-password"),
            {
                "old_password": "A-strong-password-123!",
                "new_password": "A-new-strong-password-789!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(BlacklistedToken.objects.filter(token__user=self.user).exists())

    @patch("notifications.delivery.publish_delivery")
    def test_registration_schedules_email_after_commit(self, mocked_publish):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("user-registration"),
                {
                    "username": "new-user",
                    "email": "NEW@EXAMPLE.COM",
                    "password": "A-strong-new-password-123!",
                    "password2": "A-strong-new-password-123!",
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        new_user = User.objects.get(username="new-user")
        self.assertEqual(new_user.email, "new@example.com")
        delivery = NotificationDelivery.objects.get(user=new_user)
        mocked_publish.assert_called_once_with(delivery.pk)

    def test_role_and_staff_flags_stay_synchronized(self):
        self.user.role = User.Role.ADMIN
        self.user.save(update_fields=["role"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

        self.user.role = User.Role.EMPLOYEE
        self.user.save(update_fields=["role"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_duplicate_email_with_different_case_is_400(self):
        response = self.client.post(reverse("user-registration"), {
            "username": "new-name", "email": "ALICE@EXAMPLE.COM",
            "password": "A-strong-new-password-123!", "password2": "A-strong-new-password-123!",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_password_validation_uses_username(self):
        response = self.client.post(reverse("user-registration"), {
            "username": "LongUniqueUserName", "email": "unique@example.com",
            "password": "LongUniqueUserName!", "password2": "LongUniqueUserName!",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_password_change_invalidates_existing_access_token(self):
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        self.client.post(reverse("change-password"), {
            "old_password": "A-strong-password-123!", "new_password": "A-new-strong-password-789!",
        }, format="json")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(client.get(reverse("user-profile")).status_code, 401)
        self.assertEqual(APIClient().post(reverse("token-refresh"), {"refresh": str(refresh)}, format="json").status_code, 401)

    def test_admin_password_reset_also_prevents_refresh(self):
        refresh = RefreshToken.for_user(self.user)
        self.user.set_password("Another-admin-reset-password-999!")
        self.user.save(update_fields=["password"])
        response = APIClient().post(reverse("token-refresh"), {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_refresh_rotation_rejects_replay(self):
        refresh = str(RefreshToken.for_user(self.user))
        client = APIClient()
        first = client.post(reverse("token-refresh"), {"refresh": refresh}, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertNotEqual(first.data["refresh"], refresh)
        self.assertEqual(client.post(reverse("token-refresh"), {"refresh": refresh}, format="json").status_code, 401)
        self.assertIn("no-store", first["Cache-Control"])

    def test_deleted_or_inactive_users_cannot_refresh(self):
        refresh = str(RefreshToken.for_user(self.other))
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])
        self.assertEqual(APIClient().post(reverse("token-refresh"), {"refresh": refresh}, format="json").status_code, 401)
        self.other.delete()
        self.assertEqual(APIClient().post(reverse("token-refresh"), {"refresh": refresh}, format="json").status_code, 401)

    def test_telegram_expiry_reissue_and_inactive_account(self):
        old, _ = issue_telegram_link(self.user)
        new, _ = issue_telegram_link(self.user)
        with self.assertRaises(InvalidTelegramLink):
            consume_telegram_link(old, 333)
        TelegramLinkToken.objects.filter(user=self.user).update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(InvalidTelegramLink):
            consume_telegram_link(new, 333)
        new, _ = issue_telegram_link(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        with self.assertRaises(InvalidTelegramLink):
            consume_telegram_link(new, 333)

    def test_group_chat_and_cross_account_link_are_rejected(self):
        token, _ = issue_telegram_link(self.user)
        with self.assertRaises(InvalidTelegramLink):
            consume_telegram_link(token, -100123456789)
        with self.assertRaises(TelegramChatAlreadyLinked):
            consume_telegram_link(token, self.other.telegram_id)
        self.user.refresh_from_db()
        self.assertEqual(self.user.telegram_id, "111")

    def test_unlink_invalidates_outstanding_telegram_token(self):
        token, _ = issue_telegram_link(self.user)
        unlink_telegram(self.user)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.telegram_verified_at)
        self.assertIsNone(self.user.telegram_id)
        with self.assertRaises(InvalidTelegramLink):
            consume_telegram_link(token, 333)

    def test_avatar_is_required_and_non_images_are_rejected(self):
        self.assertEqual(self.client.put(reverse("update-avatar"), {}, format="multipart").status_code, 400)
        upload = SimpleUploadedFile("bad.png", b"<script>alert(1)</script>", content_type="image/png")
        self.assertEqual(self.client.put(reverse("update-avatar"), {"avatar": upload}, format="multipart").status_code, 400)

    def test_avatar_is_reencoded_and_filename_is_not_user_controlled(self):
        original = BytesIO()
        Image.new("RGB", (8, 8), "red").save(original, format="PNG")
        upload = SimpleUploadedFile("attacker.html.png", original.getvalue() + b"<script>payload</script>", content_type="image/png")
        response = self.client.put(reverse("update-avatar"), {"avatar": upload}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.addCleanup(self.user.avatar.delete, save=False)
        self.assertNotIn("attacker", self.user.avatar.name)
        with self.user.avatar.open("rb") as avatar:
            self.assertNotIn(b"payload", avatar.read())

    def test_upload_over_limit_is_stopped_before_save(self):
        upload = SimpleUploadedFile("big.png", b"x" * (2 * 1024 * 1024 + 1), content_type="image/png")
        response = self.client.put(reverse("update-avatar"), {"avatar": upload}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_registration_ignores_privileged_fields(self):
        response = self.client.post(reverse("user-registration"), {
            "username": "not-admin", "email": "not-admin@example.com",
            "password": "A-strong-safe-password-123!", "password2": "A-strong-safe-password-123!",
            "role": "superadmin", "is_superuser": True, "is_staff": True,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="not-admin")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.role, User.Role.EMPLOYEE)

    @override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
    def test_login_lockout_cannot_be_bypassed_with_correct_password(self):
        client = APIClient()
        for _ in range(3):
            client.post(reverse("token-obtain-pair"), {"username": self.user.username, "password": "wrong"}, format="json")
        response = client.post(reverse("token-obtain-pair"), {
            "username": self.user.username, "password": "A-strong-password-123!",
        }, format="json")
        self.assertNotEqual(response.status_code, 200)


class AdminPrivilegeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("limited-admin", "admin@example.com", "password", role=User.Role.ADMIN)
        self.root = User.objects.create_superuser("superuser", "superuser@example.com", "password")
        self.employee = User.objects.create_user("regular", "regular@example.com", "password")
        self.client.force_login(self.admin)

    def test_admin_cannot_reset_superusers_password(self):
        self.assertEqual(self.client.get(f"/secretadmin/users/customuser/{self.root.pk}/password/").status_code, 403)
        self.assertEqual(self.client.post(f"/secretadmin/users/customuser/{self.root.pk}/change/", {"is_superuser": True}).status_code, 403)

    def test_admin_cannot_promote_a_regular_user(self):
        response = self.client.post(f"/secretadmin/users/customuser/{self.employee.pk}/change/", {
            "username": "regular", "email": "regular@example.com", "is_active": "on",
            "role": "superadmin", "is_superuser": "on", "is_staff": "on",
            "date_joined_0": "2026-10-08", "date_joined_1": "12:00:00",
        })
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)
        self.assertFalse(self.employee.is_superuser)
        self.assertFalse(self.employee.is_staff)

    def test_admin_bulk_delete_cannot_delete_privileged_accounts(self):
        response = self.client.post("/secretadmin/users/customuser/", {
            "action": "delete_selected", "_selected_action": [self.root.pk], "post": "yes",
        })
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.root.pk).exists())

    def test_regular_staff_flag_does_not_grant_admin_access(self):
        User.objects.filter(pk=self.employee.pk).update(is_staff=True)
        self.employee.refresh_from_db()
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get("/secretadmin/").status_code, 404)


@skipUnless(connection.vendor == "postgresql", "Row-lock races require PostgreSQL")
class PostgreSQLTokenRaceTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("concurrent", "concurrent@example.com", "Strong-password-for-race-123!")

    def test_one_telegram_code_cannot_be_consumed_twice_concurrently(self):
        token, _ = issue_telegram_link(self.user)
        barrier = Barrier(2)

        def attempt(chat):
            try:
                barrier.wait(timeout=10)
                consume_telegram_link(token, chat)
                return True
            except InvalidTelegramLink:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, (777, 888)))
        self.assertEqual(sorted(results), [False, True])
        self.user.refresh_from_db()
        self.assertIn(self.user.telegram_id, ("777", "888"))

    def test_one_refresh_token_cannot_be_rotated_twice_concurrently(self):
        token = str(RefreshToken.for_user(self.user))
        barrier = Barrier(2)

        def attempt(_):
            try:
                barrier.wait(timeout=10)
                response = APIClient().post(reverse("token-refresh"), {"refresh": token}, format="json")
                return response.status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), [200, 401])


class MigrationSafetyTests(TransactionTestCase):
    def test_legacy_accounts_are_preserved_but_unverified_notifications_are_disabled(self):
        before = ("users", "0002_telegramlinktoken")
        after = ("users", "0003_telegram_verified_at")
        executor = MigrationExecutor(connection)
        executor.migrate([before])
        try:
            legacy_user = executor.loader.project_state([before]).apps.get_model("users", "CustomUser")
            legacy = legacy_user.objects.create(
                username="legacy-chat", email="legacy@example.com", telegram_id="-100999",
                telegram_notifications_enabled=True,
            )
        finally:
            MigrationExecutor(connection).migrate([after])
        updated = User.objects.get(pk=legacy.pk)
        self.assertEqual(updated.email, "legacy@example.com")
        self.assertEqual(updated.telegram_id, "-100999")
        self.assertFalse(updated.telegram_notifications_enabled)
        self.assertIsNone(updated.telegram_verified_at)
