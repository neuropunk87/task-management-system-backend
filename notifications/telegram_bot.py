import asyncio
import logging
import os
import threading
import sys
from pathlib import Path

if __name__ == "__main__":
    # The unchanged Procfile executes the file directly, not as a Python module.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "task_management_system.settings")
    import django

    django.setup()

from aiogram import Bot, Dispatcher, F, Router, types  # noqa: E402
from aiogram.enums import ChatType
from aiogram.filters.command import Command, CommandObject  # noqa: E402
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup  # noqa: E402
from asgiref.sync import sync_to_async  # noqa: E402
from django.conf import settings  # noqa: E402

from users.models import CustomUser  # noqa: E402
from users.telegram import (  # noqa: E402
    InvalidTelegramLink,
    TelegramChatAlreadyLinked,
    consume_telegram_link,
)


logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)


def is_private_sender(message):
    return (
        message.chat.type == ChatType.PRIVATE
        and message.from_user is not None
        and not message.from_user.is_bot
        and message.from_user.id == message.chat.id
    )


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔔 Enable Notifications"),
                KeyboardButton(text="🔕 Disable Notifications"),
            ],
            [KeyboardButton(text="🛠 Help")],
        ],
        resize_keyboard=True,
    )


@router.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    if not is_private_sender(message):
        return
    chat_id = message.chat.id
    if command.args:
        try:
            await sync_to_async(consume_telegram_link)(command.args, chat_id)
        except InvalidTelegramLink:
            await message.answer(
                "This link is invalid or expired. Generate a new link in your profile."
            )
            return
        except TelegramChatAlreadyLinked:
            await message.answer(
                "This Telegram chat is already linked to another account."
            )
            return
        logger.info("A Telegram account was linked successfully.")
        await message.answer(
            "Your account is linked and notifications are enabled.",
            reply_markup=main_keyboard(),
        )
        return

    user = await sync_to_async(
        CustomUser.objects.filter(
            telegram_id=str(chat_id), is_active=True, telegram_verified_at__isnull=False
        ).first
    )()
    if user:
        await sync_to_async(
            CustomUser.objects.filter(pk=user.pk).update
        )(telegram_notifications_enabled=True)
        await message.answer(
            "Notifications are enabled.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            "Generate a one-time Telegram link in your profile, then open it here.",
            reply_markup=main_keyboard(),
        )


async def _set_notifications(message: types.Message, enabled: bool):
    if not is_private_sender(message):
        return
    updated = await sync_to_async(
        CustomUser.objects.filter(
            telegram_id=str(message.chat.id), is_active=True, telegram_verified_at__isnull=False
        ).update
    )(telegram_notifications_enabled=enabled)
    if not updated:
        await message.answer(
            "Your Telegram chat is not linked. Generate a link in your profile."
        )
        return
    state = "enabled" if enabled else "disabled"
    await message.answer(f"Notifications are {state}.", reply_markup=main_keyboard())


@router.message(Command("enable_notifications"))
async def enable_notifications(message: types.Message):
    await _set_notifications(message, True)


@router.message(lambda message: message.text == "🔔 Enable Notifications")
async def enable_notifications_button(message: types.Message):
    await _set_notifications(message, True)


@router.message(Command("disable_notifications"))
async def disable_notifications(message: types.Message):
    await _set_notifications(message, False)


@router.message(lambda message: message.text == "🔕 Disable Notifications")
async def disable_notifications_button(message: types.Message):
    await _set_notifications(message, False)


@router.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(
        "Available commands:\n"
        "/start - link your account or enable notifications\n"
        "/enable_notifications - enable notifications\n"
        "/disable_notifications - disable notifications\n"
        "/help - show this help",
        reply_markup=main_keyboard(),
    )


@router.message(lambda message: message.text == "🛠 Help")
async def help_button_handler(message: types.Message):
    await help_handler(message)


@router.message()
async def fallback_handler(message: types.Message):
    await message.answer(
        "Unknown command. Use /help or the buttons below.",
        reply_markup=main_keyboard(),
    )


async def main(shutdown: threading.Event | None = None, ready=None):
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured.")
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    if ready:
        async def on_startup(**kwargs):
            ready()
        dp.startup.register(on_startup)
    logger.info("Telegram bot is running in long-polling mode.")
    polling = asyncio.create_task(dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        handle_signals=shutdown is None,
        close_bot_session=False,
    ))
    try:
        if shutdown is None:
            await polling
        else:
            while not shutdown.is_set():
                if polling.done():
                    await polling
                    return
                await asyncio.sleep(0.25)
    finally:
        polling.cancel()
        await asyncio.gather(polling, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
