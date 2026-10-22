"""Telegram application factory — Phase-0 "hello" version.

Session C owns this folder and replaces this file in its Phase 1 (keep the `build_application()` name).
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings

HELLO = (
    "👋 Hi {name}!\n\n"
    "<b>Offer Engine</b> is warming up. Personalised offers start arriving here very soon.\n\n"
    "<i>This is a student demo with synthetic offers. No real purchases, no real data.</i>"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name if update.effective_user else "there"
    await update.effective_message.reply_html(HELLO.format(name=name))


def build_application() -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start))
    return application
