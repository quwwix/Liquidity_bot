"""Telegram bot with WebApp support."""

import logging
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import get_settings

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = get_settings()
    user_id = update.effective_user.id if update.effective_user else 0

    if settings.my_chat_id and user_id != settings.my_chat_id:
        await update.message.reply_text("⛔ Цей бот приватний. Доступ заборонено.")
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="📊 Відкрити OLX Liquidity",
                    web_app=WebAppInfo(url=settings.webapp_url),
                )
            ]
        ]
    )

    await update.message.reply_text(
        "👋 <b>OLX Liquidity Tracker</b>\n\n"
        "Приватний інструмент для аналізу ліквідності категорій OLX Ukraine.\n\n"
        "📈 Ліквідність — % проданих від загальної кількості\n"
        "⚡ Швидкість — середній час продажу в днях\n"
        "📦 Об'єм — кількість підтверджених продажів\n\n"
        "Дані оновлюються щодня о 8:00 (Київ).\n\n"
        "Натисни кнопку нижче, щоб відкрити Mini App:",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def setup_bot_menu(application: Application) -> None:
    settings = get_settings()
    if not settings.webapp_url or not settings.webapp_url.startswith("https://"):
        logger.info("Skipping menu button setup (WEBAPP_URL must be HTTPS)")
        return
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="📊 Liquidity",
                web_app=WebAppInfo(url=settings.webapp_url),
            )
        )
    except Exception as e:
        logger.warning("Could not set menu button: %s", e)


def create_bot_application() -> Application:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start_command))
    return application
