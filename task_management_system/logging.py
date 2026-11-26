"""Redact deployment credentials even when a third-party traceback contains them."""

import logging
import re
from urllib.parse import quote, unquote, urlsplit

from django.conf import settings


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        output = super().format(record)
        for name in ("SECRET_KEY", "TELEGRAM_BOT_TOKEN", "EMAIL_HOST_PASSWORD"):
            secret = getattr(settings, name, "")
            if secret:
                output = output.replace(secret, "[redacted]")
        for name in ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "CELERY_CACHE_BACKEND"):
            password = urlsplit(getattr(settings, name, "")).password
            if password:
                output = output.replace(password, "[redacted]")
                output = output.replace(unquote(password), "[redacted]")
        database_password = settings.DATABASES["default"].get("PASSWORD", "")
        if database_password:
            output = output.replace(database_password, "[redacted]")
            output = output.replace(quote(database_password, safe=""), "[redacted]")
        output = re.sub(
            r"(\b[a-z][a-z0-9+.-]*://[^:/@\s]*:)[^/@\s]+@",
            r"\1[redacted]@", output, flags=re.IGNORECASE,
        )
        return re.sub(r"(https://api\.telegram\.org/bot)[^/\s]+", r"\1[redacted]", output)
