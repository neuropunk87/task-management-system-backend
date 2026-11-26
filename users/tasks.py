from celery import shared_task
from django.core.management import call_command
from django.utils import timezone

from users.models import TelegramLinkToken


@shared_task
def prune_expired_tokens():
    call_command("flushexpiredtokens", verbosity=0)
    deleted, _ = TelegramLinkToken.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted
