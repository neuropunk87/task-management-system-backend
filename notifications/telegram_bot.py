import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "task_management_system.settings")
django.setup()

import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters.command import Command
from aiogram.client.default import DefaultBotProperties
from asgiref.sync import sync_to_async
from users.models import CustomUser
from notifications.models import Notification


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN are not set.")

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔔 Enable Notifications"),
             KeyboardButton(text="🔕 Disable Notifications")],
            [KeyboardButton(text="🛠 Help")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(Command("start"))
async def start_handler(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 /start from {user_chat_id}")

    user_exists = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).exists)()
    if user_exists:
        user = await sync_to_async(CustomUser.objects.get)(telegram_id=user_chat_id)
        user.telegram_notifications_enabled = True
        await sync_to_async(user.save)()
        await message.answer(
            "✅ Welcome! Notifications are now enabled. You will receive task updates and deadline reminders.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            "🚀 Welcome! To receive notifications, link your Telegram ID in your profile.",
            reply_markup=main_keyboard(),
        )


@router.message(Command("enable_notifications"))
async def enable_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 Enable notifications for {user_chat_id}")

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first)()
    if user:
        user.telegram_notifications_enabled = True
        await sync_to_async(user.save)()
        await message.answer("✅ Notifications have been enabled. You will now receive updates.")
    else:
        await message.answer("❌ Your Telegram ID is not linked to any user. Please link it in your profile.")

@router.message(lambda message: message.text == "🔔 Enable Notifications")
async def enable_notifications_button(message: types.Message):
    await enable_notifications(message)


@router.message(Command("disable_notifications"))
async def disable_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 Disable notifications for {user_chat_id}")

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first)()
    if user:
        user.telegram_notifications_enabled = False
        await sync_to_async(user.save)()
        await message.answer("🔕 Notifications have been disabled. You will no longer receive updates.")
    else:
        await message.answer("❌ Your Telegram ID is not linked to any user. Please link it in your profile.")

@router.message(lambda message: message.text == "🔕 Disable Notifications")
async def disable_notifications_button(message: types.Message):
    await disable_notifications(message)


@router.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(
        "📌 Available commands:\n"
        "/start - Start bot and enable notifications\n"
        "/enable_notifications - Enable notifications\n"
        "/disable_notifications - Disable notifications\n"
        "/help - Show help information\n"
        "🔹 Use the buttons below for easy navigation.",
        reply_markup=main_keyboard()
    )

@router.message(lambda message: message.text == "🛠 Help")
async def help_button_handler(message: types.Message):
    await help_handler(message)


@router.message()
async def fallback_handler(message: types.Message):
    await message.answer(
        "❌ Unknown command. Use /help or the buttons below.",
        reply_markup=main_keyboard()
    )


async def main():
    dp.include_router(router)
    logger.info("🚀 Bot is running in long polling mode")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
