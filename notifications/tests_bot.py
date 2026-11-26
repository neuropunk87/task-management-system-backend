"""Bot handlers are tested without contacting Telegram or using real tokens."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from notifications import telegram_bot
from users.models import CustomUser
from users.telegram import issue_telegram_link


class TelegramHandlerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user("bot-user", "bot@example.com", "password")
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=555, type="private"),
            from_user=SimpleNamespace(id=555, is_bot=False),
            answer=AsyncMock(),
        )

    def test_start_links_only_a_proven_private_sender(self):
        token, _ = issue_telegram_link(self.user)
        async_to_sync(telegram_bot.start_handler)(self.message, SimpleNamespace(args=token))
        self.user.refresh_from_db()
        self.assertEqual(self.user.telegram_id, "555")
        self.assertIsNotNone(self.user.telegram_verified_at)
        self.assertTrue(self.user.telegram_notifications_enabled)

    def test_invalid_link_has_a_safe_user_message(self):
        async_to_sync(telegram_bot.start_handler)(self.message, SimpleNamespace(args="invalid"))
        self.assertIn("invalid or expired", self.message.answer.call_args.args[0])

    def test_group_sender_does_not_consume_a_code(self):
        token, _ = issue_telegram_link(self.user)
        self.message.chat.type = "group"
        self.message.chat.id = -100123
        async_to_sync(telegram_bot.start_handler)(self.message, SimpleNamespace(args=token))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.telegram_id)
        self.message.answer.assert_not_called()

    def test_unverified_historical_chat_cannot_enable_notifications(self):
        self.user.telegram_id = "555"
        self.user.save()
        async_to_sync(telegram_bot.start_handler)(self.message, SimpleNamespace(args=None))
        self.user.refresh_from_db()
        self.assertFalse(self.user.telegram_notifications_enabled)

    def test_verified_chat_can_toggle_notifications_but_inactive_user_cannot(self):
        self.user.telegram_id = "555"
        self.user.telegram_verified_at = timezone.now()
        self.user.save()
        async_to_sync(telegram_bot.enable_notifications)(self.message)
        self.user.refresh_from_db()
        self.assertTrue(self.user.telegram_notifications_enabled)
        async_to_sync(telegram_bot.disable_notifications)(self.message)
        self.user.refresh_from_db()
        self.assertFalse(self.user.telegram_notifications_enabled)
        self.user.is_active = False
        self.user.save()
        async_to_sync(telegram_bot.enable_notifications)(self.message)
        self.user.refresh_from_db()
        self.assertFalse(self.user.telegram_notifications_enabled)

    @override_settings(TELEGRAM_BOT_TOKEN="test-only-token")
    def test_polling_uses_dispatcher_signals_and_closes_the_session(self):
        bot = MagicMock()
        bot.session.close = AsyncMock()
        dispatcher = MagicMock()
        dispatcher.start_polling = AsyncMock(return_value=None)
        with patch.object(telegram_bot, "Bot", return_value=bot), patch.object(telegram_bot, "Dispatcher", return_value=dispatcher):
            async_to_sync(telegram_bot.main)()
        self.assertTrue(dispatcher.start_polling.call_args.kwargs["handle_signals"])
        bot.session.close.assert_awaited_once()

    @override_settings(TELEGRAM_BOT_TOKEN="test-only-token")
    def test_polling_shutdown_is_bounded_and_session_is_closed(self):
        bot = MagicMock()
        bot.session.close = AsyncMock()
        dispatcher = MagicMock()
        shutdown = threading.Event()

        async def poll(*args, **kwargs):
            shutdown.set()
            await asyncio.sleep(10)

        dispatcher.start_polling = AsyncMock(side_effect=poll)
        with patch.object(telegram_bot, "Bot", return_value=bot), patch.object(telegram_bot, "Dispatcher", return_value=dispatcher):
            async_to_sync(telegram_bot.main)(shutdown=shutdown)
        bot.session.close.assert_awaited_once()
