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
from aiogram.filters import Command
from asgiref.sync import sync_to_async
from users.models import CustomUser
from notifications.models import Notification


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_HOST = os.environ.get("HEROKU_APP_URL")

if not TELEGRAM_BOT_TOKEN or not WEBHOOK_HOST:
    raise ValueError("TELEGRAM_BOT_TOKEN or WEBHOOK_HOST are not set.")

WEBHOOK_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}/"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔔 Enable Notifications"),
             KeyboardButton(text="🔕 Disable Notifications")],
            [KeyboardButton(text="📬 Show List Notifications"),
             KeyboardButton(text="🛠 Help")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


@router.message(Command(commands=["start"]))
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
            "🚀 Welcome! To receive notifications, please link your Telegram ID in your profile.",
            reply_markup=main_keyboard(),
        )


@router.message(Command(commands=["enable_notifications"]))
async def enable_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 /enable_notifications from {user_chat_id}")

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first)()

    if user:
        user.telegram_notifications_enabled = True
        await sync_to_async(user.save)()
        await message.answer("✅ Notifications enabled. You will now receive updates.")
    else:
        await message.answer("❌ Your Telegram ID is not linked to any user. Please link it in your profile.")


@router.message(lambda message: message.text == "🔔 Enable Notifications")
async def enable_notifications_button(message: types.Message):
    await enable_notifications(message)


@router.message(Command(commands=["disable_notifications"]))
async def disable_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 /disable_notifications from {user_chat_id}")

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first)()

    if user:
        user.telegram_notifications_enabled = False
        await sync_to_async(user.save)()
        await message.answer("🔕 Notifications disabled. You will no longer receive updates.")
    else:
        await message.answer("❌ Your Telegram ID is not linked to any user. Please link it in your profile.")


@router.message(lambda message: message.text == "🔕 Disable Notifications")
async def disable_notifications_button(message: types.Message):
    await disable_notifications(message)


@router.message(Command(commands=["list_notifications"]))
async def list_notifications(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 /list_notifications from {user_chat_id}")

    try:
        notifications = await sync_to_async(
            lambda: list(
                Notification.objects.filter(user__telegram_id=user_chat_id, is_read=False)
                .select_related("task")
            ),
            thread_sensitive=True
        )()

        logger.info(f"🔎 Found {len(notifications)} notifications for user {user_chat_id}")

        if notifications:
            response = "\n\n".join(
                [f"📬 Task: {n.task.title if n.task else 'No Task'}\n{n.message}" for n in notifications]
            )
        else:
            response = "📭 No unread notifications."

        await message.answer(response)
        logger.info(f"✅ Sent notifications to {user_chat_id}")

    except Exception as e:
        logger.error(f"❌ Error handling /list_notifications for {user_chat_id}: {e}")
        await message.answer("⚠ An error occurred while fetching notifications.")


@router.message(lambda message: message.text == "📬 Show List Notifications")
async def list_notifications_button(message: types.Message):
    user_chat_id = message.chat.id
    logger.info(f"📩 Button pressed: Show List Notifications by {user_chat_id}")

    await list_notifications(message)


@router.message(Command(commands=["help"]))
async def help_handler(message: types.Message):
    await message.answer(
        "📌 Available commands:\n"
        "/start - Start bot and enable notifications\n"
        "/enable_notifications - Enable notifications\n"
        "/disable_notifications - Disable notifications\n"
        "/list_notifications - Show unread notifications\n"
        "/help - Show help information\n"
        "🔹 You can also use the buttons below for easy navigation.",
        reply_markup=main_keyboard(),
    )


@router.message(lambda message: message.text == "🛠 Help")
async def help_button_handler(message: types.Message):
    await help_handler(message)


@router.message()
async def fallback_handler(message: types.Message):
    logger.info(f"📩 Unknown command: {message.text}")

    await message.answer(
        "❌ Unknown command. Use /help or the buttons below for available options.",
        reply_markup=main_keyboard()
    )


async def set_webhook():
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        logger.info(f"Setting new webhook: {WEBHOOK_URL}")
        await bot.set_webhook(url=WEBHOOK_URL)
    else:
        logger.info("Webhook is already set.")


async def webhook_handler(request):
    body = await request.json()
    logger.info(f"📥 Incoming Telegram data: {body}")

    try:
        update = types.Update(**body)
        logger.info(f"Webhook received update: {update}")

        await dp.feed_update(bot, update)
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"❌ Error processing update: {e}")
        return web.Response(status=500)


async def on_shutdown(app):
    await bot.session.close()

app = web.Application()
app.on_shutdown.append(on_shutdown)


async def main():
    dp.startup.register(set_webhook)
    dp.shutdown.register(on_shutdown)

    app.router.add_post(WEBHOOK_PATH, webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner)
    await set_webhook()
    await site.start()

    logger.info(f"✅ Bot is running with webhook on {WEBHOOK_URL}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
