"""Telegram application factory: handler registration + an error handler that never crashes the webhook."""

from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot import commands, onboarding
from app.config import settings

log = logging.getLogger(__name__)

COMMANDS = [
    BotCommand("start", "Set up or change your preferences"),
    BotCommand("offers", "Your active offers"),
    BotCommand("why", "Why you got the last message"),
    BotCommand("profile", "What we know about you"),
    BotCommand("pause", "No offers for a while"),
    BotCommand("resume", "Start offers again"),
    BotCommand("stop", "Unsubscribe"),
    BotCommand("help", "All commands"),
]
ERROR_TEXT = "😅 Something went wrong on our side. Please try again in a moment."


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Log the type and update id only: message text is personal data and tracebacks can carry the token URL.
    update_id = update.update_id if isinstance(update, Update) else None
    log.error(
        "handler error on update %s: %s",
        update_id,
        type(context.error).__name__,
        exc_info=(type(context.error), context.error, context.error.__traceback__)
        if context.error
        else None,
    )
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(update.effective_chat.id, ERROR_TEXT, parse_mode=ParseMode.HTML)
        except Exception:  # the error handler itself must never raise
            log.warning("could not send the error reply")


def register_handlers(application: Application) -> None:
    private = filters.ChatType.PRIVATE
    application.add_handler(CommandHandler("start", onboarding.start, filters=private))
    application.add_handler(CallbackQueryHandler(onboarding.on_button, pattern=r"^ob:"))
    application.add_handler(CallbackQueryHandler(commands.on_offer_button, pattern=r"^o:"))
    for name, handler in {
        "help": commands.help_cmd,
        "profile": commands.profile_cmd,
        "offers": commands.offers_cmd,
        "why": commands.why_cmd,
        "pause": commands.pause_cmd,
        "resume": commands.resume_cmd,
        "stop": commands.stop_cmd,
    }.items():
        application.add_handler(CommandHandler(name, handler, filters=private))
    application.add_handler(MessageHandler(private & (filters.TEXT | filters.COMMAND), commands.unknown))
    application.add_error_handler(on_error)


async def set_commands(application: Application) -> None:
    """Fills the bot's "/" menu. Runs as post_init under polling; the webhook boot can call it too."""
    await application.bot.set_my_commands(COMMANDS)


def build_application() -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    application = Application.builder().token(settings.telegram_bot_token).post_init(set_commands).build()
    register_handlers(application)
    return application
