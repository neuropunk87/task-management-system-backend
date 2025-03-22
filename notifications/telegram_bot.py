import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "task_management_system.settings")
django.setup()

import sys
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
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
WEBHOOK_HOST = os.getenv("HEROKU_APP_URL")

if not TELEGRAM_BOT_TOKEN or not WEBHOOK_HOST:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN or WEBHOOK_HOST are not set.")

WEBHOOK_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔔 Enable Notifications"),
             KeyboardButton(text="🔕 Disable Notifications")],
            [KeyboardButton(text="📬 Show List Notifications"),
             KeyboardButton(text="🛠 Help")],
        ],
        resize_keyboard=True
    )


@router.message(CommandStart())
async def start_handler(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 /start from {user_chat_id}")

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first, thread_sensitive=True)()

    if user:
        user.telegram_notifications_enabled = True
        await sync_to_async(user.save, thread_sensitive=True)()
        await message.answer(
            "✅ Welcome! Notifications are now enabled. You will receive task updates and deadline reminders.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            "🚀 Link your Telegram ID in your profile to receive notifications.",
            reply_markup=main_keyboard()
        )


@router.message(Command("enable_notifications"))
@router.message(lambda msg: msg.text == "🔔 Enable Notifications")
async def enable_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 Enable notifications for {user_chat_id}")

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first, thread_sensitive=True)()

    if user:
        user.telegram_notifications_enabled = True
        await sync_to_async(user.save, thread_sensitive=True)()
        await message.answer("✅ Notifications enabled. You will now receive updates.")
    else:
        await message.answer("❌ Link your Telegram ID in your profile.")


@router.message(Command("disable_notifications"))
@router.message(lambda msg: msg.text == "🔕 Disable Notifications")
async def disable_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 Disable notifications for {user_chat_id}")

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first, thread_sensitive=True)()

    if user:
        user.telegram_notifications_enabled = False
        await sync_to_async(user.save, thread_sensitive=True)()
        await message.answer("🔕 Notifications disabled. You will no longer receive updates.")
    else:
        await message.answer("❌ Link your Telegram ID in your profile.")


@router.message(Command("list_notifications"))
@router.message(lambda msg: msg.text == "📬 Show List Notifications")
async def list_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 Request list of notifications for {user_chat_id}")

    try:
        notifications = await sync_to_async(
            lambda: list(Notification.objects.filter(user__telegram_id=user_chat_id, is_read=False).select_related("task")),
            thread_sensitive=True
        )()

        if notifications:
            response = "\n\n".join([f"📬 Task: {n.task.title if n.task else 'No Task'}\n{n.message}" for n in notifications])
        else:
            response = "📭 No unread notifications."

        await message.answer(response)
    except Exception as e:
        logger.error(f"❌ Error fetching notifications: {e}")
        await message.answer("⚠ An error occurred while fetching notifications.")


@router.message(Command("help"))
@router.message(lambda msg: msg.text == "🛠 Help")
async def help_handler(message: types.Message):
    await message.answer(
        "📌 Available commands:\n"
        "/start - Start bot and enable notifications\n"
        "/enable_notifications - Enable notifications\n"
        "/disable_notifications - Disable notifications\n"
        "/list_notifications - Show notifications\n"
        "/help - Show help information\n"
        "🔹 Use the buttons below for easy navigation.",
        reply_markup=main_keyboard()
    )


@router.message()
async def fallback_handler(message: types.Message):
    await message.answer(
        "❌ Unknown command. Use /help or the buttons below.",
        reply_markup=main_keyboard()
    )


async def reset_webhook():
    logger.info("🚀 Resetting webhook...")
    await bot.delete_webhook(drop_pending_updates=True)


async def set_webhook():
    await reset_webhook()
    await bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}")


async def webhook_handler(request):
    body = await request.json()
    logger.info(f"🔍 Received update: {body}")

    try:
        update = types.Update.model_validate(body)
        await dp._process_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return web.Response(status=500)


async def on_startup(app):
    logger.info("🚀 Bot is starting...")
    await set_webhook()


async def on_shutdown(app):
    logger.info("⚠ Shutting down bot...")
    await bot.session.close()


async def main():
    dp.include_router(router)
    app = web.Application()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_post(WEBHOOK_PATH, webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
    await site.start()

    print("Server running... Press Ctrl+C to stop")
    logger.info(f"✅ Bot running with webhook on {WEBHOOK_URL}")

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(main())
