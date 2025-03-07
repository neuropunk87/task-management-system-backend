import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "task_management_system.settings")
django.setup()

import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters.command import Command
from asgiref.sync import sync_to_async
from django.conf import settings
from users.models import CustomUser


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
router = Router()


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔔 Enable Notifications"), KeyboardButton(text="🔕 Disable Notifications")],
            [KeyboardButton(text="🛠 Help")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@router.message(Command(commands=["start"]))
async def start_handler(message: types.Message):
    user_chat_id = message.chat.id

    user_exists = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).exists)()
    if user_exists:
        user = await sync_to_async(CustomUser.objects.get)(telegram_id=user_chat_id)
        user.telegram_notifications_enabled = True
        await sync_to_async(user.save)()
        await message.answer(
            "Welcome! Notifications are now enabled. You will receive task updates and deadline reminders.",
            reply_markup=main_keyboard(),
        )
    else:
        await message.answer(
            "Welcome! To receive notifications, link your Telegram ID in your profile.",
            reply_markup=main_keyboard(),
        )


@router.message(Command(commands=["enable_notifications"]))
async def enable_notifications(message: types.Message):
    user_chat_id = message.chat.id

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first)()
    if user:
        user.telegram_notifications_enabled = True
        await sync_to_async(user.save)()
        await message.answer("Notifications have been enabled. You will now receive updates.")
    else:
        await message.answer("Your Telegram ID is not linked to any user. Please link it in your profile.")


@router.message(lambda message: message.text == "🔔 Enable Notifications")
async def enable_notifications_button(message: types.Message):
    await enable_notifications(message)


@router.message(Command(commands=["disable_notifications"]))
async def disable_notifications(message: types.Message):
    user_chat_id = message.chat.id

    user = await sync_to_async(CustomUser.objects.filter(telegram_id=user_chat_id).first)()
    if user:
        user.telegram_notifications_enabled = False
        await sync_to_async(user.save)()
        await message.answer("Notifications have been disabled. You will no longer receive updates.")
    else:
        await message.answer("Your Telegram ID is not linked to any user. Please link it in your profile.")


@router.message(lambda message: message.text == "🔕 Disable Notifications")
async def disable_notifications_button(message: types.Message):
    await disable_notifications(message)


@router.message(Command(commands=["help"]))
async def help_handler(message: types.Message):
    await message.answer(
        "Available commands:\n"
        "/start - Start the bot and enable notifications\n"
        "/enable_notifications - Enable notifications\n"
        "/disable_notifications - Disable notifications\n"
        "/help - Show help information\n"
        "You can also use the buttons below for easy navigation.",
        reply_markup=main_keyboard(),
    )


@router.message(lambda message: message.text == "🛠 Help")
async def help_button_handler(message: types.Message):
    await help_handler(message)


# @router.message(Command(commands=["list_notifications"]))
# async def list_notifications(message: types.Message):
#     user_chat_id = message.chat.id
#
#     notifications = await sync_to_async(
#         lambda: list(Notification.objects.filter(user__telegram_id=user_chat_id, is_read=False).select_related("task")),
#         thread_sensitive=True
#     )()
#
#     if notifications:
#         response = "\n\n".join(
#             [f"📬 Task: {getattr(n.task, 'title', 'No Task')}\n{n.message}" for n in notifications]
#             # [f"📬 Task: {n.task.title if n.task else 'No Task'}\n{n.message}" for n in notifications]
#         )
#         await message.answer(response)
#     else:
#         await message.answer("No notifications.")
#
#
# @router.message(lambda message: message.text == "📬 Show List Notifications")
# async def list_notifications_button(message: types.Message):
#     await list_notifications(message)


@router.message()
async def fallback_handler(message: types.Message):
    await message.answer(
        "Command not recognized. Use /help or the buttons below for available options.",
        reply_markup=main_keyboard()
    )


async def main():
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
