"""Secure Telegram account-linking helpers."""

import hashlib
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from users.models import CustomUser, TelegramLinkToken


class TelegramLinkError(Exception):
    """Base error for a failed Telegram linking attempt."""


class InvalidTelegramLink(TelegramLinkError):
    """The supplied link code is missing, invalid, or expired."""


class TelegramChatAlreadyLinked(TelegramLinkError):
    """The Telegram chat already belongs to another account."""


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@transaction.atomic
def issue_telegram_link(user: CustomUser) -> tuple[str, datetime]:
    """Create a one-time code while storing only its SHA-256 digest."""

    user = CustomUser.objects.select_for_update().get(pk=user.pk, is_active=True)
    raw_token = secrets.token_urlsafe(24)
    expires_at = timezone.now() + timedelta(
        minutes=settings.TELEGRAM_LINK_TOKEN_TTL_MINUTES
    )
    TelegramLinkToken.objects.update_or_create(
        user=user,
        defaults={"token_digest": _digest(raw_token), "expires_at": expires_at},
    )
    return raw_token, expires_at


@transaction.atomic
def consume_telegram_link(raw_token: str, telegram_id: int | str) -> CustomUser:
    """Atomically consume a one-time code and attach the proven chat ID."""

    if not raw_token or len(raw_token) > 128:
        raise InvalidTelegramLink

    telegram_id = str(telegram_id)
    if not telegram_id.isascii() or not telegram_id.isdecimal() or not (
        0 < int(telegram_id) <= 9_223_372_036_854_775_807
    ):
        raise InvalidTelegramLink

    try:
        # Lock users first in every issue/consume/unlink path to avoid deadlocks.
        user_id = TelegramLinkToken.objects.values_list("user_id", flat=True).get(
            token_digest=_digest(raw_token)
        )
        user = CustomUser.objects.select_for_update().get(pk=user_id, is_active=True)
        link = TelegramLinkToken.objects.select_for_update().get(
            user=user, token_digest=_digest(raw_token)
        )
    except (TelegramLinkToken.DoesNotExist, CustomUser.DoesNotExist) as exc:
        raise InvalidTelegramLink from exc

    if link.expires_at <= timezone.now():
        raise InvalidTelegramLink

    if (
        CustomUser.objects.filter(telegram_id=telegram_id)
        .exclude(pk=link.user_id)
        .exists()
    ):
        raise TelegramChatAlreadyLinked

    user.telegram_id = telegram_id
    user.telegram_notifications_enabled = True
    user.telegram_verified_at = timezone.now()
    try:
        user.save(update_fields=["telegram_id", "telegram_notifications_enabled", "telegram_verified_at"])
    except IntegrityError as exc:
        raise TelegramChatAlreadyLinked from exc
    link.delete()
    return user


@transaction.atomic
def unlink_telegram(user: CustomUser) -> None:
    user = CustomUser.objects.select_for_update().get(pk=user.pk)
    user.telegram_id = None
    user.telegram_notifications_enabled = False
    user.telegram_verified_at = None
    user.save(update_fields=["telegram_id", "telegram_notifications_enabled", "telegram_verified_at"])
    TelegramLinkToken.objects.filter(user=user).delete()
