import logging
import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase, override_settings
from rest_framework.throttling import AnonRateThrottle

from task_management_system.middleware import GetRemoteAddrMiddleware
from task_management_system.logging import RedactingFormatter


class ProxyHeaderSecurityTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GetRemoteAddrMiddleware(lambda request: request)

    @override_settings(TRUST_X_FORWARDED_FOR=False, TRUSTED_PROXY_COUNT=1)
    def test_spoofed_forwarded_header_is_ignored_by_default(self):
        request = self.factory.get(
            "/",
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="1.2.3.4",
        )
        result = self.middleware(request)
        self.assertEqual(result.META["REMOTE_ADDR"], "10.0.0.10")

    @override_settings(
        TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_COUNT=1,
        TRUSTED_PROXY_IPS=["10.0.0.0/8"],
    )
    def test_trusted_proxy_uses_rightmost_appended_address(self):
        request = self.factory.get(
            "/",
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="1.1.1.1, 203.0.113.8",
        )
        result = self.middleware(request)
        self.assertEqual(result.META["REMOTE_ADDR"], "203.0.113.8")

    def test_drf_throttling_cannot_be_bypassed_by_changing_forwarded_ip(self):
        identities = []
        for fake in ("1.1.1.1", "2.2.2.2"):
            request = self.factory.get("/", REMOTE_ADDR="203.0.113.10", HTTP_X_FORWARDED_FOR=fake)
            self.middleware(request)
            identities.append(AnonRateThrottle().get_ident(request))
            self.assertNotIn("HTTP_X_FORWARDED_FOR", request.META)
        self.assertEqual(identities, ["203.0.113.10", "203.0.113.10"])

    @override_settings(TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_IPS=["10.0.0.0/8"])
    def test_untrusted_peer_cannot_supply_proxy_headers(self):
        request = self.factory.get("/", REMOTE_ADDR="203.0.113.10", HTTP_X_FORWARDED_FOR="1.1.1.1", HTTP_X_FORWARDED_PROTO="https")
        self.middleware(request)
        self.assertEqual(request.META["REMOTE_ADDR"], "203.0.113.10")
        self.assertNotIn("HTTP_X_FORWARDED_PROTO", request.META)

    @override_settings(
        TRUST_X_FORWARDED_FOR=True, TRUST_X_FORWARDED_PROTO=True,
        TRUSTED_PROXY_IPS=["10.0.0.0/8"],
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    )
    def test_trusted_proxy_https_and_invalid_ip_are_handled(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.10", HTTP_X_FORWARDED_FOR="invalid", HTTP_X_FORWARDED_PROTO="https")
        self.middleware(request)
        self.assertEqual(request.META["REMOTE_ADDR"], "10.0.0.10")
        self.assertTrue(request.is_secure())


class DeploymentInvariantTests(SimpleTestCase):
    def test_procfile_is_preserved_exactly(self):
        expected = (
            "web: gunicorn task_management_system.wsgi --log-file -\n"
            "worker: celery -A task_management_system worker --loglevel=info -P gevent & "
            "celery -A task_management_system beat --scheduler django_celery_beat.schedulers.DatabaseScheduler "
            "--loglevel=info & exec python notifications/telegram_bot.py\n"
        )
        path = Path(__file__).resolve().parent.parent / "Procfile"
        self.assertEqual(path.read_text(encoding="utf-8").replace("\r\n", "\n"), expected)

    @override_settings(TELEGRAM_BOT_TOKEN="test-sensitive-token")
    def test_logs_redact_telegram_credentials(self):
        record = logging.LogRecord("httpx", logging.ERROR, __file__, 1, "Request failed https://api.telegram.org/bottest-sensitive-token/sendMessage", (), None)
        formatted = RedactingFormatter().format(record)
        self.assertNotIn("test-sensitive-token", formatted)
        self.assertIn("[redacted]", formatted)

    @override_settings(CELERY_BROKER_URL="rediss://audit:password%2Bwith%2Bspaces@localhost:6380/0")
    def test_logs_redact_encoded_and_decoded_connection_credentials(self):
        record = logging.LogRecord(
            "celery", logging.ERROR, __file__, 1,
            "Failed rediss://audit:password%%2Bwith%%2Bspaces@localhost:6380/0: %s; "
            "postgresql://audit:another%%40credential:with:colons@localhost/db",
            ("password+with+spaces",), None,
        )
        formatted = RedactingFormatter().format(record)
        for secret in ("password%2Bwith%2Bspaces", "password+with+spaces", "another%40credential", "with:colons"):
            self.assertNotIn(secret, formatted)
        self.assertIn("[redacted]", formatted)

    def test_django_handlers_cannot_bypass_secret_redaction(self):
        for name in ("django", "django.server"):
            logger = logging.getLogger(name)
            self.assertFalse(logger.propagate)
            self.assertTrue(logger.handlers)
            for handler in logger.handlers:
                self.assertIsInstance(handler.formatter, RedactingFormatter)

    def test_bot_does_not_accept_a_group_or_different_sender(self):
        from types import SimpleNamespace
        from notifications.telegram_bot import is_private_sender

        self.assertFalse(is_private_sender(SimpleNamespace(chat=SimpleNamespace(type="group", id=-100), from_user=SimpleNamespace(id=1, is_bot=False))))
        self.assertFalse(is_private_sender(SimpleNamespace(chat=SimpleNamespace(type="private", id=1), from_user=SimpleNamespace(id=2, is_bot=False))))
        self.assertTrue(is_private_sender(SimpleNamespace(chat=SimpleNamespace(type="private", id=1), from_user=SimpleNamespace(id=1, is_bot=False))))


class ProductionConfigurationTests(SimpleTestCase):
    def load_settings(self, **overrides):
        environment = {
            "DJANGO_ENV": "production",
            "DJANGO_SECRET_KEY": "test-only-production-check-secret-not-for-real-use-123456789",
            "ALLOWED_HOSTS": "example.com",
            "DATABASE_URL": "postgresql://audit:audit@127.0.0.1/audit",
            "REDIS_URL": "rediss://127.0.0.1:6380/0",
        }
        environment.update(overrides)
        path = Path(__file__).resolve().parent / "settings.py"
        # These are configuration-only tests: never read the user's .env or
        # connect to any service, and never mutate the active Django settings.
        with patch.dict(os.environ, environment, clear=True), patch("environ.Env.read_env"):
            return runpy.run_path(str(path))

    def test_heroku_without_ca_keeps_encrypted_connections_compatible(self):
        import ssl

        config = self.load_settings(DYNO="web.1")
        self.assertTrue(config["HEROKU_REDIS_COMPATIBILITY"])
        self.assertTrue(config["CELERY_BROKER_URL"].startswith("rediss://"))
        self.assertEqual(config["CELERY_BROKER_USE_SSL"]["ssl_cert_reqs"], ssl.CERT_NONE)
        self.assertEqual(config["CELERY_REDIS_BACKEND_USE_SSL"]["ssl_cert_reqs"], ssl.CERT_NONE)
        self.assertEqual(config["CACHES"]["default"]["OPTIONS"]["CONNECTION_POOL_KWARGS"]["ssl_cert_reqs"], ssl.CERT_NONE)
        self.assertTrue(config["TRUST_X_FORWARDED_PROTO"])

    def test_heroku_with_explicit_ca_keeps_certificate_verification(self):
        import ssl

        config = self.load_settings(DYNO="worker.1", REDIS_SSL_CA_CERTS="/test-only-ca.pem")
        self.assertFalse(config["HEROKU_REDIS_COMPATIBILITY"])
        self.assertEqual(config["CELERY_BROKER_USE_SSL"]["ssl_cert_reqs"], ssl.CERT_REQUIRED)
        self.assertEqual(config["CELERY_BROKER_USE_SSL"]["ssl_ca_certs"], "/test-only-ca.pem")

    def test_nonheroku_cannot_disable_certificate_verification(self):
        import ssl

        self.assertEqual(self.load_settings()["REDIS_CERT_REQUIREMENTS"], ssl.CERT_REQUIRED)
        for overrides in (
            {"HEROKU_REDIS_COMPATIBILITY": "True"},
            {"REDIS_URL": "rediss://127.0.0.1:6380/0?ssl_cert_reqs=none"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ImproperlyConfigured):
                self.load_settings(**overrides)

    def test_production_rejects_plaintext_redis_even_on_heroku(self):
        with self.assertRaises(ImproperlyConfigured):
            self.load_settings(DYNO="worker.1", REDIS_URL="redis://127.0.0.1:6379/0")

    def test_production_rejects_debug_wildcard_hosts_and_plaintext_database(self):
        for overrides in (
            {"DEBUG": "True"}, {"ALLOWED_HOSTS": "*"}, {"POSTGRES_SSLMODE": "disable"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ImproperlyConfigured):
                self.load_settings(**overrides)

    def test_heroku_inherits_addon_tls_url_for_all_redis_consumers(self):
        config = self.load_settings(
            DYNO="worker.1", REDIS_URL="redis://127.0.0.1:6379/0",
            REDIS_TLS_URL="rediss://provider.example:6380/0",
        )
        for name in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "CELERY_CACHE_BACKEND"):
            self.assertEqual(config[name], "rediss://provider.example:6380/0")


class JSONBodyLimitTests(SimpleTestCase):
    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=32)
    def test_valid_json_is_preserved(self):
        from io import BytesIO
        from task_management_system.parsers import LimitedJSONParser

        self.assertEqual(LimitedJSONParser().parse(BytesIO(b'{"value": "valid"}')), {"value": "valid"})

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=32)
    def test_oversized_stream_is_not_read_or_decoded_in_full(self):
        from io import BytesIO
        from task_management_system.parsers import LimitedJSONParser, PayloadTooLarge

        stream = BytesIO(b" " * 100_000)
        with self.assertRaises(PayloadTooLarge):
            LimitedJSONParser().parse(stream)
        self.assertEqual(stream.tell(), 33)

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=128)
    @patch("users.views.UserRegistrationSerializer")
    def test_api_rejects_oversized_json_before_field_validation(self, serializer):
        from rest_framework.test import APIClient

        response = APIClient().post(
            "/api/users/register/", {"username": "a" * 256}, format="json",
        )
        # Django can reject a known Content-Length before DRF selects a parser;
        # that early guard returns 400, while the parser's own guard returns 413.
        self.assertIn(response.status_code, (400, 413))
        serializer.assert_not_called()
